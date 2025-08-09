# CLAUDE.md - Project Context for AI Assistants

## Project Overview

**cocode** is a macOS CLI tool that orchestrates multiple code agents to fix GitHub issues in parallel. It provides a TUI for monitoring agent progress and selecting the best solution for PR creation.

## Architecture Decision Records (ADRs)

### ADR-001: TUI Framework - Textual ✅
- **Decision**: Use Textual over Rich for TUI
- **Key Reasons**: Built-in async support, testing framework, reactive paradigm, better streaming log handling
- **Implementation**: Use Compose pattern, reactive attributes, CSS styling, messages for communication, workers for background tasks

### ADR-002: CLI Framework - Typer ✅
- **Decision**: Use Typer over Click for CLI
- **Key Reasons**: Type hints support, cleaner syntax, auto shell completion, modern Python patterns
- **Implementation**: Type hints for all args, Rich for console output, typer.testing.CliRunner for tests

### ADR-003: Agent Communication Protocol ✅
- **Decision**: Environment Variables + Git Commits
- **Protocol**:
  - Input: `COCODE_REPO_PATH`, `COCODE_ISSUE_NUMBER`, `COCODE_ISSUE_URL`, `COCODE_ISSUE_BODY_FILE`, `COCODE_READY_MARKER`
  - Output: Git commits with ready marker (`cocode ready for check`) in commit message
  - Ready detection: `git log -1 --format=%B | grep -q "cocode ready for check"`
- **Exit Codes**: 0=success, 1=error, 2=invalid config, 3=missing deps, 124=timeout, 130=interrupted

### ADR-004: Security Model ✅
- **MVP Model**: User-level privileges, no sandboxing
- **Isolation**: Git worktrees with filesystem boundary validation
- **Secrets**: Allowlist-based environment filtering, comprehensive log redaction
- **Resources**: 15-minute default timeout with process group cleanup
- **Future**: Container-based sandboxing, network filtering, fine-grained permissions

### ADR-005: Performance & Scalability Targets ✅
- **Concurrent Agents**: Max 5 agents (MVP), configurable via profiles (low/medium/high)
- **Log Handling**: 10MB buffer with auto-rotation, compression for verbose agents (>1MB/min), 2000-line TUI retention
- **Repository Limits**: 500MB working tree recommended, clear size calculation (excludes .git, respects .gitignore)
- **Timeouts**: Adaptive 15-45min based on complexity, smart polling intervals (2s→5s→10s)
- **Memory Management**: 2GB per agent soft limit, graceful handling of limit violations
- **Edge Cases**: Defined strategies for memory/timeout exceeded, log overflow, size violations

## Key Architectural Decisions

### Technology Stack
- **Language**: Python 3.10+
- **CLI Framework**: Typer (ADR-002)
- **TUI Framework**: Textual (ADR-001)
- **Agent Protocol**: Environment Variables + Git Commits (ADR-003)
- **Security Model**: User-level with worktree isolation (ADR-004)
- **Git Operations**: Direct git CLI commands via subprocess
- **GitHub API**: Via `gh` CLI (never direct API calls)
- **Distribution**: pipx for isolation

### Core Design Principles

1. **Agent Agnostic**: Support any CLI tool that can accept issue context and make commits
2. **Worktree Isolation**: Each agent gets its own git worktree to prevent conflicts
3. **Synchronous Execution**: MVP uses subprocess, not async (simpler debugging)
4. **State Persistence**: All state in `.cocode/` for crash recovery
5. **No Background Services**: Single process, ephemeral runs
6. **Security Through Simplicity**: User trust model with clear warnings (ADR-004)

## Keep It Simple (KISS) Guide

### Philosophy
"Make it work, make it right, make it fast" - in that order. Start with the simplest solution that could possibly work.

### Simplicity Rules

#### 1. No Premature Abstraction
```python
# ❌ BAD: Over-engineered for current needs
class AbstractAgentFactory(ABC):
    def create_agent(self) -> Agent:
        return self._instantiate_from_registry(
            self._resolve_dependencies()
        )

# ✅ GOOD: Simple and direct
def create_agent(agent_type: str) -> Agent:
    if agent_type == "claude-code":
        return ClaudeCodeAgent()
    elif agent_type == "codex":
        return CodexAgent()
    else:
        raise ValueError(f"Unknown agent: {agent_type}")
```

