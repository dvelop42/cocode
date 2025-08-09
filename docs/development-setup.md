# Development Setup

This guide helps you get a working cocode development environment with linting, type
checking, tests, and editor integration.

## Prerequisites
- Python 3.10+ (`python3 --version`)
- Git 2.30+
- Optional: `uv` for fast installs (https://docs.astral.sh/uv/)
- Optional: GitHub CLI `gh` for GitHub workflows (https://cli.github.com/)

## Clone and Environment
1. Clone the repo:
   - `git clone https://github.com/dvelop42/cocode && cd cocode`
2. Create a virtual environment (choose one):
   - With uv: `uv venv` and `source .venv/bin/activate`
   - With Python: `python -m venv .venv` and `source .venv/bin/activate`
     - Windows (PowerShell): `.venv\Scripts\Activate.ps1`
3. Install dev dependencies:
   - With uv: `uv pip install -e .[dev]`
   - With pip: `pip install -e .[dev]`

Tip: You can also use the Makefile shortcuts once deps are installed, e.g. `make test`.

## Editor / IDE Setup

### VSCode
This repo includes workspace settings at `.vscode/settings.json`.
Install these extensions for best experience:
- Python (ms-python.python)
- Ruff (charliermarsh.ruff)
- Black Formatter (ms-python.black-formatter) or rely on Ruff’s formatting if preferred
- MyPy Type Checker (matangover.mypy) optional

VSCode will discover the `.venv` automatically when you open the folder.

### PyCharm
- Set the project interpreter to the local `.venv`.
- Enable Black as external formatter (or use built-in reformat to 100 cols).
- Install and enable the Ruff plugin.
- Add a MyPy configuration pointing to the repo root (PyCharm Professional recommended).

## Pre-commit Hooks
Enable consistent formatting and linting before commits:
- `pre-commit install`
- Run on all files: `pre-commit run --all-files`

## Common Tasks
Makefile targets are provided for convenience (see `Makefile`):
- `make install` — Install project + dev deps (uses uv if available, falls back to pip)
- `make lint` — Ruff lint
- `make format` — Black format
- `make typecheck` — MyPy type checks
- `make test` — Run pytest with coverage (HTML in `htmlcov/`)
- `make test-quick` — Quick pytest run
- `make precommit-install` — Install pre-commit hooks
- `make precommit-run` — Run pre-commit on all files
- `make tui-demo` — Run the Textual prototype

## Running the CLI Locally
- `python -m cocode --help`
- `cocode --help` (after `pipx install` or when installed as an editable script)

Current subcommands exist but are not fully implemented yet:
- `init`, `run`, `doctor`, `clean`

## Running Tests
- Full test suite: `pytest`
- Quick filter: `pytest -k cli -q`
- Coverage HTML report: open `htmlcov/index.html`

## Debugging the TUI
There is a Textual prototype at `prototypes/textual_prototype/textual_demo.py`:
- Run: `python prototypes/textual_prototype/textual_demo.py`
- Tips:
  - Resize the terminal to observe layout changes
  - Use the logs panel to watch streaming output

When the main TUI is implemented under `src/cocode/tui/`, you’ll be able to run it similarly:
- `python -m cocode run <issue>` (once implemented)

## Troubleshooting
- If VSCode doesn’t detect the venv, select the interpreter manually (`.venv/bin/python`).
- If `ruff`, `mypy`, or `pytest` are missing, ensure you installed dev deps: `pip install -e .[dev]`.
- If `uv` isn’t installed, the Makefile falls back to `pip`.

