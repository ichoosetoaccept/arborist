"""Integration tests for install-dev.sh script."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from git import Repo


@pytest.fixture
def temp_workspace() -> Generator[Path, None, None]:
    """Create a temporary workspace with the essential project files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Initialize git repository
        repo = Repo.init(temp_path)

        # Copy essential files to temp directory
        project_root = Path(__file__).parent.parent
        files_to_copy = [
            "pyproject.toml",
            "scripts/install-dev.sh",
            ".pre-commit-config.yaml",
        ]

        for file in files_to_copy:
            src = project_root / file
            dst = temp_path / file
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

        # Add files to git
        repo.index.add([f for f in files_to_copy if (temp_path / f).exists()])
        repo.index.commit("Initial commit")

        # Store original directory
        original_dir = os.getcwd()

        # Change to temp directory
        os.chdir(temp_path)

        yield temp_path

        # Restore original directory
        os.chdir(original_dir)


def test_install_dev_script_success(temp_workspace: Path) -> None:
    """Test successful execution of install-dev.sh."""
    script_path = temp_workspace / "scripts" / "install-dev.sh"

    # Make sure script is executable
    script_path.chmod(0o755)

    # Run the script
    result = subprocess.run(
        [str(script_path)],
        capture_output=True,
        text=True,
        env={**os.environ, "TERM": "xterm-256color"},
    )

    # Check if script executed successfully
    assert result.returncode == 0

    # Check for expected output messages
    assert "📦 Installing dependencies..." in result.stdout
    assert "🔧 Setting up pre-commit hooks..." in result.stdout

    # Verify that pre-commit hooks were installed
    hooks_dir = temp_workspace / ".git" / "hooks"
    assert (hooks_dir / "pre-commit").exists()
    assert (hooks_dir / "commit-msg").exists()