#### 2. Use Standard Library First
```python
# ❌ BAD: External dependency for simple task
import requests  # Don't add dependency
response = requests.get(url)

# ✅ GOOD: Standard library
import urllib.request
with urllib.request.urlopen(url) as response:
    data = response.read()

# Exception: Use subprocess for git, not GitPython
# ✅ GOOD: Direct and debuggable
subprocess.run(["git", "add", "."], check=True)
```

#### 3. Explicit Over Implicit
```python
# ❌ BAD: Magic behavior
class Agent:
    def __getattr__(self, name):
        # Complex dynamic attribute resolution
        return self._registry.get(name)

# ✅ GOOD: Clear and obvious
class Agent:
    @property
    def status(self) -> str:
        return self._status
```

#### 4. Flat Over Nested
```python
# ❌ BAD: Deep nesting
if condition1:
    if condition2:
        if condition3:
            do_something()

# ✅ GOOD: Early returns
if not condition1:
    return
if not condition2:
    return
if not condition3:
    return
do_something()
```

#### 5. Single Responsibility
```python
# ❌ BAD: Does too much
def process_agent_and_create_pr_and_notify(agent, issue):
    # 200 lines of mixed concerns
    pass

# ✅ GOOD: Focused functions
def run_agent(agent: Agent, issue: Issue) -> AgentResult:
    # Just runs the agent
    pass

def create_pr(result: AgentResult) -> str:
    # Just creates PR
    pass
```

#### 6. Avoid Clever Code
```python
# ❌ BAD: Clever one-liner
agents = [a for a in [create(t) for t in types] if a and a.valid]

# ✅ GOOD: Clear intent
agents = []
for agent_type in types:
    agent = create_agent(agent_type)
    if agent and agent.is_valid():
        agents.append(agent)
```

#### 7. Configuration Over Code
```python
# ❌ BAD: Hardcoded values
timeout = 1800  # What is this number?

# ✅ GOOD: Named constants with context
DEFAULT_AGENT_TIMEOUT = 1800  # 30 minutes
timeout = config.get("timeout", DEFAULT_AGENT_TIMEOUT)
```

#### 8. Fail Fast and Loud
```python
# ❌ BAD: Silent failure
try:
    result = do_something()
except:
    result = None  # Hide the error

# ✅ GOOD: Clear errors
try:
    result = do_something()
except SpecificError as e:
    logger.error(f"Failed to do something: {e}")
    raise CocodeError(f"Operation failed: {e}") from e
```

### When to Add Complexity

Only add complexity when you have a proven need:
- ❌ "We might need this later"
- ❌ "This would be more flexible"
- ❌ "Other projects do it this way"
- ✅ "We've hit this limitation 3 times"
- ✅ "Users are asking for this"
- ✅ "Tests are becoming difficult"

### Simplicity Checklist

Before committing code, ask:
- [ ] Can this be done with fewer lines?
- [ ] Can this be done without a new dependency?
- [ ] Will a new developer understand this in 30 seconds?
- [ ] Can this be tested with a simple unit test?
- [ ] Is there a standard library solution?
- [ ] Am I solving actual problems or imaginary ones?

### Examples from Our Codebase

#### Simple Agent Protocol (ADR-003)
Instead of complex RPC or message queues, we use:
- Environment variables for input
- Git commits for output
- Exit codes for status

#### Simple Security (ADR-004)
Instead of complex sandboxing in MVP:
- Git worktrees for isolation
- User-level permissions
- Clear warnings to users

#### Simple CLI (ADR-002)
Instead of complex command parsing:
- Typer with type hints
- Automatic help generation
- Standard patterns

Remember: **You can always add complexity later, but you can rarely remove it.**

## Project Structure

```
cocode/
├── src/
│   └── cocode/
│       ├── __init__.py
│       ├── __main__.py          # Entry point
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── init.py          # init command
│       │   ├── run.py           # run command
│       │   ├── doctor.py        # doctor command
│       │   └── clean.py         # clean command
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── base.py          # Agent ABC
│       │   ├── claude_code.py   # Claude Code implementation
│       │   └── codex_cli.py     # Codex CLI implementation
│       ├── git/
│       │   ├── __init__.py
│       │   ├── worktree.py      # Worktree management
│       │   └── operations.py    # Git operations
│       ├── github/
│       │   ├── __init__.py
│       │   ├── issues.py        # Issue operations via gh
│       │   └── pull_requests.py # PR operations via gh
│       ├── tui/
│       │   ├── __init__.py
│       │   ├── app.py           # Main TUI application
│       │   ├── panels.py        # Agent panels
│       │   └── base_panel.py    # Base agent panel
│       ├── config/
│       │   ├── __init__.py
│       │   ├── manager.py       # Config file management
│       │   └── state.py         # State management
│       └── utils/
│           ├── __init__.py
│           ├── logging.py       # Logging utilities
│           └── security.py      # Secret redaction
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── pyproject.toml
├── README.md
├── CLAUDE.md
├── CONTRIBUTING.md
└── LICENSE
```

