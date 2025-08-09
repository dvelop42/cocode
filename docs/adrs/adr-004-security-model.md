# ADR-004: Security Model & Sandboxing

## Status
Accepted

## Context
cocode orchestrates multiple code agents that need to interact with the filesystem, network, and execute commands. We need to define a security model that balances safety with functionality, preventing agents from causing harm while allowing them to complete their tasks effectively.

### Security Considerations

#### 1. File System Access
Agents need to read and modify code within their assigned worktrees. Key concerns:
- Preventing access to sensitive files outside the project
- Protecting the main repository from corruption
- Isolating agents from each other's worktrees
- Preventing access to system files or user home directory secrets

#### 2. Network Access
Agents may need to:
- Install dependencies (npm, pip, etc.)
- Access documentation and APIs
- Use AI services for code generation
- Pull git submodules or dependencies

Security risks:
- Data exfiltration
- Accessing internal network resources
- Making excessive API calls
- Downloading malicious packages

#### 3. Process Execution
Agents run as subprocesses and may spawn their own child processes:
- Running tests and builds
- Installing dependencies
- Using language-specific tools

Risks:
- Resource exhaustion (CPU, memory, disk)
- Fork bombs
- Long-running or hung processes
- Privilege escalation

#### 4. Secret Management
Agents need access to:
- Git credentials (handled by system git)
- API tokens for AI services
- GitHub tokens (via gh CLI)

Concerns:
- Preventing secret leakage in logs
- Avoiding secrets in commits
- Protecting tokens from malicious agents

## Decision

### MVP Security Model (Phase 1)
We will implement a minimal, pragmatic security model for the MVP that relies on:

1. **Process Isolation via Git Worktrees**
   - Each agent operates in its own git worktree (`cocode_<agent>`)
   - Worktrees provide natural filesystem isolation
   - Agents cannot affect the main repository or each other

2. **User-Level Privileges**
   - Agents run with the same privileges as the user
   - No sandboxing or containerization in MVP
   - Rely on OS-level permissions and user trust

3. **Basic Secret Protection**
   - Pass secrets via environment variables only
   - Implement log redaction for common token patterns
   - Never store secrets in configuration files
   - Rely on gh CLI for GitHub authentication

4. **Resource Limits**
   - Implement timeout for agent execution (configurable, default 30 minutes)
   - Monitor and log resource usage
   - Allow manual cancellation via TUI

5. **Minimal Network Restrictions**
   - No network filtering in MVP
   - Log all network-accessing commands
   - Future: consider domain allowlisting

### Implementation Details

#### Environment Variable Passthrough
```python
# Use explicit allowlist for better security
ALLOWED_ENV_VARS = {
    'LANG', 'LC_ALL', 'LC_CTYPE', 'LC_MESSAGES', 'LC_TIME',
    'TERM', 'TERMINFO', 'USER', 'USERNAME', 'TZ', 'TMPDIR'
}

# Construct safe PATH from known directories
SAFE_PATH_DIRS = ['/usr/bin', '/bin', '/usr/local/bin', '/opt/homebrew/bin']
safe_path = ':'.join(SAFE_PATH_DIRS)

# Agent-specific environment
agent_env = {
    "COCODE_REPO_PATH": str(repo_path),
    "COCODE_ISSUE_NUMBER": str(issue_number),
    "COCODE_ISSUE_URL": issue_url,
    "COCODE_ISSUE_BODY_FILE": issue_body_path,
    "COCODE_READY_MARKER": "cocode ready for check",
    "PATH": safe_path,  # Controlled PATH
}

# Filter environment using allowlist
filtered_env = {
    k: v for k, v in os.environ.items()
    if k in ALLOWED_ENV_VARS or k.startswith('COCODE_')
}

# Merge environments
final_env = {**filtered_env, **agent_env}
```

#### Log Redaction
```python
import re

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
    ]
    
    def redact(self, text: str) -> str:
        """Redact secrets from text."""
        for pattern, replacement in self.PATTERNS:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text
```

