# TUI Framework Prototypes

This directory contains prototype implementations for evaluating TUI frameworks for cocode.

## Setup

```bash
pip install -r requirements.txt
```

## Running the Prototypes

### Textual Demo
```bash
python textual_prototype/textual_demo.py
```

Features demonstrated:
- Three concurrent agent panels
- Real-time log streaming
- Keyboard navigation (1-3 to select agents, q to quit)
- Status indicators
- Reactive updates

### Rich Demo
```bash
python rich_prototype/rich_demo.py
```

Features demonstrated:
- Menu-driven interface
- Layout capabilities
- Streaming log simulation
- Basic panel structure

## Key Differences

| Feature | Textual | Rich |
|---------|---------|------|
| Interactivity | Built-in event system | Manual implementation |
| Layout | Automatic with CSS | Manual construction |
| Testing | Full test framework | No built-in testing |
| Code Complexity | ~150 lines | ~250 lines |
| Learning Curve | Moderate (reactive) | Low (imperative) |

## Recommendation

Based on the prototypes, **Textual** is recommended for cocode due to:
1. Better support for interactive TUIs
2. Built-in testing capabilities
3. Cleaner code structure
4. More maintainable for complex UIs

See `/docs/adrs/adr-001-tui-framework.md` for the full analysis.