## Key Implementation Guidelines

### CLI Framework (Typer)

Use Typer for all CLI commands with these patterns:

```python
import typer
from typing import Optional, List
from rich.console import Console
from rich.prompt import Confirm, Prompt

app = typer.Typer(
    name="cocode",
    help="Orchestrate multiple code agents to fix GitHub issues",
    add_completion=True,
)
console = Console()

@app.command()
def command_name(
    required_arg: str,
    optional_arg: Optional[str] = typer.Option(None, "--opt", "-o", help="Description"),
    flag: bool = typer.Option(False, "--flag", help="Boolean flag")
):
    """Command docstring becomes help text."""
    pass
```

- Use type hints for all arguments
- Provide help text for options
- Use Rich for console output and prompts
- Test with typer.testing.CliRunner
- Add shell completion with `add_completion=True`
- Use `--interactive/--no-interactive` pattern for prompts

### Git Operations

1. **Always use explicit git commands** - No GitPython or other libraries
2. **Worktree naming**: `cocode_<agent>` for directories, `cocode/<issue>-<agent>` for branches
3. **Fetch before operations**: Always `git fetch --all --prune` before worktree ops
4. **Clean check**: Ensure clean working tree before starting agents

### Agent Interface (ADR-003)

```python
# Agent environment variables (REQUIRED)
env = {
    "COCODE_REPO_PATH": "/path/to/repo",
    "COCODE_ISSUE_NUMBER": "123",
    "COCODE_ISSUE_URL": "https://github.com/org/repo/issues/123",
    "COCODE_ISSUE_BODY_FILE": "/tmp/issue_123_body.txt",
    "COCODE_READY_MARKER": "cocode ready for check"
}

# Safe environment variable passthrough (ADR-004)
ALLOWED_ENV_VARS = {
    'LANG', 'LC_ALL', 'LC_CTYPE', 'LC_MESSAGES', 'LC_TIME',
    'TERM', 'TERMINFO', 'USER', 'USERNAME', 'TZ', 'TMPDIR'
}

# Construct safe PATH from known directories
SAFE_PATH_DIRS = ['/usr/bin', '/bin', '/usr/local/bin', '/opt/homebrew/bin']
safe_path = ':'.join(SAFE_PATH_DIRS)

filtered_env = {
    k: v for k, v in os.environ.items()
    if k in ALLOWED_ENV_VARS or k.startswith('COCODE_')
}
env["PATH"] = safe_path  # Add controlled PATH
final_env = {**filtered_env, **env}

# Agent execution with timeout (ADR-004)
try:
    result = subprocess.run(
        [agent_binary, *agent_args],
        cwd=worktree_path,
        env=final_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=900  # 15 minutes default
    )
except subprocess.TimeoutExpired:
    raise AgentTimeoutError("Agent execution exceeded 15 minute limit")
```

### Ready Detection

Agents signal completion by including the exact string `"cocode ready for check"` in their final commit message. The marker can appear anywhere in the commit message (subject or body):

```bash
# Check for ready state (searches entire commit message including multiline body)
git log -1 --format=%B | grep -q "cocode ready for check"
```

**Valid commit examples:**
```bash
# Single line with marker
git commit -m "fix: issue #123 - cocode ready for check"

# Multiline with marker in body (recommended)
git commit -m "fix: resolve authentication issue" \
           -m "Implemented OAuth flow" \
           -m "cocode ready for check"

# Using heredoc
git commit -m "$(cat <<EOF
fix: issue #123

Detailed changes made.

cocode ready for check
EOF
)"
```

### Error Handling Patterns

```python
# Use specific exception types
class CocodeError(Exception): pass
class GitError(CocodeError): pass
class AgentError(CocodeError): pass
class GithubError(CocodeError): pass

# Always provide actionable error messages
try:
    result = subprocess.run(["gh", "auth", "status"], capture_output=True)
    if result.returncode != 0:
        raise GithubError(
            "GitHub CLI not authenticated. Run: gh auth login"
        )
except FileNotFoundError:
    raise GithubError(
        "GitHub CLI not installed. Install from: https://cli.github.com"
    )
```

