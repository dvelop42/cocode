# CLAUDE.md - Project Context for AI Assistants

## Project Overview

**cocode** is a macOS CLI tool that orchestrates multiple code agents to fix GitHub issues in parallel. It provides a TUI for monitoring agent progress and selecting the best solution for PR creation.

## Key Architectural Decisions

### Technology Stack
- **Language**: Python 3.10+
- **CLI Framework**: Typer (decided in ADR-002)
- **TUI Framework**: Textual or Rich (TBD during implementation)
- **Git Operations**: Direct git CLI commands via subprocess
- **GitHub API**: Via `gh` CLI (never direct API calls)
- **Distribution**: pipx for isolation

### Core Design Principles

1. **Agent Agnostic**: Support any CLI tool that can accept issue context and make commits
2. **Worktree Isolation**: Each agent gets its own git worktree to prevent conflicts
3. **Synchronous Execution**: MVP uses subprocess, not async (simpler debugging)
4. **State Persistence**: All state in `.cocode/` for crash recovery
5. **No Background Services**: Single process, ephemeral runs

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

app = typer.Typer(help="Your command description")

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
- Use Rich for console output
- Test with typer.testing.CliRunner

### Git Operations

1. **Always use explicit git commands** - No GitPython or other libraries
2. **Worktree naming**: `cocode_<agent>` for directories, `cocode/<issue>-<agent>` for branches
3. **Fetch before operations**: Always `git fetch --all --prune` before worktree ops
4. **Clean check**: Ensure clean working tree before starting agents

### Agent Interface

```python
# Agent environment variables
env = {
    "COCODE_REPO_PATH": "/path/to/repo",
    "COCODE_ISSUE_NUMBER": "123",
    "COCODE_ISSUE_URL": "https://github.com/org/repo/issues/123",
    "COCODE_ISSUE_BODY_FILE": "/tmp/issue_123_body.txt",
    "COCODE_READY_MARKER": "cocode ready for check"
}

# Agent execution
subprocess.run(
    [agent_binary, *agent_args],
    cwd=worktree_path,
    env={**os.environ, **env},
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)
```

### Ready Detection

Agents signal completion by including the exact string `"cocode ready for check"` in their final commit message. Poll using:

```bash
git log -1 --format=%s | grep -q "cocode ready for check"
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

### TUI Guidelines

1. **Keep it responsive**: Long operations should show progress
2. **Streaming logs**: Use generators for real-time output
3. **Clear status indicators**: ✓ ready, ✗ failed, ⟳ running
4. **Keyboard-first**: All operations accessible via keyboard

### Testing Strategy

1. **Mock external commands**: Mock `subprocess.run` for git/gh commands
2. **Fixture-based testing**: Use fixture repos and issues
3. **TUI testing**: Use Textual's testing utilities
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

# Secret redaction
def redact_secrets(text: str) -> str:
    # Redact common patterns
    patterns = [
        r'(gh[ps]_[A-Za-z0-9]{36})',  # GitHub tokens
        r'(sk-[A-Za-z0-9]{48})',       # OpenAI tokens
        # Add more patterns
    ]
    ...
```

## Performance Considerations

1. **Minimize gh calls**: Batch operations when possible
2. **Cache issue data**: Don't re-fetch during a run
3. **Stream logs**: Don't buffer entire output in memory
4. **Efficient polling**: Use exponential backoff for ready checks

## Security Considerations

1. **Never handle tokens directly**: Use gh for GitHub, env vars for agents
2. **Validate inputs**: Sanitize issue numbers, branch names
3. **No eval/exec**: Never execute dynamic code
4. **Log redaction**: Always redact potential secrets

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
# Run in development mode
pip install -e ".[dev]"

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

## Questions to Ask When Implementing

1. Is this the simplest solution that works?
2. Will this handle network failures gracefully?
3. Can the user recover from this error?
4. Is the user informed of what's happening?
5. Will this work on both Intel and Apple Silicon Macs?