"""Integration tests for arborist CLI."""

import os
import tempfile
from pathlib import Path

import pytest
from git import Repo
from typer.testing import CliRunner

from arborist.cli import app
from arborist.git import GitRepo


@pytest.fixture
def test_repo():
    """Create a test repository with various branch scenarios."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Initialize repo with main as default branch
        repo_path = Path(temp_dir)
        os.environ["GIT_CONFIG_GLOBAL"] = str(repo_path / ".gitconfig")
        repo = Repo.init(repo_path)
        with repo.config_writer() as config:
            config.set_value("init", "defaultBranch", "main")
            config.set_value("user", "name", "Test User")
            config.set_value("user", "email", "test@example.com")

        # Change to repo directory
        old_cwd = os.getcwd()
        os.chdir(repo_path)

        try:
            # Create initial commit
            readme = Path("README.md")
            readme.write_text("# Test Repository")
            repo.index.add(["README.md"])
            repo.index.commit("Initial commit")

            # Rename master to main
            master = repo.heads.master
            master.rename("main")

            # Create test branches
            scenarios = {
                "feature/merged": True,  # Should be merged
                "feature/unmerged": False,  # Should not be merged
                "release/1.0": True,  # Protected branch
                "feature/gone": True,  # Will be deleted remotely
                "feature/conflict": False,  # Branch with merge conflict
                "feature/#123": True,  # Branch with special chars
                "hotfix/1.0/fix": True,  # Nested branch for glob testing
            }

            # Create a file that will cause conflicts
            conflict_file = Path("conflict.txt")
            conflict_file.write_text("main content")
            repo.index.add(["conflict.txt"])
            repo.index.commit("Add conflict file in main")

            # Create feature/conflict branch with conflicting changes
            repo.create_head("feature/conflict").checkout()
            conflict_file.write_text("branch content")
            repo.index.add(["conflict.txt"])
            repo.index.commit("Change content in branch")

            # Make another change in main to ensure conflict
            repo.heads.main.checkout()
            conflict_file.write_text("updated main content")
            repo.index.add(["conflict.txt"])
            repo.index.commit("Update content in main")

            # Create and set up other branches
            for branch_name, should_merge in scenarios.items():
                if branch_name == "feature/conflict":
                    continue  # Already created

                # Create and checkout branch
                branch = repo.create_head(branch_name)
                branch.checkout()

                # Add a test file
                test_file = Path(f"{branch_name.replace('/', '_')}.txt")
                test_file.write_text(f"Test content for {branch_name}")
                repo.index.add([str(test_file)])
                repo.index.commit(f"Add test file for {branch_name}")

                # Add extra commits to some branches
                if branch_name == "feature/#123":
                    test_file.write_text(f"Updated content for {branch_name}")
                    repo.index.add([str(test_file)])
                    repo.index.commit("Update test file")

                # Try to merge if needed
                if should_merge:
                    repo.heads.main.checkout()
                    repo.git.merge(branch_name, no_ff=True)

            # Return to main
            repo.heads.main.checkout()

            yield repo_path

        finally:
            # Restore working directory
            os.chdir(old_cwd)


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


def test_list_command(test_repo, runner):
    """Test the list command."""
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "feature/merged" in result.stdout
    assert "feature/unmerged" in result.stdout
    assert "release/1.0" in result.stdout


def test_clean_merged_branch(test_repo, runner):
    """Test cleaning a merged branch."""
    result = runner.invoke(app, ["clean", "--no-interactive"])
    assert result.exit_code == 0
    assert "feature/merged" in result.stdout
    assert "Successfully deleted" in result.stdout

    # Verify branch is gone
    repo = GitRepo(test_repo)
    branches = repo.get_branch_status()
    assert "feature/merged" not in branches


def test_clean_with_protection(test_repo, runner):
    """Test branch protection."""
    result = runner.invoke(app, ["clean", "--protect", "release/*", "--no-interactive"])
    assert result.exit_code == 0
    assert "release/1.0" not in result.stdout

    # Verify protected branch still exists
    repo = GitRepo(test_repo)
    branches = repo.get_branch_status()
    assert "release/1.0" in branches


def test_clean_dry_run(test_repo, runner):
    """Test dry run mode."""
    result = runner.invoke(app, ["clean", "--dry-run"])
    assert result.exit_code == 0
    assert "Would delete branch" in result.stdout

    # Verify no branches were actually deleted
    repo = GitRepo(test_repo)
    branches = repo.get_branch_status()
    assert "feature/merged" in branches


def test_clean_interactive_cancel(test_repo, runner):
    """Test canceling in interactive mode."""
    result = runner.invoke(app, ["clean"], input="n\n")
    assert result.exit_code == 0
    assert "Operation cancelled" in result.stdout

    # Verify no branches were deleted
    repo = GitRepo(test_repo)
    branches = repo.get_branch_status()
    assert "feature/merged" in branches


def test_invalid_repo(runner):
    """Test handling of invalid repository path."""
    with tempfile.TemporaryDirectory() as temp_dir:
        result = runner.invoke(app, ["list", "--path", temp_dir])
        assert result.exit_code == 1
        assert "Failed to open repository" in result.stdout


def test_multiple_protection_patterns(test_repo, runner):
    """Test multiple branch protection patterns."""
    result = runner.invoke(app, ["clean", "--protect", "release/*,hotfix/*", "--no-interactive"])
    assert result.exit_code == 0

    # Verify protected branches still exist
    repo = GitRepo(test_repo)
    branches = repo.get_branch_status()
    assert "release/1.0" in branches
    assert "hotfix/1.0/fix" in branches


def test_force_delete_unmerged(test_repo, runner):
    """Test force deletion of unmerged branches."""
    result = runner.invoke(app, ["clean", "--force", "--no-interactive"])
    assert result.exit_code == 0
    assert "feature/unmerged" in result.stdout
    assert "Successfully deleted" in result.stdout

    # Verify branch is gone
    repo = GitRepo(test_repo)
    branches = repo.get_branch_status()
    assert "feature/unmerged" not in branches


def test_special_chars_branch(test_repo, runner):
    """Test handling of branches with special characters."""
    result = runner.invoke(app, ["clean", "--no-interactive"])
    assert result.exit_code == 0
    assert "feature/#123" in result.stdout
    assert "Successfully deleted" in result.stdout

    # Verify branch is gone
    repo = GitRepo(test_repo)
    branches = repo.get_branch_status()
    assert "feature/#123" not in branches


def test_conflict_branch_protection(test_repo, runner):
    """Test that conflicted branches are not deleted without force."""
    result = runner.invoke(app, ["clean", "--no-interactive"])
    assert result.exit_code == 0
    assert "feature/conflict" not in result.stdout

    # Verify branch still exists and is marked as unmerged
    repo = GitRepo(test_repo)
    branches = repo.get_branch_status()
    assert "feature/conflict" in branches
    assert branches["feature/conflict"].value == "unmerged"
