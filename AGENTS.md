# Repository Guidelines

This repository hosts the `cocode` CLI/TUI for orchestrating multiple code agents to fix GitHub issues in parallel. Use the guide below to contribute effectively and consistently.

## Project Structure & Modules
- `src/cocode/`: Application code
  - `cli/`: Typer commands (`init`, `run`, `doctor`, `clean`)
  - `tui/`: Textual app and views
  - `agents/`: Agent base and integrations
  - `git/`, `github/`, `config/`, `utils/`: Services and helpers
- `tests/`: Pytest suite (`tests/unit/test_*.py`)
- `docs/`, `prototypes/`: Documentation and explorations

## Build, Test, and Dev Commands
- Install (dev): `uv pip install -e .[dev]` or `pip install -e .[dev]`
- Run CLI locally: `python -m cocode --help` or `cocode`
- Tests + coverage: `pytest` (writes `htmlcov/` and terminal report)
- Lint: `ruff check .`  |  Format: `black .`
- Type-check: `mypy .`

## Coding Style & Conventions
- Python 3.10+, 4-space indentation, max line length 100.
- Naming: packages/modules `snake_case`, classes `PascalCase`, functions/vars `snake_case`.
- Tools: Black (format), Ruff (lint; pycodestyle/pyflakes/isort/bugbear), MyPy (type checks).
- Keep functions small; prefer explicit returns and typed signatures.

## Testing Guidelines
- Framework: Pytest with `test_*.py` in `tests/` (configured in `pyproject.toml`).
- Aim for meaningful coverage of CLI entry points, services, and error paths.
- Quick examples: `pytest -k cli -q`, `pytest tests/unit/test_cli.py::test_cli_help`.

## Commit & PR Guidelines
- Commit style: Conventional Commits (`feat:`, `fix:`, `docs:`; scopes welcomed, e.g., `feat(cli): ...`).
- Reference issues: “Closes #123” in commits/PRs when applicable.
- PRs: clear description, linked issue, rationale, and screenshots/GIFs for TUI changes; include CLI output for behavior changes.
- Keep diffs focused; update docs or tests alongside code changes.

## Security & Agent Notes
- Do not commit secrets. Use environment variables (loaded via `python-dotenv` if present) and GitHub CLI auth (`gh`).
- When adding agents, implement under `src/cocode/agents/` and follow the environment contract in README. Agents must emit the completion marker “cocode ready for check” in their final commit message.
