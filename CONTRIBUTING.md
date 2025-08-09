# Contributing to cocode

Thank you for your interest in contributing to cocode! This guide will help you get started.

## Code of Conduct

Please be respectful and constructive in all interactions. We aim to maintain a welcoming and inclusive community.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally
3. **Set up development environment** (see [Development Setup](docs/development-setup.md))
4. **Create a feature branch** from `main`
5. **Make your changes** with clear commits
6. **Write/update tests** as needed
7. **Submit a pull request**

## Development Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/cocode.git
cd cocode

# Add upstream remote
git remote add upstream https://github.com/dvelop42/cocode.git

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On macOS/Linux

# Install in development mode
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Run type checking
mypy src/cocode

# Run linting
ruff check src/cocode
```

## Finding Issues to Work On

Look for issues labeled:
- `good-first-issue` - Great for newcomers
- `help-wanted` - Community help needed
- `needs-design` - Design discussion needed

Check the [Project Board](https://github.com/dvelop42/cocode/projects) for current priorities.

## Pull Request Process

### Before Submitting

1. **Check existing issues/PRs** to avoid duplicates
2. **Follow the architecture** defined in [CLAUDE.md](CLAUDE.md)
3. **Write clear commit messages** using [conventional commits](https://www.conventionalcommits.org/)
4. **Add tests** for new functionality
5. **Update documentation** if needed
6. **Run all checks locally**:
   ```bash
   make test
   make lint
   make typecheck
   ```

### PR Guidelines

#### Title Format
```
<type>: <description>

Types:
- feat: New feature
- fix: Bug fix
- docs: Documentation
- test: Tests
- refactor: Code refactoring
- chore: Maintenance
```

#### PR Description Template
```markdown
## Summary
Brief description of changes

## Motivation
Why is this change needed?

## Changes
- List of changes
- Another change

## Testing
How has this been tested?

## Screenshots (if applicable)
Add screenshots for UI changes

## Checklist
- [ ] Tests pass locally
- [ ] Documentation updated
- [ ] Follows code style
- [ ] Addresses linked issue
```

### Review Process

1. **Automated checks** must pass
2. **Code review** by maintainers
3. **Address feedback** promptly
4. **Squash commits** if requested
5. **Merge** when approved

## Code Style

### Python Guidelines

```python
# Use type hints
def process_agent(agent_name: str, timeout: int = 300) -> AgentResult:
    ...

# Use dataclasses for data structures
@dataclass
class AgentConfig:
    name: str
    command: List[str]
    environment: Dict[str, str]

# Clear variable names
# Good
repository_path = "/path/to/repo"
# Bad
rp = "/path/to/repo"

# Docstrings for public functions
def create_worktree(repo: Repository, branch: str) -> Path:
    """Create a git worktree for the agent.
    
    Args:
        repo: Repository object
        branch: Branch name to create
        
    Returns:
        Path to the created worktree
        
    Raises:
        GitError: If worktree creation fails
    """
```

### Import Order

```python
# Standard library
import os
import sys
from pathlib import Path

# Third-party
import click
from rich.console import Console

# Local
from cocode.agents import AgentExecutor
from cocode.config import ConfigManager
```

## Testing

### Test Structure

```python
# tests/unit/test_agent_executor.py
import pytest
from unittest.mock import Mock, patch

from cocode.agents import AgentExecutor

def test_agent_executor_starts_process():
    """Test that agent executor starts subprocess correctly."""
    with patch('subprocess.Popen') as mock_popen:
        executor = AgentExecutor()
        executor.start("test-agent", env={"TEST": "value"})
        
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        assert "test-agent" in call_args[0][0]
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=cocode --cov-report=html

# Run specific test file
pytest tests/unit/test_agent_executor.py

# Run with verbose output
pytest -v

# Run only marked tests
pytest -m "not slow"
```

## Documentation

### Code Documentation

- Add docstrings to all public functions/classes
- Include type hints for clarity
- Document exceptions that can be raised
- Add usage examples for complex functions

### User Documentation

- Update README.md for user-facing changes
- Add to docs/ for detailed guides
- Include examples and screenshots
- Keep language clear and concise

## Architecture Decisions

For significant changes, create an ADR (Architecture Decision Record):

1. Copy template: `docs/adrs/template.md`
2. Name it: `adr-XXX-short-title.md`
3. Fill in sections:
   - Status (proposed/accepted/rejected)
   - Context
   - Decision
   - Consequences
4. Link from main docs

## Release Process

Releases are managed by maintainers:

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Create git tag: `git tag -a v0.1.0 -m "Release v0.1.0"`
4. Push tag: `git push upstream v0.1.0`
5. GitHub Actions creates release

## Getting Help

- Check [existing issues](https://github.com/dvelop42/cocode/issues)
- Ask in [Discussions](https://github.com/dvelop42/cocode/discussions)
- Read the [documentation](docs/)
- Contact maintainers via issues

## Recognition

Contributors are recognized in:
- [Contributors list](https://github.com/dvelop42/cocode/graphs/contributors)
- Release notes
- Project README (significant contributions)

Thank you for contributing to cocode! 🎉