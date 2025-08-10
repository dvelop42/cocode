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
- **Buffer size per agent**: 10MB in-memory buffer (initial)
- **Log rotation**: Automatic rotation when buffer exceeds 10MB
  - Compress and write to `.cocode/logs/agent_<name>_<timestamp>.log.gz`
  - Keep last 3 rotated logs per agent (configurable)
- **Streaming chunk size**: 4KB chunks for TUI updates
- **Retention policy**: Keep last 2000 lines per agent in TUI (configurable)
- **Disk persistence**:
  - Optional full log to `.cocode/logs/` directory
  - Automatic compression for logs > 10MB
  - Log rotation after 50MB total per agent
- **Verbose agent handling**: Dynamic buffer expansion up to 50MB for agents producing > 1MB/min
- **Rationale**: Prevents memory exhaustion while maintaining useful debugging context, handles verbose agents gracefully

### 3. Repository Size Limits
- **Size calculation methodology**:
  - Excludes `.git` directory for working tree size
  - Includes `.git` directory for total repository size
  - Excludes files matching `.gitignore` patterns
  - LFS objects counted separately with warning
- **Recommended max repo size**: 500MB working tree (no warning)
- **Warning threshold**: 1GB working tree (display warning, proceed)
- **Hard limit**: 5GB working tree (require explicit confirmation)
- **Total repository limit**: 10GB including `.git` directory
- **Worktree strategy**:
  - Use shallow clones (depth=1) for repos > 100MB
  - Single branch fetch for worktrees
  - Sparse checkout support for monorepos
  - Blob-less clones for repos with large binary history
- **Rationale**: Balances functionality with disk space and clone time, provides clear size expectations

### 4. Timeout Configuration
- **Default agent execution timeout**: 15 minutes (simple issues)
- **Adaptive timeout based on complexity**:
  - Simple issues (< 100 LOC change): 15 minutes
  - Medium issues (100-500 LOC): 30 minutes
  - Complex issues (> 500 LOC or refactoring): 45 minutes
  - Configurable multiplier based on repository size
- **Maximum agent timeout**: 60 minutes (hard limit)
- **Ready marker check interval**:
  - First 30 seconds: Check every 2 seconds
  - Next 2 minutes: Check every 5 seconds
  - After 2 minutes: Check every 10 seconds
- **Network operation timeouts**:
  - GitHub API calls: 30 seconds
  - Git operations: 5 minutes
  - Clone operations: 15 minutes + 1 min per 100MB repo size
- **Rationale**: Provides responsive feedback while adapting to task complexity

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

### Configuration Schema with Validation
```yaml
# .cocode/config.yaml
performance:
  max_concurrent_agents: 5      # min: 1, max: 20
  agent_timeout: 900            # min: 60, max: 3600 (seconds)
  max_repo_size_mb: 5000        # min: 100, max: 50000
  log_buffer_size_mb: 10        # min: 1, max: 100
  log_rotation_size_mb: 50      # min: 10, max: 500
  max_worktrees: 10             # min: 1, max: 50
  tui_log_lines: 2000           # min: 100, max: 10000

profiles:
  low:  # For CI/CD or low-end machines
    max_concurrent_agents: 2
    log_buffer_size_mb: 5
    agent_timeout: 600
  medium:  # Default profile
    max_concurrent_agents: 5
    log_buffer_size_mb: 10
    agent_timeout: 900
  high:  # For powerful workstations
    max_concurrent_agents: 10
    log_buffer_size_mb: 20
    agent_timeout: 1800
```

### Monitoring Metrics
- Agent execution time
- Memory usage per agent
- Log throughput rate (MB/min)
- Ready detection attempts
- Repository clone time
- Buffer overflow events
- Timeout violations
- Resource limit hits

### Edge Case Handling

#### Agent Exceeds Memory Limit
1. Send SIGTERM to agent process
2. Wait 10 seconds for graceful shutdown
3. Send SIGKILL if still running
4. Mark agent as failed with reason "memory_limit_exceeded"
5. Preserve partial work in worktree for debugging

#### Agent Exceeds Timeout
1. Send SIGTERM to agent process group
2. Wait 5 seconds for cleanup
3. Send SIGKILL to process group
4. Check for partial commits
5. Mark as failed with reason "timeout_exceeded"

#### Log Buffer Overflow
1. Trigger automatic rotation to disk
2. Compress rotated log
3. Continue with fresh buffer
4. Notify user if disk space < 100MB

#### Repository Size Violations
1. For warning threshold: Display warning, log, continue
2. For hard limit: Prompt user with options:
   - Continue anyway (override)
   - Use shallow clone
   - Use sparse checkout
   - Cancel operation

### Performance Testing Plan

#### Unit Tests
- Test resource limit enforcement
- Test timeout calculations
- Test log rotation logic
- Test size calculation accuracy

#### Integration Tests
```python
# test_performance_limits.py
def test_concurrent_agent_limit():
    """Verify system respects max concurrent agents"""

def test_memory_limit_enforcement():
    """Verify memory limits are enforced per agent"""

def test_timeout_adaptation():
    """Verify timeout adjusts based on complexity"""

def test_log_rotation():
    """Verify logs rotate at size threshold"""
```

#### Load Tests
- Scenario 1: 5 agents on 1GB repository
- Scenario 2: 10 agents with verbose logging
- Scenario 3: Long-running agents (> 30 min)
- Scenario 4: Memory pressure conditions
- Scenario 5: Large monorepo with sparse checkout

#### Performance Regression Tests
- Baseline metrics for each release
- Automated performance comparison
- Alert on > 10% regression

### Future Considerations
- Dynamic resource allocation based on system load
- Distributed agent execution
- Cloud-based agent runners
- Incremental log streaming to disk
- Machine learning for timeout prediction

## References
- [System Resource Management Best Practices](https://12factor.net/concurrency)
- [Git Performance Documentation](https://git-scm.com/docs/git-config#_performance)
- Similar tools: Jenkins (build limits), GitHub Actions (concurrency limits)
