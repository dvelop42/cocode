# cocode System Architecture

## Overview

cocode orchestrates multiple code agents to solve GitHub issues in parallel, providing a TUI for monitoring and selection.

## High-Level Architecture

```mermaid
graph TB
    subgraph "User Interface"
        CLI[CLI Commands]
        TUI[TUI Application]
    end

    subgraph "Core System"
        ORCH[Orchestrator]
        CONFIG[Config Manager]
        STATE[State Manager]
    end

    subgraph "Git Operations"
        REPO[Repository Manager]
        WT[Worktree Manager]
        PUSH[Push/PR Manager]
    end

    subgraph "GitHub Integration"
        GH[gh CLI Wrapper]
        ISSUES[Issue Fetcher]
        PR[PR Creator]
    end

    subgraph "Agent Framework"
        EXEC[Agent Executor]
        MONITOR[Ready Monitor]
        LOGS[Log Streamer]
    end

    subgraph "Agents"
        CLAUDE[Claude Code]
        CODEX[Codex CLI]
        CUSTOM[Custom Agents]
    end

    CLI --> ORCH
    TUI --> ORCH
    ORCH --> CONFIG
    ORCH --> STATE
    ORCH --> REPO
    ORCH --> EXEC

    REPO --> WT
    REPO --> GH

    GH --> ISSUES
    GH --> PR

    WT --> PUSH
    PUSH --> PR

    EXEC --> CLAUDE
    EXEC --> CODEX
    EXEC --> CUSTOM

    EXEC --> MONITOR
    EXEC --> LOGS

    LOGS --> TUI
    MONITOR --> STATE
```

## Component Responsibilities

### User Interface Layer
- **CLI**: Entry point for all commands (init, run, doctor, clean)
- **TUI**: Real-time monitoring and interaction interface

### Core System
- **Orchestrator**: Coordinates the entire workflow
- **Config Manager**: Handles .cocode/config.json
- **State Manager**: Manages .cocode/state.json and recovery

### Git Operations
- **Repository Manager**: Local repo detection and cloning
- **Worktree Manager**: Creates and manages git worktrees
- **Push/PR Manager**: Handles branch pushing and PR creation

### GitHub Integration
- **gh CLI Wrapper**: All GitHub API operations via gh
- **Issue Fetcher**: Retrieves and filters issues
- **PR Creator**: Creates pull requests with proper formatting

### Agent Framework
- **Agent Executor**: Subprocess management for agents
- **Ready Monitor**: Watches for completion markers
- **Log Streamer**: Real-time log streaming to TUI

## Data Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Orchestrator
    participant GitHub
    participant Agent
    participant Git

    User->>CLI: cocode run
    CLI->>Orchestrator: Start workflow
    Orchestrator->>GitHub: Fetch issues
    GitHub-->>Orchestrator: Issue list
    Orchestrator->>User: Select issue
    User-->>Orchestrator: Issue #123

    loop For each agent
        Orchestrator->>Git: Create worktree
        Orchestrator->>Agent: Start with context
        Agent->>Git: Make commits
        Agent->>Git: Final commit with marker
        Git-->>Orchestrator: Ready detected
    end

    Orchestrator->>User: Select best result
    User-->>Orchestrator: Choose agent
    Orchestrator->>Git: Push branch
    Orchestrator->>GitHub: Create PR
    GitHub-->>User: PR URL
```

## File System Layout

```
project-root/
├── .cocode/
│   ├── config.json          # User configuration
│   ├── state.json           # Current run state
│   └── logs/
│       ├── claude.log       # Agent logs
│       └── codex.log
├── cocode_claude/           # Claude's worktree
├── cocode_codex/            # Codex's worktree
└── original-repo/           # Main repository
```

## Agent Communication Protocol

```mermaid
graph LR
    subgraph "Environment Variables"
        ENV[COCODE_REPO_PATH<br/>COCODE_ISSUE_NUMBER<br/>COCODE_ISSUE_URL<br/>COCODE_ISSUE_BODY_FILE<br/>COCODE_READY_MARKER]
    end

    subgraph "Agent Process"
        AGENT[Agent Binary]
        WORK[Working Directory]
        LOG[Log Output]
        COMMIT[Git Commits]
    end

    ENV --> AGENT
    AGENT --> WORK
    AGENT --> LOG
    WORK --> COMMIT

    COMMIT -->|Contains Marker| READY[Ready Signal]
```

## Security Model

```mermaid
graph TB
    subgraph "Trust Boundary"
        USER[User Environment]
        TOKENS[API Tokens]
    end

    subgraph "cocode Process"
        MAIN[Main Process]
        REDACT[Secret Redaction]
    end

    subgraph "Agent Processes"
        AGENT1[Agent 1]
        AGENT2[Agent 2]
    end

    USER --> TOKENS
    TOKENS --> MAIN
    MAIN --> REDACT
    REDACT --> AGENT1
    REDACT --> AGENT2

    AGENT1 -.->|No Direct Access| TOKENS
    AGENT2 -.->|No Direct Access| TOKENS
```

## Performance Considerations

- **Concurrent Execution**: All agents run in parallel
- **Streaming Logs**: Line-buffered output prevents memory bloat
- **Lazy Loading**: Issues fetched on-demand
- **Worktree Reuse**: Existing worktrees are reused when possible
- **State Recovery**: Interrupted runs can be resumed
