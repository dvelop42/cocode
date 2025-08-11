# Log Streaming Implementation

## Overview

The log streaming functionality in cocode enables real-time display of agent output in the TUI panels. This feature provides immediate feedback to users about what each agent is doing, making it easier to monitor progress and debug issues.

## Architecture

### Components

1. **StreamingSubprocess** (`utils/subprocess.py`)
   - Executes agent commands with line-by-line output streaming
   - Uses separate threads for stdout and stderr to prevent blocking
   - Supports timeout and cancellation

2. **AgentRunner** (`agents/runner.py`)
   - Accepts stdout/stderr callbacks for processing output
   - Passes callbacks through to StreamingSubprocess
   - Collects output for error reporting

3. **AgentLifecycleManager** (`agents/lifecycle.py`)
   - Manages agent lifecycle (start/stop/restart)
   - Routes callbacks from caller to AgentRunner
   - Runs agents in separate threads for concurrency

4. **CocodeApp** (`tui/app.py`)
   - Creates callbacks via `_make_panel_callbacks()`
   - Routes output to appropriate AgentPanel
   - Manages UI updates in batch for performance

5. **AgentPanel** (`tui/agent_panel.py`)
   - Displays agent status and logs
   - Uses Textual's Log widget for scrollable output
   - Implements buffering with MAX_LOG_LINES limit

### Data Flow

```
Agent Process
    ↓ (stdout/stderr)
StreamingSubprocess
    ↓ (line-by-line callbacks)
AgentRunner
    ↓ (callbacks with agent context)
AgentLifecycleManager
    ↓ (callbacks with lifecycle info)
CocodeApp._make_panel_callbacks()
    ↓ (formatted output)
AgentPanel.add_log_line()
    ↓ (timestamped, styled)
Textual Log Widget
    ↓ (rendered)
User's Terminal
```

## Key Features

### Real-time Updates
- Output appears in panels as soon as agents produce it
- No buffering delays - line-by-line streaming
- Separate handling of stdout and stderr

### Performance Optimization
- **Batched UI Updates**: The app uses `with self.batch_update()` to reduce render cycles
- **Bounded Buffer**: Each panel limits logs to MAX_LOG_LINES (500 by default)
- **Auto-scrolling**: New output automatically scrolls into view
- **Thread-safe**: Concurrent agents can stream without interference

### Visual Feedback
- Timestamps on each log line
- Color coding for different message types:
  - Normal output: default color
  - Errors: red
  - Success messages: green
  - Status updates: blue/yellow

## Implementation Details

### Callback Creation (app.py)

```python
def _make_panel_callbacks(self, panel: AgentPanel):
    """Create unified callbacks for a panel."""

    def on_stdout(line: str) -> None:
        panel.add_log_line(line)

    def on_stderr(line: str) -> None:
        panel.add_log_line(f"[red]{line}[/red]")

    def on_completion(status: AgentStatus) -> None:
        if status.ready:
            panel.add_log_line("[green]Agent ready![/green]")
        elif status.exit_code == 0:
            panel.add_log_line("[green]Agent completed successfully[/green]")
        else:
            panel.add_log_line(f"[red]Agent failed: {status.error_message}[/red]")

    return on_stdout, on_stderr, on_completion
```

### Log Addition (agent_panel.py)

```python
def add_log_line(self, line: str) -> None:
    """Add a line to the agent's log."""
    log_widget = self.query_one(f"#log-{self.agent_name}", Log)
    timestamp = datetime.now().strftime("%H:%M:%S")
    # Log widget handles Rich markup in strings
    log_widget.write_line(f"[dim]{timestamp}[/dim] {line}")
```

### Streaming Process (subprocess.py)

```python
def _stream_output(self, pipe, stream_name, callback):
    """Read lines from a pipe and process them."""
    for line in pipe:
        if line:
            line = line.rstrip("\n\r")
            if callback:
                callback(line)  # Real-time callback
            self._output_queue.put((stream_name, line))
```

## Buffering Strategy

1. **Line Buffering**: Subprocess uses `bufsize=1` for line-buffered output
2. **Bounded History**: AgentPanel limits to MAX_LOG_LINES (500 lines)
3. **FIFO Eviction**: Oldest lines are removed when limit is reached
4. **Memory Efficiency**: Only keeps necessary history for user review

## Testing

The implementation includes comprehensive tests in `tests/unit/tui/test_log_streaming.py`:

1. **Basic Streaming**: Verifies output reaches panels
2. **High-volume Output**: Tests buffer limits with 1000+ lines
3. **Concurrent Agents**: Ensures isolation between agent outputs
4. **Error Handling**: Validates stderr and failure messages

## Usage

When agents run, their output automatically streams to their respective panels:

```bash
# Run with TUI (default - streaming enabled)
cocode run 123

# Run without TUI (CLI mode - also streams to console)
cocode run 123 --no-tui
```

## Future Enhancements

Potential improvements for future versions:

1. **Filtering**: Allow users to filter logs by type or keyword
2. **Search**: Add search functionality within logs
3. **Export**: Save logs to file for later analysis
4. **Highlighting**: Syntax highlighting for code in logs
5. **Folding**: Collapse/expand verbose sections
6. **Performance Metrics**: Show execution time and resource usage

## Summary

The log streaming implementation provides a robust, performant solution for real-time agent monitoring. By leveraging Textual's reactive UI framework and Python's threading capabilities, cocode delivers immediate feedback while maintaining responsive UI performance even with multiple agents producing high-volume output.
