PYTHON := $(shell command -v python3 2>/dev/null || command -v python)
PIP := $(PYTHON) -m pip

.PHONY: help install venv pre-commit test lint format typecheck check run tui doctor clean

help:
	@echo "Available targets:"
	@echo "  install      Install dev dependencies (editable)"
	@echo "  venv         Create a local .venv"
	@echo "  pre-commit   Install and run pre-commit hooks"
	@echo "  lint         Run Ruff lint checks"
	@echo "  format       Run Black formatting"
	@echo "  typecheck    Run MyPy type checks"
	@echo "  test         Run pytest with coverage"
	@echo "  check        Lint + typecheck + tests"
	@echo "  run          Run CLI (pass args via ARGS='...')"
	@echo "  tui          Launch Textual TUI"
	@echo "  doctor       Run environment checks"
	@echo "  clean        Remove caches and build artifacts"

venv:
	$(PYTHON) -m venv .venv
	@echo "Activate with: source .venv/bin/activate"

install:
	$(PIP) install --upgrade pip
	$(PIP) install -e .[dev]

pre-commit:
	pre-commit install
	pre-commit run --all-files

lint:
	ruff check .

format:
	black .

typecheck:
	mypy .

test:
	pytest

check: lint typecheck test

run:
	$(PYTHON) -m cocode $(ARGS)

tui:
	$(PYTHON) -c "from cocode.tui.app import CocodeApp; CocodeApp().run()"

doctor:
	$(PYTHON) -m cocode doctor

clean:
	rm -rf .mypy_cache .ruff_cache .pytest_cache htmlcov build dist
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
