"""Integration tests for arborist CLI.

Tests various branch cleanup scenarios.
Includes tests for branch listing, cleaning, and protection.
"""

import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from arborist.cli import app
from arborist.git import GitRepo


@pytest.fixture
def test_repo(test_env: tuple[Path, Path]) -> Path:
    """Create a test repository with various branch scenarios."""
    local_path, _ = test_env
    return local_path


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


def test_list_command(test_repo: Path, runner: CliRunner) -> None:
    """Test the list command."""
    result = runner.invoke(app, ["list", "--path", str(test_repo)])
    assert result.exit_code == 0
    assert "feature/merged" in result.stdout
    assert "feature/test" in result.stdout
    assert "feature/current" in result.stdout
    assert "✓" in result.stdout
    assert "✋" in result.stdout

    # Verify branch names are on single lines (no line breaks in branch names)
    lines = result.stdout.splitlines()
    for line in lines:
        # Only check table rows that contain branch names (exclude summary sections)
        if "│" in line:  # This is a table row
            if "feature/" in line and not line.startswith("│ origin/"):  # Local branch
                assert line.count("feature/") == 1  # Branch name should be on a single line
            elif "origin/feature/" in line:  # Remote branch
                assert line.count("origin/feature/") == 1  # Branch name should be on a single line


def test_clean_merged_branch(test_repo: Path, runner: CliRunner) -> None:
    """Test cleaning a merged branch."""
    # First verify the repo state
    repo = GitRepo(test_repo)
    print("\nDEBUG: Initial repo state:")
    print(f"DEBUG: Current branch: {repo.get_current_branch_name()}")
    print("DEBUG: Branch status:")
    for branch, status in repo.get_branch_status().items():
        print(f"DEBUG: {branch}: {status.value}")

    # Run the clean command with the correct repo path
    result = runner.invoke(app, ["clean", "--no-interactive", "--path", str(test_repo)])
    print("\nDEBUG: Clean command output:")
    print(result.stdout)

    assert result.exit_code == 0
    assert "feature/merged" in result.stdout
    assert "Successfully deleted" in result.stdout

    # Verify branch is gone
    repo = GitRepo(test_repo)
    branches = repo.get_branch_status()
    assert "feature/merged" not in branches


def test_clean_with_protection(test_repo: Path, runner: CliRunner) -> None:
    """Test branch protection."""
    # Get initial state
    repo = GitRepo(test_repo)
    initial_branches = repo.get_branch_status()

    # Run the clean command with the correct repo path
    result = runner.invoke(app, ["clean", "--protect", "feature/*", "--no-interactive", "--path", str(test_repo)])

    assert result.exit_code == 0

    # Verify all feature branches (both local and remote) still exist
    final_branches = repo.get_branch_status()
    for branch in initial_branches:
        if "feature/" in branch:  # This covers both local and remote feature branches
            assert branch in final_branches, f"Protected branch {branch} was deleted"


def test_clean_dry_run(test_repo: Path, runner: CliRunner) -> None:
    """Test dry run mode."""
    # First verify the repo state
    repo = GitRepo(test_repo)
    print("\nDEBUG: Initial repo state:")
    print(f"DEBUG: Current branch: {repo.get_current_branch_name()}")
    print("DEBUG: Branch status:")
    for branch, status in repo.get_branch_status().items():
        print(f"DEBUG: {branch}: {status.value}")

    # Run the clean command with the correct repo path
    result = runner.invoke(app, ["clean", "--dry-run", "--path", str(test_repo)])
    print("\nDEBUG: Clean command output:")
    print(result.stdout)

    assert result.exit_code == 0
    assert "Would delete branch" in result.stdout

    # Verify no branches were actually deleted
    repo = GitRepo(test_repo)
    branches = repo.get_branch_status()
    assert "feature/merged" in branches


def test_clean_interactive_cancel(test_repo: Path, runner: CliRunner) -> None:
    """Test canceling in interactive mode."""
    # First verify the repo state
    repo = GitRepo(test_repo)

    # Run the clean command with the correct repo path
    result = runner.invoke(app, ["clean", "--path", str(test_repo)], input="n\n")

    assert result.exit_code == 0
    # Verify no branches were deleted
    repo = GitRepo(test_repo)
    branches = repo.get_branch_status()
    assert "feature/merged" in branches  # Branch should still exist


def test_invalid_repo(runner: CliRunner) -> None:
    """Test handling of invalid repository path."""
    with tempfile.TemporaryDirectory() as temp_dir:
        result = runner.invoke(app, ["list", "--path", temp_dir])
        assert result.exit_code == 1
        assert "Failed to open repository" in result.stdout


def test_multiple_protection_patterns(test_repo: Path, runner: CliRunner) -> None:
    """Test multiple branch protection patterns."""
    result = runner.invoke(app, ["clean", "--protect", "feature/*,hotfix/*", "--no-interactive"])
    assert result.exit_code == 0

    # Verify protected branches still exist
    repo = GitRepo(test_repo)
    branches = repo.get_branch_status()
    assert "feature/merged" in branches


def test_force_delete_unmerged(test_repo: Path, runner: CliRunner) -> None:
    """Test force deletion of unmerged branches."""
    # First verify the repo state
    repo = GitRepo(test_repo)
    print("\nDEBUG: Initial repo state:")
    print(f"DEBUG: Current branch: {repo.get_current_branch_name()}")
    print("DEBUG: Branch status:")
    for branch, status in repo.get_branch_status().items():
        print(f"DEBUG: {branch}: {status.value}")

    # Run the clean command with the correct repo path
    result = runner.invoke(app, ["clean", "--force", "--no-interactive", "--path", str(test_repo)])
    print("\nDEBUG: Clean command output:")
    print(result.stdout)

    assert result.exit_code == 0
    assert "feature/test" in result.stdout
    assert "Successfully deleted" in result.stdout

    # Verify branch is gone
    repo = GitRepo(test_repo)
    branches = repo.get_branch_status()
    assert "feature/test" not in branches


def test_cannot_delete_main_branch_with_force(test_repo: Path, runner: CliRunner) -> None:
    """Test that main branch cannot be deleted even with force."""
    # First verify the repo state
    repo = GitRepo(test_repo)
    print("\nDEBUG: Initial repo state:")
    print(f"DEBUG: Current branch: {repo.get_current_branch_name()}")
    print("DEBUG: Branch status:")
    for branch, status in repo.get_branch_status().items():
        print(f"DEBUG: {branch}: {status.value}")

    # Try to force delete main branch
    result = runner.invoke(app, ["clean", "--force", "--no-interactive", "--protect", "", "--path", str(test_repo)])
    print("\nDEBUG: Clean command output:")
    print(result.stdout)

    assert result.exit_code == 0

    # Verify main branch still exists
    repo = GitRepo(test_repo)
    branches = repo.get_branch_status()
    assert "main" in branches
