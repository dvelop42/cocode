#!/bin/bash
# Run all CI checks locally before pushing
# This mimics the GitHub Actions CI pipeline

set -e  # Exit on any error

echo "🔍 Running CI checks locally..."
echo "================================"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed. Please install it first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    uv venv
fi

# Install dependencies
echo "📦 Installing dependencies..."
uv pip install -e .[dev]

# Run ruff linting
echo ""
echo "🔍 Running ruff linter..."
if uv run ruff check .; then
    echo "✅ Ruff check passed"
else
    echo "❌ Ruff check failed"
    exit 1
fi

# Run black formatting check
echo ""
echo "🎨 Checking black formatting..."
if uv run black --check .; then
    echo "✅ Black formatting check passed"
else
    echo "❌ Black formatting check failed"
    echo "💡 Run 'uv run black .' to fix formatting"
    exit 1
fi

# Run mypy type checking
echo ""
echo "🔍 Running mypy type checker..."
if uv run mypy .; then
    echo "✅ Mypy check passed"
else
    echo "❌ Mypy check failed"
    exit 1
fi

# Run pytest with coverage
echo ""
echo "🧪 Running tests with coverage..."
if uv run pytest; then
    echo "✅ All tests passed"
else
    echo "❌ Tests failed"
    exit 1
fi

echo ""
echo "================================"
echo "✅ All CI checks passed! Safe to push."
echo ""
echo "To push your changes, run:"
echo "  git push"