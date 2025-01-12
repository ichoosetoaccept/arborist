# Arborist

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/ichoosetoaccept/arborist/actions/workflows/test.yml/badge.svg)](https://github.com/ichoosetoaccept/arborist/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/ichoosetoaccept/arborist/branch/main/graph/badge.svg)](https://codecov.io/gh/ichoosetoaccept/arborist)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-✓-green.svg)](https://conventionalcommits.org)
[![SemVer](https://img.shields.io/badge/SemVer-✓-blue.svg)](https://semver.org/)
[![CodeRabbit Reviews](https://img.shields.io/coderabbit/pull-request-reviews/ichoosetoaccept/arborist?logo=coderabbit&style=flat-square)](https://coderabbit.ai)

## Platform Support

[![macOS](https://img.shields.io/badge/macOS-tested-success)](https://github.com/ichoosetoaccept/arborist/actions/workflows/test.yml)
[![Linux](https://img.shields.io/badge/Linux-in%20progress-yellow)](https://github.com/ichoosetoaccept/arborist/actions/workflows/test.yml)
[![Windows](https://img.shields.io/badge/Windows-untested-inactive)](https://github.com/ichoosetoaccept/arborist/issues)

A CLI tool to clean up Git branches. Like a skilled arborist pruning trees, this tool helps you maintain a clean Git branch structure by removing merged and stale branches while protecting important ones.

## Features

- 🧼 Safely Removes merged branches
- 🔍 Detects and removes branches with gone remotes
- 🗑️ Performs garbage collection and pruning
- 🛡️ Protects main branch
- ⚡ Optimizes repository performance
- 🔄 Automatic remote pruning

## Installation

### Development Installation

To install the package for local development:

```bash
# Clone the repository
git clone https://github.com/ichoosetoaccept/arborist.git
cd arborist

# Install dependencies and the package in development mode
uv sync

# Install the package as a tool to make `arb` available globally
uv tool install -e .
```

After installation:
- The `arb` command will be available globally (you may need to restart your shell)
- Changes you make to the code will be reflected immediately
- Run tests with: `uv run pytest -v`
- No virtual environment activation is needed as uv manages this automatically

## Usage

```bash
# Show help
arb --help

# List all branches with their cleanup status
arb list

# Clean up merged and gone branches
arb clean
```

## How It Works

1. **List Branches**: Shows all branches with their cleanup status
2. **Clean Branches**: Removes local branches that meet cleanup criteria

## Safety Features

- Never deletes protected branches (main by default)
- Only deletes branches that are fully merged or have gone remotes

## Recovery

If you accidentally delete a branch, you can recover it within Git's reflog expiry period
(default: 90 days):

```bash
# See the reflog entries
git reflog

# Recover a branch (replace SHA with the commit hash from reflog)
git branch <branch-name> <SHA>
```

## Configuration

You can configure default behavior by creating a `.arboristrc` file in your home directory:

```json
{
  "protectedBranches": ["main", "develop"],
  "interactive": false,
  "skipGc": false,
  "reflogExpiry": "90.days"
}
```

## Development

### Requirements

- Python 3.12 or higher
- uv package manager
- Git 2.28 or higher
- Docker (optional, for cross-platform testing)

### Development Setup

We provide a convenient setup script that automates the development environment setup:

```bash
./scripts/install-dev.sh
```

This script will:
1. Check for uv installation
2. Install project dependencies
3. Set up pre-commit hooks for:
   - Code formatting and linting
   - Commit message validation
4. Run initial pre-commit checks

After running the script, you'll be ready to create branches and start contributing following our branch naming convention:
- `feature/your-feature`
- `bugfix/your-bugfix`
- `hotfix/your-hotfix`
- `release/version`
- `ci/your-ci-change`

### Package Management with uv

This project uses [uv](https://github.com/astral/uv) for Python package management. uv is a modern Python package manager focused on speed and reliability.

To install uv:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Key uv commands used in this project:
```bash
# Install dependencies
uv sync

# Run a command (e.g., pytest, pre-commit)
uv run pytest
uv run pre-commit run --all-files

# Install the package as a development tool
uv tool install -e .
```

Note: Never use `uv pip` as it's a legacy command. Use the modern uv commands instead.

### Platform Support

The project is actively tested on:
- macOS (primary development platform)
- Linux (testing in progress via Docker and CI)

Windows support is currently untested. Contributions to add Windows testing and support are welcome!

Note: Linux support is being actively developed and tested. While basic functionality works, there might be platform-specific issues that we're still discovering and fixing. Please report any Linux-specific issues you encounter!

### Running Tests

```bash
# Run tests locally
uv run pytest -v -s

# Run tests on both macOS and Linux (via Docker)
./test-all.sh

# Run linting
uv run ruff check .

# Run formatting
uv run ruff format .
```

Test coverage includes:
- CLI functionality and options
- Git operations and error handling
- Progress bars and visual feedback
- Configuration management
- Cross-platform compatibility (macOS and Linux)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Pull Request Process

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Ensure tests pass (`./test-all.sh`)
5. Commit your changes using conventional commits
6. Push to your fork
7. Open a Pull Request

### Commit Message Format

We use [Conventional Commits](https://www.conventionalcommits.org/) format. Each commit message should follow this format:

```
<type>(<scope>): <description>

[optional body]
```

Where:
- `type` is one of:
  - `feat`: A new feature
  - `fix`: A bug fix
  - `docs`: Documentation only changes
  - `style`: Changes that don't affect the code's meaning
  - `refactor`: Code changes that neither fix a bug nor add a feature
  - `perf`: Performance improvements
  - `test`: Adding or fixing tests
  - `chore`: Changes to build process or auxiliary tools
- `scope` is optional and indicates the area of change
- `description` is a short description of the change

Example:
```
feat(cli): add support for remote branch cleanup

Add functionality to clean up merged remote branches.
This helps keep the remote repository clean by removing
branches that have been merged into the main branch.
```

### Release Process

Releases are automated through GitHub Actions using semantic versioning rules. The version number is automatically determined based on the changes in each Pull Request:

1. MAJOR version (X.0.0) is bumped when:
   - PR has the `breaking-change` label
   - Changes include backwards-incompatible updates

2. MINOR version (0.X.0) is bumped when:
   - PR has the `enhancement` or `feature` label
   - New features are added in a backwards-compatible manner

3. PATCH version (0.0.X) is bumped when:
   - PR has `bug`, `bugfix`, or `fix` labels
   - Backwards-compatible bug fixes are made
   - Documentation or maintenance changes are made

The release process is fully automated:

1. Create a Pull Request with your changes
2. Apply appropriate labels to your PR:
   - `enhancement`, `feature`: For new features
   - `bug`, `bugfix`, `fix`: For bug fixes
   - `breaking-change`: For breaking changes
   - `documentation`: For documentation updates
   - `performance`: For performance improvements
   - `maintenance`, `dependencies`: For maintenance work

3. When your PR is merged to main:
   - A new version number is automatically determined
   - A new tag is created and pushed
   - The release workflow creates a GitHub release
   - Release notes are automatically generated based on PR labels

The release notes will be automatically organized into categories based on the labels used in Pull Requests.

## License

MIT License - feel free to use this in your own projects!
