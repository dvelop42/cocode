# Cocode Development Setup

This guide helps you set up a reliable local environment to develop, test, and debug `cocode`.

## Prerequisites
- Python 3.10+ (3.10–3.12 supported)
- Git and GitHub CLI (`gh`) for issue workflows
- Optional: `uv` for faster installs, otherwise use `pip`

Verify tools:

```bash
python --version
git --version
gh --version
```

Authenticate GitHub CLI if you haven’t:

```bash
gh auth login
```

## Project Checkout
```bash
git clone https://github.com/dvelop42/cocode.git
cd cocode
```

## Virtual Environment
Create a local `.venv` in the repo root (recommended for editor integration):

```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
```

## Install Dependencies (dev)
Using pip:

```bash
python -m pip install -e .[dev]
```

Using uv (optional):

```bash
uv pip install -e .[dev]
```

## Pre-commit Hooks
This repo includes `.pre-commit-config.yaml` to enforce formatting and linting before commits.

```bash
pre-commit install            # Enable hooks on commit
pre-commit run --all-files    # Run hooks across the codebase
```

## Editor / IDE Setup
- VSCode: open the repo folder. If you use the provided `.vscode/settings.json`, VSCode will:
  - Use `.venv` interpreter
  - Format with Black on save
  - Lint/fix with Ruff on save and organize imports
  - Enable Pytest discovery

- PyCharm:
  - Set Project Interpreter to the repo’s `.venv`
  - Enable Black and Ruff integrations (via plugins or external tools)
  - Mark `tests/` as test sources for discovery

## Common Tasks
Use the Makefile (optional) or run commands directly.

With Makefile:

```bash
make install          # Install dev deps
make lint             # Ruff lint
make format           # Black format
make typecheck        # MyPy type checks
make test             # Pytest with coverage
make check            # Lint + typecheck + tests
make run ARGS="--help"   # Run CLI (pass args via ARGS)
make doctor           # Environment checks (CLI command placeholder)
make tui              # Launch the Textual TUI (dev harness)
make clean            # Remove caches/artifacts
```

Direct commands:

```bash
python -m cocode --help
pytest
ruff check .
black .
mypy .
```

## Environment Variables
The app loads environment variables via `python-dotenv` if a `.env` file exists. For local experiments, create `.env` and add keys as needed (no secrets in VCS).

## Debugging the TUI
The TUI is implemented with Textual. During development you can launch the app class directly:

```bash
python -c "from cocode.tui.app import CocodeApp; CocodeApp().run()"
```

Tips:
- Increase verbosity of your logs via the CLI global flag: `python -m cocode -l DEBUG --help`
- Textual can output rich logs to the terminal; instrument using `rich`/`logging` where helpful.

## Running the CLI
The CLI provides `init`, `run`, `doctor`, and `clean` subcommands and a global `--log-level` option.

Examples:

```bash
python -m cocode --help
python -m cocode init --help
python -m cocode run --help
```

Note: Some commands are placeholders today; tests assert command registration and help output.

## Testing
Run the full suite with coverage:

```bash
pytest
open htmlcov/index.html  # macOS; view coverage report
```

Quick filters:

```bash
pytest -k cli -q
pytest tests/unit/test_cli.py::test_cli_help -q
```

## Code Style
- Formatting: Black (line length 100)
- Linting: Ruff (pycodestyle/pyflakes/isort/bugbear)
- Types: MyPy (strict-ish settings)

These are configured in `pyproject.toml` and run by pre-commit hooks.

## Troubleshooting
- Ensure you’re using the project `.venv` in your editor and terminal
- If VSCode can’t find the interpreter, select `${workspaceFolder}/.venv/bin/python`
- Clear caches if behavior is odd: `make clean` then reinstall