### TUI Guidelines (Textual Framework - ADR-001)

1. **Keep it responsive**: Long operations should show progress
2. **Streaming logs**: Use Textual's Log widget for real-time output
3. **Clear status indicators**: ✓ ready, ✗ failed, ⟳ running
4. **Keyboard-first**: All operations accessible via keyboard
5. **Use Textual patterns**:
   - Compose pattern for building layouts
   - Reactive attributes for automatic UI updates
   - CSS for consistent styling
   - Messages for inter-component communication
   - Workers for background tasks without blocking UI
6. **Development Tools**:
   - Hot-reload support for rapid iteration
   - Inspector tool for debugging
   - Snapshot testing for UI verification

**Key Textual advantages over Rich (ADR-001):**
- Built-in async support with virtual DOM
- Native testing framework with event simulation
- Reactive paradigm reduces manual refresh logic
- ~150 lines of code vs ~250 for equivalent Rich implementation

### Testing Strategy

1. **Mock external commands**: Mock `subprocess.run` for git/gh commands
2. **Fixture-based testing**: Use fixture repos and issues
3. **TUI testing**: Use Textual's built-in testing framework with snapshot testing and event simulation
4. **Integration tests**: Real git operations in temp directories

## Code Style

### Python Conventions

```python
# Type hints for all functions
def create_worktree(
    repo_path: Path,
    branch_name: str,
    base_branch: str = "main"
) -> Path:
    ...

# Dataclasses for structured data
@dataclass
class AgentStatus:
    name: str
    branch: str
    worktree: Path
    ready: bool = False
    last_commit: Optional[str] = None

# Context managers for resource cleanup
with tempfile.NamedTemporaryFile() as f:
    f.write(issue_body.encode())
    f.flush()
    env["COCODE_ISSUE_BODY_FILE"] = f.name
    # run agent
```

### Logging

```python
import logging
logger = logging.getLogger(__name__)

# Structured logging
logger.info(
    "Starting agent",
    extra={"agent": agent_name, "issue": issue_number}
)

# Secret redaction (ADR-004)
class SecretRedactor:
    """Redact common secret patterns from logs."""
    
    PATTERNS = [
        # GitHub tokens
        (r'gh[ps]_[A-Za-z0-9]{36}', 'gh*_***'),
        # OpenAI/Anthropic tokens
        (r'sk-[A-Za-z0-9]{48}', 'sk-***'),
        (r'anthropic-[A-Za-z0-9]{40}', 'anthropic-***'),
        # JWT tokens
        (r'eyJ[A-Za-z0-9\-_]*\.[A-Za-z0-9\-_]*\.[A-Za-z0-9\-_]*', 'jwt-***'),
        # Database URLs
        (r'(postgres|mysql|mongodb)://[^@]+@[^/\s]+/\w+', r'\1://***:***@***/***'),
        # SSH private keys
        (r'-----BEGIN [A-Z ]+PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+PRIVATE KEY-----', '-----BEGIN PRIVATE KEY-----***-----END PRIVATE KEY-----'),
        # Generic API keys
        (r'api[_-]?key["\s:=]+["\'`]?([A-Za-z0-9_\-]{32,})', 'api_key=***'),
        # Bearer tokens
        (r'Bearer\s+[A-Za-z0-9\-._~+/]+=*', 'Bearer ***'),
        # AWS credentials
        (r'AKIA[0-9A-Z]{16}', 'AKIA***'),
        (r'aws[_-]?secret[_-]?access[_-]?key["\s:=]+["\'`]?([A-Za-z0-9/+=]{40})', 'aws_secret_access_key=***'),
        # Azure credentials
        (r'[a-z0-9]{8}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{12}', 'azure-client-id-***'),
        (r'azure[_-]?client[_-]?secret["\s:=]+["\'`]?([A-Za-z0-9_\-]{34,})', 'azure_client_secret=***'),
        # Google Cloud service accounts
        (r'"private_key":\s*"-----BEGIN [A-Z ]+PRIVATE KEY-----[^"]+-----END [A-Z ]+PRIVATE KEY-----\\n"', '"private_key": "-----BEGIN PRIVATE KEY-----***-----END PRIVATE KEY-----"'),
        (r'[a-zA-Z0-9_-]{40,}@[a-zA-Z0-9-]+\.iam\.gserviceaccount\.com', '***@***.iam.gserviceaccount.com'),
    ]
    
    def redact(self, text: str) -> str:
        """Redact secrets from text."""
        for pattern, replacement in self.PATTERNS:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text
