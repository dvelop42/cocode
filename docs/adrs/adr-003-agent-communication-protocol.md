# ADR-003: Agent Communication Protocol

**Status**: Proposed → **ACCEPTED** ✅

**Date**: 2025-01-09

**Decision**: **Environment Variables + Git Commits**

## Context

We need to define a standardized protocol for communication between cocode and code agents. This protocol must support:
- Passing issue context to agents
- Monitoring agent progress
- Detecting when agents complete their work
- Handling errors and timeouts
- Supporting diverse agent implementations

## Options Evaluated

### Option 1: Command Line Arguments
```bash
agent --repo-path /path --issue-number 123 --issue-url https://... --issue-body-file /tmp/issue.txt
```

**Pros:**
- ✅ Explicit and discoverable
- ✅ Easy to test from command line
- ✅ Self-documenting with --help

**Cons:**
- ❌ Argument parsing varies by language
- ❌ Complex escaping for special characters
- ❌ Length limits on some systems
- ❌ Not all agents may support custom arguments

### Option 2: JSON Config File
```json
{
  "repo_path": "/path/to/repo",
  "issue_number": 123,
  "issue_url": "https://github.com/org/repo/issues/123",
  "issue_body": "Fix the bug in..."
}
```

**Pros:**
- ✅ Structured data format
- ✅ No escaping issues
- ✅ Can include complex data

**Cons:**
- ❌ Requires file I/O and parsing
- ❌ Need to manage temporary files
- ❌ More complex for simple agents
- ❌ File cleanup on errors

### Option 3: Environment Variables + Git Commits
```bash
export COCODE_REPO_PATH="/path/to/repo"
export COCODE_ISSUE_NUMBER="123"
export COCODE_ISSUE_URL="https://github.com/org/repo/issues/123"
export COCODE_ISSUE_BODY_FILE="/tmp/issue_123.txt"
export COCODE_READY_MARKER="cocode ready for check"
```

**Pros:**
- ✅ Universal language support
- ✅ No argument parsing needed
- ✅ Works with any executable
- ✅ Git commits are natural for code changes
- ✅ Ready marker in commits is persistent

**Cons:**
- ❌ Environment variable limits (usually generous)
- ❌ Less discoverable than CLI args
- ❌ Requires documentation

## Decision

**Choose Environment Variables + Git Commits** for the following reasons:

1. **Universal Compatibility**: Every language can read environment variables
2. **Simplicity**: No parsing libraries or complex logic needed
3. **Git-Native**: Using commits for state aligns with version control workflow
4. **Persistence**: Commit messages persist ready state even after crashes
5. **Flexibility**: Agents can be simple scripts or complex applications

## Protocol Specification

### Input Protocol

Agents receive context through environment variables:

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `COCODE_REPO_PATH` | Path | Yes | Absolute path to repository |
| `COCODE_ISSUE_NUMBER` | Integer | Yes | GitHub issue number |
| `COCODE_ISSUE_URL` | URL | Yes | Full GitHub issue URL |
| `COCODE_ISSUE_BODY_FILE` | Path | Yes | Path to file containing issue body |
| `COCODE_READY_MARKER` | String | Yes | Marker to include in final commit |

The agent's working directory is set to its worktree path.

### Output Protocol

#### Progress Communication
Agents communicate through git commits:
```bash
# Regular progress
git commit -m "feat: implement authentication"

# Final commit with ready marker
git commit -m "fix: issue #123 - cocode ready for check"
```

#### Log Streaming
Agents output logs to stdout/stderr. Both structured and plain text are supported:

**Structured (Recommended):**
```json
{"timestamp": "2024-01-09T12:00:00Z", "level": "info", "message": "Starting"}
```

**Plain Text:**
```
[INFO] Starting analysis
```

### Ready Detection

The ready marker (`cocode ready for check`) must appear in the commit message:
```bash
# Check for ready state
git log -1 --format=%B | grep -q "cocode ready for check"
```

### Exit Codes

| Code | Meaning | Cocode Action |
|------|---------|---------------|
| 0 | Success | Check for ready marker |
| 1 | General error | Mark agent as failed |
| 2 | Invalid config | Check agent setup |
| 3 | Missing deps | Suggest doctor command |
| 124 | Timeout | Agent exceeded time limit |
| 130 | Interrupted | User cancelled |

## Implementation Example

### Minimal Agent (Bash)
```bash
#!/bin/bash
set -e

# Read context
issue_file="$COCODE_ISSUE_BODY_FILE"
issue_number="$COCODE_ISSUE_NUMBER"
ready_marker="$COCODE_READY_MARKER"

echo "[INFO] Working on issue #$issue_number"

# Read issue
issue_body=$(cat "$issue_file")

# Do work (simplified)
echo "// Fix for issue #$issue_number" >> fix.js

# Commit with ready marker
git add .
git commit -m "fix: issue #$issue_number

$ready_marker"

echo "[INFO] Complete"
```

### Full Agent (Python)
```python
#!/usr/bin/env python3
import os
import sys
import json
import subprocess
from datetime import datetime

def log(level, message):
    """Output structured log"""
    print(json.dumps({
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": level,
        "message": message
    }))
    sys.stdout.flush()

def main():
    # Read environment
    repo_path = os.environ["COCODE_REPO_PATH"]
    issue_number = os.environ["COCODE_ISSUE_NUMBER"]
    issue_body_file = os.environ["COCODE_ISSUE_BODY_FILE"]
    ready_marker = os.environ["COCODE_READY_MARKER"]
    
    log("info", f"Starting issue #{issue_number}")
    
    # Read issue
    with open(issue_body_file) as f:
        issue_body = f.read()
    
    # Analyze and fix
    # ... agent logic ...
    
    # Commit changes
    subprocess.run(["git", "add", "."], check=True)
    message = f"fix: issue #{issue_number}\n\n{ready_marker}"
    subprocess.run(["git", "commit", "-m", message], check=True)
    
    log("info", "Complete")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

## Testing Your Agent

```bash
# Set up test environment
export COCODE_REPO_PATH="/tmp/test-repo"
export COCODE_ISSUE_NUMBER="1"
export COCODE_ISSUE_URL="https://github.com/test/repo/issues/1"
export COCODE_ISSUE_BODY_FILE="/tmp/issue.txt"
export COCODE_READY_MARKER="cocode ready for check"

# Create test issue
echo "Fix the bug" > /tmp/issue.txt

# Run agent
cd "$COCODE_REPO_PATH"
./my-agent

# Verify ready
git log -1 --format=%B | grep -q "$COCODE_READY_MARKER" && echo "Success!"
```

## Consequences

### Positive
- Simple protocol that any tool can implement
- No dependencies or parsing libraries needed
- Git-native approach aligns with version control
- Ready state persists in commit history
- Easy to test and debug

### Negative
- Environment variables less discoverable than CLI args
- Requires documentation for agent developers
- No built-in validation of inputs

### Mitigation
- Provide clear documentation and examples
- Include example agents in multiple languages
- cocode doctor can validate agent setup
- Test harness for agent developers

## Future Considerations

- **Streaming Updates**: Could add WebSocket/SSE for real-time progress
- **Bidirectional Communication**: Could add callback URLs for agent questions
- **Resource Limits**: Could pass CPU/memory limits via environment
- **Authentication**: Could pass agent-specific tokens if needed

## References
- [Agent Protocol Specification](../architecture/agent-protocol.md)
- [CLAUDE.md Agent Interface](../../CLAUDE.md#agent-interface)
- [POSIX Environment Variables](https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap08.html)