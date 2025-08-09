# Makefile for cocode development

.PHONY: help install test lint format type-check ci clean dev fix

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

install: ## Install the project in development mode
	uv venv
	uv pip install -e .[dev]

test: ## Run tests with coverage
	uv run pytest

lint: ## Run ruff linter
	uv run ruff check .

format: ## Format code with black
	uv run black .

format-check: ## Check code formatting with black
	uv run black --check .

type-check: ## Run mypy type checker
	uv run mypy .

ci: ## Run all CI checks locally (lint, format, type-check, test)
	@echo "🔍 Running all CI checks..."
	@$(MAKE) lint
	@$(MAKE) format-check
	@$(MAKE) type-check
	@$(MAKE) test
	@echo "✅ All CI checks passed!"

fix: ## Auto-fix linting and formatting issues
	uv run ruff check --fix .
	uv run black .

clean: ## Clean up generated files and caches
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "coverage.xml" -delete
	find . -type f -name ".coverage" -delete

dev: install ## Set up development environment
	@echo "✅ Development environment ready!"
	@echo ""
	@echo "Run 'make test' to run tests"
	@echo "Run 'make ci' to run all CI checks"
	@echo "Run 'make help' to see all available commands"