```

## Performance Considerations

1. **Minimize gh calls**: Batch operations when possible
2. **Cache issue data**: Don't re-fetch during a run
3. **Stream logs**: Don't buffer entire output in memory
4. **Efficient polling**: Use exponential backoff for ready checks

## Security Considerations (ADR-004)

### MVP Security Model
1. **Process Isolation**: Each agent in separate git worktree
2. **User Privileges**: Agents run with user permissions (no sandboxing)
3. **Environment Filtering**: Allowlist-based with controlled PATH
4. **Secret Protection**: 
   - Never handle tokens directly (use gh for GitHub)
   - Environment variable passthrough only
   - Comprehensive log redaction patterns
   - Never store secrets in config files
5. **Resource Limits**: 15-minute default timeout with process group cleanup
6. **Filesystem Boundaries**: Path validation to prevent escaping worktree
7. **Input Validation**: Sanitize issue numbers, branch names
8. **No Dynamic Code**: Never use eval/exec

### Filesystem Boundary Validation
```python
from pathlib import Path

def validate_agent_path(path: Path, worktree_root: Path) -> bool:
    """Ensure agent cannot escape worktree boundaries."""
    try:
        resolved_path = path.resolve()
        resolved_root = worktree_root.resolve()
        return resolved_path.is_relative_to(resolved_root)
    except (ValueError, RuntimeError):
        return False
```

### Security Warning Display
```
⚠️  Security Notice:
Agents run with your user privileges and can:
- Modify files in their worktree
- Access the network
- Execute commands

Only run agents you trust. Review agent configurations before use.
```

## Common Pitfalls to Avoid

1. **Don't assume branch exists**: Always fetch and check
2. **Don't ignore worktree state**: Check for uncommitted changes
3. **Don't hardcode paths**: Use Path objects and resolve
4. **Don't swallow exceptions**: Log and re-raise with context

## Future Considerations (Post-MVP)

1. **Async execution**: Move to asyncio for better concurrency
2. **Plugin system**: Dynamic agent loading via entry points
3. **Config schema**: JSON Schema validation for config files
4. **Metrics**: OpenTelemetry integration for monitoring

## Useful Commands for Development

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Run in development mode with uv
uv pip install -e ".[dev]"

# Type checking
mypy src/cocode

# Linting
ruff check src/cocode

# Format code
black src/cocode

# Run tests with coverage
pytest --cov=cocode --cov-report=html

# Test TUI manually
python -m cocode run --debug

# Clean all cocode artifacts
find . -name "cocode_*" -type d -exec rm -rf {} +
find . -name ".cocode" -type d -exec rm -rf {} +
```

## Git Commit Convention

Use conventional commits:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `style:` Code style
- `refactor:` Refactoring
- `test:` Tests
- `chore:` Maintenance

Example: `feat: add claude-code agent integration`

## PR Guidelines

1. One feature per PR
2. Include tests for new functionality
3. Update documentation if needed
4. Ensure all CI checks pass
5. Reference the issue being addressed

## Writing Agents (ADR-003)

### Minimal Agent Example (Bash)
```bash
#!/bin/bash
set -e

# Validate required environment variables
[[ -z "$COCODE_REPO_PATH" ]] && exit 2
[[ -z "$COCODE_ISSUE_NUMBER" ]] && exit 2
[[ -z "$COCODE_ISSUE_BODY_FILE" ]] && exit 2
[[ -z "$COCODE_READY_MARKER" ]] && exit 2

# Read issue
issue_body=$(cat "$COCODE_ISSUE_BODY_FILE")

# Do work
echo "// Fix for issue #$COCODE_ISSUE_NUMBER" >> fix.js

# Commit with ready marker
git add .
git commit -m "fix: issue #$COCODE_ISSUE_NUMBER

$COCODE_READY_MARKER"
```

### Agent Exit Codes
| Code | Meaning | Cocode Action |
|------|---------|---------------|
| 0 | Success | Check for ready marker |
| 1 | General error | Mark agent as failed |
| 2 | Invalid config | Check agent setup |
| 3 | Missing deps | Suggest doctor command |
| 124 | Timeout | Agent exceeded time limit |
| 130 | Interrupted | User cancelled |

### Testing Your Agent
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

## Questions to Ask When Implementing

1. Is this the simplest solution that works?
2. Will this handle network failures gracefully?
3. Can the user recover from this error?
4. Is the user informed of what's happening?
5. Will this work on both Intel and Apple Silicon Macs?