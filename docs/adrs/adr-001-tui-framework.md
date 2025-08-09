# ADR-001: Choose TUI Framework

## Status
Accepted

## Context
The cocode project requires a Terminal User Interface (TUI) to display multiple agent outputs simultaneously, allow user interaction for selecting the best solution, and provide real-time status updates. We need to choose between Textual and Rich as our TUI framework.

## Decision
We will use **Textual** as the TUI framework for cocode.

## Rationale

### Evaluation Criteria & Results

#### 1. Performance with Streaming Logs
- **Textual**: ✅ Excellent - Built-in async support, efficient rendering with virtual DOM, handles high-frequency updates smoothly
- **Rich**: ⚠️ Good - Can handle streaming but requires manual refresh management, potential flickering with rapid updates

#### 2. Testing Capabilities
- **Textual**: ✅ Excellent - Built-in testing framework, supports snapshot testing, event simulation, and headless testing
- **Rich**: ❌ Limited - No dedicated testing utilities, requires custom mocking solutions

#### 3. Documentation Quality
- **Textual**: ✅ Excellent - Comprehensive docs with tutorials, API reference, and examples
- **Rich**: ✅ Good - Well-documented but focuses more on console output than interactive TUIs

#### 4. Community Support
- **Textual**: ✅ Active - Growing community, responsive maintainers, regular updates
- **Rich**: ✅ Very Active - Larger user base but mostly for non-TUI use cases

#### 5. Feature Completeness for Our Use Case
- **Textual**: ✅ Complete - All required features out-of-the-box:
  - Multiple concurrent panels
  - Keyboard navigation with customizable bindings
  - Reactive state management
  - CSS-based styling
  - Built-in widgets (Log, Button, etc.)
  - Event-driven architecture

- **Rich**: ⚠️ Partial - Requires significant custom implementation:
  - Manual layout management
  - Custom event loop for keyboard input
  - No built-in interactive widgets
  - Complex state management

#### 6. Development Experience
- **Textual**: ✅ Superior - Reactive paradigm, hot-reload support, inspector tool
- **Rich**: ⚠️ Adequate - More imperative, requires manual refresh logic

### Prototype Comparison

Both prototypes were created to demonstrate key features:

**Textual Prototype** (`prototypes/textual_prototype/textual_demo.py`):
- Clean separation of concerns with widget classes
- Automatic layout management
- Built-in keyboard bindings
- Reactive updates
- ~150 lines of code

**Rich Prototype** (`prototypes/rich_prototype/rich_demo.py`):
- Manual layout construction
- Complex threading for input handling
- Manual refresh management
- Limited interactivity
- ~250 lines of code for similar functionality

### Size Considerations
- **Textual**: ~2MB - Acceptable given the feature set
- **Rich**: ~500KB - Smaller but requires more custom code

## Consequences

### Positive
- Faster development with built-in components
- Better maintainability with reactive paradigm
- Robust testing capabilities
- Professional, polished UI out-of-the-box
- Future-proof with active development
- Better accessibility support

### Negative
- Larger dependency footprint
- Steeper initial learning curve for developers unfamiliar with reactive patterns
- Potential overkill for simpler use cases

### Mitigation
- Document Textual patterns and best practices in CONTRIBUTING.md
- Create reusable components for common patterns
- Provide examples and templates for new contributors

## Implementation Notes

### Key Textual Features to Leverage
1. **Compose Pattern**: Use for building complex layouts
2. **Reactive Attributes**: For automatic UI updates
3. **CSS Styling**: For consistent theming
4. **Messages**: For inter-component communication
5. **Workers**: For background tasks without blocking UI

### Migration Path
If we ever need to migrate away from Textual:
1. Abstract TUI logic behind interfaces
2. Keep business logic separate from UI components
3. Use dependency injection for TUI components

## References
- [Textual Documentation](https://textual.textualize.io/)
- [Rich Documentation](https://rich.readthedocs.io/)
- Prototype code in `/prototypes/` directory
- Issue #79: TUI Framework Selection