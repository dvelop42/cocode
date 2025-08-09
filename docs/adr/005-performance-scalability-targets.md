# ADR-005: Performance & Scalability Targets

## Status
Accepted

## Context
As cocode grows, we need to establish clear performance targets and resource limits to ensure reliable operation across different environments and use cases. These targets will guide implementation decisions and set user expectations.

## Decision
We will implement the following performance targets and limits for the MVP:

### 1. Concurrent Agent Limits
- **Maximum concurrent agents**: 5 (MVP)
- **Resource allocation**: Equal CPU shares per agent
- **Queue strategy**: FIFO with optional priority override
- **Rationale**: Balances parallelism with system resources on typical developer machines

### 2. Log Handling
- **Buffer size per agent**: 10MB in-memory buffer
- **Streaming chunk size**: 4KB chunks for TUI updates
- **Retention policy**: Keep last 1000 lines per agent in TUI
- **Disk persistence**: Optional full log to `.cocode/logs/` directory
- **Rationale**: Prevents memory exhaustion while maintaining useful debugging context

### 3. Repository Size Limits
- **Recommended max repo size**: 500MB (no warning)
- **Warning threshold**: 1GB (display warning, proceed)
- **Hard limit**: 5GB (require explicit confirmation)
- **Worktree strategy**: 
  - Use shallow clones for repos > 100MB
  - Single branch fetch for worktrees
  - Sparse checkout support for monorepos
- **Rationale**: Balances functionality with disk space and clone time

### 4. Timeout Configuration
- **Default agent execution timeout**: 15 minutes
- **Maximum agent timeout**: 60 minutes (configurable)
- **Ready marker check interval**: 
  - First 30 seconds: Check every 2 seconds
  - Next 2 minutes: Check every 5 seconds  
  - After 2 minutes: Check every 10 seconds
- **Network operation timeouts**:
  - GitHub API calls: 30 seconds
  - Git operations: 5 minutes
  - Clone operations: 15 minutes
- **Rationale**: Provides responsive feedback while avoiding excessive polling

### 5. Memory Management
- **Maximum memory per agent**: 2GB (soft limit via monitoring)
- **TUI memory budget**: 100MB
- **Total application target**: < 3GB for 5 agents
- **Memory pressure response**: Queue agents when > 80% system memory

### 6. Filesystem Limits
- **Maximum worktrees**: 10 (configurable)
- **Worktree cleanup**: Automatic after 7 days idle
- **Temp file cleanup**: Immediate after agent completion
- **State file size**: 10MB max for `.cocode/state.json`

### 7. Performance Targets
- **TUI responsiveness**: < 100ms for user interactions
- **Log streaming latency**: < 500ms from agent output to display
- **Agent startup time**: < 5 seconds
- **Ready detection latency**: < 2 seconds after commit

## Consequences

### Positive
- Predictable resource usage
- Clear user expectations
- Prevents system overload
- Enables optimization targets
- Supports wide range of hardware

### Negative  
- May limit power users with high-end hardware
- Requires configuration for edge cases
- Additional complexity for resource management

### Mitigation
- Make limits configurable via `.cocode/config.yaml`
- Provide `--performance-profile` flag (low/medium/high)
- Add monitoring dashboard for resource usage
- Document tuning guide for different scenarios

## Implementation Notes

### Configuration Schema
```yaml
# .cocode/config.yaml
performance:
  max_concurrent_agents: 5
  agent_timeout: 900  # seconds
  max_repo_size_mb: 5000
  log_buffer_size_mb: 10
  max_worktrees: 10
  
profiles:
  low:  # For CI/CD or low-end machines
    max_concurrent_agents: 2
    log_buffer_size_mb: 5
  high:  # For powerful workstations
    max_concurrent_agents: 10
    log_buffer_size_mb: 20
```

### Monitoring Metrics
- Agent execution time
- Memory usage per agent
- Log throughput rate
- Ready detection attempts
- Repository clone time

### Future Considerations
- Dynamic resource allocation based on system load
- Distributed agent execution
- Cloud-based agent runners
- Incremental log streaming to disk
- Adaptive timeout based on repository size

## References
- [System Resource Management Best Practices](https://12factor.net/concurrency)
- [Git Performance Documentation](https://git-scm.com/docs/git-config#_performance)
- Similar tools: Jenkins (build limits), GitHub Actions (concurrency limits)