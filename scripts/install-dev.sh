#!/usr/bin/env bash
set -euo pipefail

echo "🔍 Checking for uv installation..."
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed. Please install it first:"
    echo "curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "📦 Installing dependencies..."
uv sync

echo "🔧 Setting up pre-commit hooks..."
# Install base pre-commit hooks
uv run pre-commit install

# Install commit-msg hook for gitlint
uv run pre-commit install --hook-type commit-msg

echo "✨ Running initial pre-commit check..."
uv run pre-commit run --all-files || {
    echo "⚠️  Some pre-commit checks failed. This is normal for the first run!"
    echo "   The hooks have auto-fixed some issues."
    echo "   Please stage the modified files and commit again."
}

echo "
✅ Development environment setup complete!

Next steps:
1. Create a new branch following our naming convention:
   - feature/your-feature
   - bugfix/your-bugfix
   - hotfix/your-hotfix
   - release/version
   - ci/your-ci-change

2. Make your changes and commit. The pre-commit hooks will:
   - Run tests
   - Check code formatting
   - Validate commit messages
   - Ensure branch naming conventions
"