#### Filesystem Boundary Validation
```python
from pathlib import Path

def validate_agent_path(path: Path, worktree_root: Path) -> bool:
    """Ensure agent cannot escape worktree boundaries."""
    try:
        # Resolve to absolute paths to handle symlinks and ../
        resolved_path = path.resolve()
        resolved_root = worktree_root.resolve()
        return resolved_path.is_relative_to(resolved_root)
    except (ValueError, RuntimeError):
        # Path resolution failed - treat as invalid
        return False

def safe_file_operation(file_path: str, worktree_root: Path) -> Path:
    """Validate and return safe path for file operations."""
    path = Path(file_path)
    if not validate_agent_path(path, worktree_root):
        raise SecurityError(f"Path {file_path} is outside worktree boundary")
    return path
```

#### Process Timeout and Cleanup
```python
import signal
import psutil

def run_agent(agent_cmd: List[str], timeout: int = 900) -> subprocess.CompletedProcess:
    """Run agent with timeout (default 15 minutes) and proper cleanup."""
    process = None
    try:
        process = subprocess.Popen(
            agent_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            # Start new process group for cleanup
            preexec_fn=os.setsid if os.name != 'nt' else None
        )
        
        stdout, _ = process.communicate(timeout=timeout)
        return subprocess.CompletedProcess(
            args=agent_cmd,
            returncode=process.returncode,
            stdout=stdout
        )
    except subprocess.TimeoutExpired:
        logger.error(f"Agent exceeded timeout of {timeout} seconds")
        if process:
            # Kill entire process group
            if os.name != 'nt':
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            else:
                # Windows: kill process tree
                parent = psutil.Process(process.pid)
                for child in parent.children(recursive=True):
                    child.kill()
                parent.kill()
        raise AgentTimeoutError(f"Agent execution exceeded {timeout}s limit")
```

### Security Warnings to Users
The tool will display clear warnings about the security model:

```
⚠️  Security Notice:
Agents run with your user privileges and can:
- Modify files in their worktree
- Access the network
- Execute commands

Only run agents you trust. Review agent configurations before use.
```

## Consequences

### Positive
- Simple to implement and understand
- No complex sandboxing to debug
- Agents have full functionality needed
- Natural isolation via git worktrees
- Easy to extend in future phases

### Negative
- Limited protection against malicious agents
- Relies heavily on user trust
- No fine-grained access control
- Potential for resource exhaustion
- No network access restrictions

### Mitigation Strategies
1. **Agent Vetting**: Document and encourage reviewing agent code
2. **Monitoring**: Log all agent actions for audit
3. **Manual Control**: Always require user confirmation for PR creation
4. **Resource Monitoring**: Show resource usage in TUI
5. **Quick Cancellation**: Easy abort via Ctrl+C in TUI

## Future Enhancements (Phase 2+)

### Container-Based Sandboxing
```yaml
# Future: Docker/Podman container per agent
agent_container:
  image: cocode/agent-sandbox:latest
  volumes:
    - ./worktree:/workspace:rw
    - ./repo:/repo:ro
  network: restricted
  resources:
    cpu: 2
    memory: 2G
  security_opts:
    - no-new-privileges
    - seccomp=cocode.json
```

### Network Filtering
- Implement HTTP(S) proxy for agents
- Allowlist of permitted domains
- Rate limiting for API calls
- Block access to local network (RFC1918)

### Enhanced File System Protection
- Use Linux namespaces or macOS sandbox-exec
- Read-only bind mounts for repo
- Temporary filesystems for build artifacts
- Quota enforcement on worktree size

### Fine-Grained Permissions
```yaml
# Future: Per-agent permission model
agent_permissions:
  filesystem:
    read: ["./worktree", "./repo"]
    write: ["./worktree"]
  network:
    allowed_domains: ["github.com", "*.npmjs.org"]
  processes:
    allowed_commands: ["npm", "git", "python"]
```

## References
- [OWASP Secure Coding Practices](https://owasp.org/www-project-secure-coding-practices-quick-reference-guide/)
- [Principle of Least Privilege](https://en.wikipedia.org/wiki/Principle_of_least_privilege)
- [Git Worktree Documentation](https://git-scm.com/docs/git-worktree)
- [subprocess Security Considerations](https://docs.python.org/3/library/subprocess.html#security-considerations)

## Decision Records
- **Date**: 2025-01-09
- **Deciders**: cocode development team
- **Status**: Accepted for MVP, with documented path for enhancement