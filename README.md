# cocode

> Orchestrate multiple code agents to fix GitHub issues in parallel

cocode is a macOS command-line tool that reads a GitHub issue and orchestrates multiple local code agents (e.g., Codex CLI, Claude Code) to attempt a fix in parallel. It presents a split-pane TUI showing each agent's live work log and allows you to pick the best result to create a PR.

## Features

- **Parallel Agent Execution**: Run multiple code agents simultaneously on the same issue
- **Live Progress Monitoring**: Split-pane TUI with real-time agent logs
- **Smart PR Creation**: Choose the best solution or let the base agent recommend
- **Git Worktree Isolation**: Each agent works in its own isolated worktree
- **GitHub Integration**: Seamless issue fetching and PR creation via `gh` CLI

## Prerequisites

- macOS (Apple Silicon or Intel)
- Python 3.10+
- [uv](https://github.com/astral-sh/uv) - Fast Python package manager
- git >= 2.31
- [GitHub CLI (`gh`)](https://cli.github.com/) - authenticated
- At least one supported agent:
  - [claude-code](https://github.com/anthropics/claude-code)
  - [codex-cli](https://github.com/example/codex-cli)

## Installation

### Using pipx (recommended for users)

```bash
pipx install cocode
```

### Using uv (for development)

```bash
# Clone the repository
git clone https://github.com/dvelop42/cocode.git
cd cocode

# Set up development environment
make dev

# Run CI checks locally before pushing
make ci
```

## Quick Start

1. **Initialize cocode** - Configure your agents and preferences:
   ```bash
   cocode init
   ```

2. **Run on an issue** - Start the parallel agent workflow:
   ```bash
   cocode run
   ```

3. **Check system** - Verify all dependencies:
   ```bash
   cocode doctor
   ```

## Usage

### Initialize Configuration

```bash
cocode init
```

Interactive setup that:
- Verifies GitHub CLI authentication
- Discovers installed agents
- Lets you select which agents to use
- Chooses a base agent for recommendations

### Run Workflow

```bash
cocode run
```

Launches the TUI workflow:
1. Select or clone a repository
2. Choose a GitHub issue to work on
3. Watch agents work in parallel
4. Review results and create a PR

### System Diagnostics

```bash
cocode doctor
```

Checks:
- Dependency versions and paths
- GitHub authentication status
- Agent availability
- Environment configuration

### Cleanup

```bash
cocode clean        # Safe cleanup
cocode clean --hard # Remove unmerged worktrees (with confirmation)
```

## TUI Keybindings

| Key | Action |
|-----|--------|
| `1-9` | Switch to agent tab N |
| `[`/`]` | Cycle through agent tabs |
| `/` | Search within current log |
| `g` | Refresh issue list / poll ready state |
| `r` | Restart current agent |
| `d` | Show diff of last commit |
| `p` | Open PR creation dialog |
| `?` | Show help overlay |
| `q` | Quit (prompts if agents running) |

## Development

### Setting Up

```bash
# Clone and install
git clone https://github.com/dvelop42/cocode.git
cd cocode
make dev  # Sets up virtual environment, installs dependencies, and configures pre-commit hooks
```

Pre-commit hooks are automatically installed and will:
- Run linting (ruff) and formatting (black) on commit
- Run full test suite with coverage on push
- Check for secrets and common issues

### Development Commands

```bash
# Run all CI checks locally (before pushing)
make ci

# Individual checks
make lint        # Run ruff linter
make format      # Format code with black
make type-check  # Run mypy type checker
make test        # Run tests with coverage

# Auto-fix issues
make fix         # Fix linting and formatting issues

# Pre-commit hooks
make pre-commit  # Run all pre-commit hooks manually
pre-commit run --all-files  # Same as above

# Clean up
make clean       # Remove caches and generated files
```

### Running CI Locally

Before pushing changes, always run:

```bash
make ci
```

This runs the same checks as GitHub Actions CI:
- Ruff linting
- Black formatting check
- Mypy type checking
- Pytest with coverage (45% minimum)

### Pre-commit Hooks

Pre-commit hooks are automatically installed when you run `make dev`. They will:

**On every commit:**
- Fix and check linting with ruff
- Format code with black
- Check for trailing whitespace
- Fix end-of-file issues
- Check for merge conflicts
- Scan for secrets

**On push:**
- Run full test suite
- Check test coverage (45% minimum)

To run hooks manually:
```bash
make pre-commit  # or
pre-commit run --all-files
```

To skip hooks temporarily (not recommended):
```bash
git commit --no-verify
git push --no-verify
```

## Configuration

Configuration is stored in `.cocode/` within your project:

```
.cocode/
├── config.json    # Agent selection and preferences
├── state.json     # Current run state
└── logs/          # Agent execution logs
    ├── claude.log
    └── codex.log
```

### config.json

```json
{
  "agents": ["claude-code", "codex-cli"],
  "base_agent": "claude-code"
}
```

## Agent Integration

Agents receive issue context via environment variables:
- `COCODE_REPO_PATH` - Repository path
- `COCODE_ISSUE_NUMBER` - Issue number
- `COCODE_ISSUE_URL` - Full issue URL
- `COCODE_ISSUE_BODY_FILE` - Path to issue body text
- `COCODE_READY_MARKER` - Marker for completion signal

Agents signal completion by including `"cocode ready for check"` in their final commit message.

## Project Conventions

If your repository contains a `COCODE.md` file, cocode will read and apply team-specific rules for:
- PR labels
- Commit message formats
- Branch naming conventions
- Review requirements

## Development

```bash
# Clone the repository
git clone https://github.com/yourusername/cocode.git
cd cocode

# Install development dependencies with uv
uv pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check .
mypy .
```

## Architecture

cocode uses:
- Git worktrees for isolated agent workspaces
- GitHub CLI for API operations
- Python subprocess for synchronous agent execution (MVP)
- Textual for the reactive TUI interface

## Security

- GitHub authentication handled via `gh` CLI
- Agent API keys read from environment variables
- Basic secret redaction in logs and TUI output
- No telemetry or remote data collection

## Roadmap

- [ ] Linux support
- [ ] Fork-and-PR workflow
- [ ] CI/test integration before PR creation
- [ ] Agent plugin registry
- [ ] GitHub Enterprise support

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

MIT - see [LICENSE](LICENSE) file for details

## Support

- Report issues: [GitHub Issues](https://github.com/dvelop42/cocode/issues)
- Documentation: [Wiki](https://github.com/dvelop42/cocode/wiki)
- Discussions: [GitHub Discussions](https://github.com/dvelop42/cocode/discussions)