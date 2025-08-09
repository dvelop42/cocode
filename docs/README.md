# cocode Documentation

## Overview

cocode orchestrates multiple code agents to fix GitHub issues in parallel.

## Documentation Structure

### Architecture
- [System Overview](architecture/system-overview.md) - High-level architecture and data flow
- [Agent Protocol](architecture/agent-protocol.md) - Agent communication specification

### Architecture Decision Records (ADRs)
- [ADR-001: TUI Framework Selection](adrs/adr-001-tui-framework.md) - **Accepted** (Textual)
- [ADR-002: CLI Framework Selection](adrs/adr-002-cli-framework.md) - **Accepted** (Typer)
- [ADR-003: Agent Communication Protocol](adrs/adr-003-agent-protocol.md) - Pending
- [ADR-004: Security Model](adrs/adr-004-security.md) - Pending
- [ADR-005: Performance Targets](adrs/adr-005-performance.md) - Pending

### Development
- [Development Setup](development-setup.md) - Getting started guide
- [Contributing Guide](../CONTRIBUTING.md) - How to contribute
- [Testing Strategy](testing-strategy.md) - Testing approach and guidelines

### User Guides
- [Installation Guide](installation.md) - Installing cocode
- [Quick Start](quick-start.md) - First steps with cocode
- [Configuration](configuration.md) - Configuration options
- [Troubleshooting](troubleshooting.md) - Common issues and solutions

## Quick Links

- [GitHub Repository](https://github.com/dvelop42/cocode)
- [Issue Tracker](https://github.com/dvelop42/cocode/issues)
- [Project Board](https://github.com/dvelop42/cocode/projects)

## Key Concepts

### Agents
Code agents are CLI tools that can:
- Accept issue context via environment variables
- Make changes to a git repository
- Commit their work incrementally
- Signal completion with a marker in commit messages

### Worktrees
Each agent works in an isolated git worktree, preventing conflicts and allowing parallel execution.

### Ready Detection
Agents signal completion by including "cocode ready for check" in their final commit message.

### Base Agent
The base agent is your preferred agent that can provide recommendations when multiple agents complete successfully.

## Architecture Principles

1. **Agent Agnostic**: Support any CLI tool that follows the protocol
2. **Parallel Execution**: All agents run simultaneously
3. **State Persistence**: Recoverable from interruptions
4. **GitHub Native**: Uses gh CLI for all GitHub operations
5. **Security First**: No direct token handling, secret redaction

## Getting Help

- Check the [Troubleshooting Guide](troubleshooting.md)
- Search [existing issues](https://github.com/dvelop42/cocode/issues)
- Ask in [Discussions](https://github.com/dvelop42/cocode/discussions)
- Report bugs via [GitHub Issues](https://github.com/dvelop42/cocode/issues/new)
