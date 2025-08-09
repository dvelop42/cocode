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
- git >= 2.31
- [GitHub CLI (`gh`)](https://cli.github.com/) - authenticated
- At least one supported agent:
  - [claude-code](https://github.com/anthropics/claude-code)
  - [codex-cli](https://github.com/example/codex-cli)

## Installation

```bash
pipx install cocode
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

# Install development dependencies
pip install -e ".[dev]"

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