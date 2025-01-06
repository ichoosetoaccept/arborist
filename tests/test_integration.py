"""Integration tests for arborist CLI.

Tests various branch cleanup scenarios.
Includes tests for branch listing, cleaning, and protection.
"""

import tempfile
from pathlib import Path

import pytest
from git import Actor, Repo
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
    assert "✅" in result.stdout
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


def test_list_command_silent_mode(test_repo: Path, runner: CliRunner) -> None:
    """Test that list command in silent mode produces no output."""
    result = runner.invoke(app, ["list", "--path", str(test_repo), "--silent"])
    assert result.exit_code == 0
    assert not result.stdout  # Silent mode should produce no output


def test_fetch_before_list(test_repo: Path, runner: CliRunner) -> None:
    """Test that list command fetches from remotes before displaying branches."""
    repo = GitRepo(test_repo)
    test_repo_obj = repo.repo

    # Create and push a test branch in the remote
    remote_repo = test_repo_obj.remote().repo
    remote_repo.git.branch("test/remote-fetch")

    # Run list command which should fetch and show the new remote branch
    result = runner.invoke(app, ["list", "--path", str(test_repo)])
    assert result.exit_code == 0
    assert "test/remote-fetch" in result.stdout


def test_fetch_before_clean(test_repo: Path, runner: CliRunner) -> None:
    """Test that clean command fetches from remotes before cleaning."""
    repo = GitRepo(test_repo)
    test_repo_obj = repo.repo

    # Make sure we're on main first
    test_repo_obj.git.checkout("main")

    # Create and push a test branch
    test_repo_obj.git.checkout("-b", "test/to-delete")
    test_repo_obj.git.push("origin", "test/to-delete")

    # Switch back to main before deleting
    test_repo_obj.git.checkout("main")

    # Delete the branch on remote directly
    remote_repo = test_repo_obj.remote().repo
    remote_repo.git.branch("-D", "test/to-delete")

    # Run clean command which should fetch and detect the gone branch
    result = runner.invoke(app, ["clean", "--path", str(test_repo), "--no-interactive"])
    assert result.exit_code == 0
    assert "test/to-delete" in result.stdout
    assert "gone" in result.stdout.lower()


def test_clean_uses_list_state(test_repo: Path, runner: CliRunner) -> None:
    """Test that clean command uses list command's state."""
    # First run list to get initial state
    list_result = runner.invoke(app, ["list", "--path", str(test_repo)])
    assert list_result.exit_code == 0

    # Run clean command with no-interactive mode
    clean_result = runner.invoke(app, ["clean", "--path", str(test_repo), "--no-interactive"])
    assert clean_result.exit_code == 0

    # Extract cleanable branches from list output
    list_cleanable = []
    for line in list_result.stdout.splitlines():
        if "✅" in line:
            # Extract branch name from the line (between first two │ characters)
            parts = line.split("│")
            if len(parts) >= 2:
                branch = parts[1].strip()
                # Remove (current) indicator if present
                branch = branch.replace(" (current)", "")
                list_cleanable.append(branch)

    # Extract branches that were deleted from clean output
    clean_branches = []
    for line in clean_result.stdout.splitlines():
        if "Successfully deleted" in line:
            # The next lines will contain the branch names
            continue
        if "│" in line:  # Table row
            parts = line.split("│")
            if len(parts) >= 2:
                branch = parts[1].strip()
                if branch and not branch == "Branch":  # Skip header row
                    clean_branches.append(branch)

    # Sort and deduplicate the lists
    list_cleanable = sorted(set(list_cleanable))
    clean_branches = sorted(set(clean_branches))

    # Verify both commands identified the same branches
    assert list_cleanable == clean_branches

    # Verify repo state
    repo = GitRepo(test_repo)
    branches = repo.get_branch_status()
    assert "main" in branches


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


def test_clean_preview(test_repo: Path, runner: CliRunner) -> None:
    """Test preview mode with confirmation cancelled."""
    # First verify the repo state
    repo = GitRepo(test_repo)
    print("\nDEBUG: Initial repo state:")
    print(f"DEBUG: Current branch: {repo.get_current_branch_name()}")
    print("DEBUG: Branch status:")
    for branch, status in repo.get_branch_status().items():
        print(f"DEBUG: {branch}: {status.value}")

    # Run the clean command with interactive mode and simulate 'n' input
    result = runner.invoke(app, ["clean", "--path", str(test_repo)], input="n\n")
    print("\nDEBUG: Clean command output:")
    print(result.stdout)

    assert result.exit_code == 0
    assert "Operation cancelled" in result.stdout


def test_invalid_repo(runner: CliRunner) -> None:
    """Test handling of invalid repository path."""
    with tempfile.TemporaryDirectory() as temp_dir:
        result = runner.invoke(app, ["list", "--path", temp_dir])
        assert result.exit_code == 1
        assert "Failed to open repository" in result.stdout


def test_multiple_protection_patterns(test_repo: Path, runner: CliRunner) -> None:
    """Test multiple branch protection patterns."""
    # Debug output
    repo = GitRepo(test_repo)
    print("\nDEBUG: Initial repo state:")
    print(f"DEBUG: Git version: {repo.repo.git.version()}")
    print("DEBUG: Git config:")
    config = repo.repo.config_reader()
    for section in config.sections():
        for key, value in config.items(section):
            print(f"DEBUG: {section}.{key}: {value}")
    print("\nDEBUG: Branch status:")
    for branch, status in repo.get_branch_status().items():
        print(f"DEBUG: {branch}: {status.value}")

    result = runner.invoke(app, ["clean", "--protect", "feature/*,hotfix/*", "--no-interactive"])
    print("\nDEBUG: Clean command output:")
    print(result.stdout)

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


def test_list_shows_latest_remote_status(test_repo: Path, runner: CliRunner) -> None:
    """Test that list command shows latest remote branch status after remote changes."""
    repo = GitRepo(test_repo)
    test_repo_obj = repo.repo

    # Make sure we're on main first
    test_repo_obj.git.checkout("main")

    # Create and push a test branch
    test_repo_obj.git.checkout("-b", "test/remote-status")
    test_file = Path(test_repo) / "test_remote_status.txt"
    test_file.write_text("initial content")
    test_repo_obj.index.add(["test_remote_status.txt"])
    test_repo_obj.index.commit("Initial commit")
    test_repo_obj.git.push("origin", "test/remote-status")

    # Switch back to main
    test_repo_obj.git.checkout("main")

    # Get initial list output
    initial_result = runner.invoke(app, ["list", "--path", str(test_repo)])
    assert initial_result.exit_code == 0
    assert "test/remote-status" in initial_result.stdout
    assert "unmerged" in initial_result.stdout.lower()

    # Create a separate clone to simulate remote changes
    remote_clone_path = test_repo.parent / "remote_clone"
    remote_clone = Repo.clone_from(str(test_repo_obj.remote().url), str(remote_clone_path))

    # Set up git config in remote clone
    author = Actor("Test User", "test@example.com")
    remote_clone.config_writer().set_value("user", "name", author.name).release()
    remote_clone.config_writer().set_value("user", "email", author.email).release()

    # Fetch and merge the branch into main in the remote clone
    remote_clone.git.fetch("origin", "test/remote-status:test/remote-status")
    remote_clone.git.checkout("main")
    remote_clone.git.merge("test/remote-status", "--no-ff")  # Force a merge commit
    remote_clone.git.push("origin", "main")  # Push the merge to origin/main

    # Run list command again - it should show the branch as merged
    final_result = runner.invoke(app, ["list", "--path", str(test_repo)])
    assert final_result.exit_code == 0
    assert "test/remote-status" in final_result.stdout
    # The branch should be marked as merged in the output
    assert "│ test/remote-status        │  merged  │" in final_result.stdout

    # Clean up
    test_repo_obj.git.checkout("main")
    test_repo_obj.delete_head("test/remote-status")


def test_list_warns_when_main_behind(test_repo: Path, runner: CliRunner) -> None:
    """Test that list command warns when local main is behind remote."""
    repo = GitRepo(test_repo)
    test_repo_obj = repo.repo

    # Create a separate clone to simulate remote changes
    remote_clone_path = test_repo.parent / "remote_clone"
    remote_clone = Repo.clone_from(str(test_repo_obj.remote().url), str(remote_clone_path))

    # Set up git config in remote clone
    author = Actor("Test User", "test@example.com")
    remote_clone.config_writer().set_value("user", "name", author.name).release()
    remote_clone.config_writer().set_value("user", "email", author.email).release()

    # Make a change in the remote clone and push to main
    test_file = remote_clone_path / "test_main_behind.txt"
    test_file.write_text("test content")
    remote_clone.index.add(["test_main_behind.txt"])
    remote_clone.index.commit("Add test file to main")
    remote_clone.git.push("origin", "main")

    # Run list command - it should warn about main being behind and offer automatic update
    result = runner.invoke(app, ["list", "--path", str(test_repo)], input="n\n")  # Choose manual update
    assert result.exit_code == 1  # Should exit with error
    assert "Local main branch is behind remote" in result.stdout
    assert "Let arborist handle it automatically" in result.stdout
    assert "Do it manually" in result.stdout
    assert "Please update main branch manually" in result.stdout

    # Try again with automatic update
    result = runner.invoke(app, ["list", "--path", str(test_repo)], input="y\n")  # Choose automatic update
    assert result.exit_code == 0
    # Verify we can see the branch status table
    assert "Local Branches" in result.stdout
    assert "Remote Branches" in result.stdout
    # Verify the branch status is correct
    assert "feature/current (current)" in result.stdout
    assert "origin/main" in result.stdout


def test_list_handles_uncommitted_changes(test_repo: Path, runner: CliRunner) -> None:
    """Test that list command handles uncommitted changes when updating main."""
    repo = GitRepo(test_repo)
    test_repo_obj = repo.repo

    # Create a separate clone to simulate remote changes
    remote_clone_path = test_repo.parent / "remote_clone"
    remote_clone = Repo.clone_from(str(test_repo_obj.remote().url), str(remote_clone_path))

    # Set up git config in remote clone
    author = Actor("Test User", "test@example.com")
    remote_clone.config_writer().set_value("user", "name", author.name).release()
    remote_clone.config_writer().set_value("user", "email", author.email).release()

    # Make a change in the remote clone and push to main
    test_file = remote_clone_path / "test_main_behind.txt"
    test_file.write_text("test content")
    remote_clone.index.add(["test_main_behind.txt"])
    remote_clone.index.commit("Add test file to main")
    remote_clone.git.push("origin", "main")

    # Create uncommitted changes in the local repo
    local_file = test_repo / "uncommitted.txt"
    local_file.write_text("uncommitted changes")
    test_repo_obj.index.add(["uncommitted.txt"])

    # Run list command with automatic update
    result = runner.invoke(app, ["list", "--path", str(test_repo)], input="y\n")
    assert result.exit_code == 0
    assert "Local Branches" in result.stdout
    assert "Remote Branches" in result.stdout

    # Verify our uncommitted changes are still there
    assert local_file.read_text() == "uncommitted changes"
    assert "uncommitted.txt" in test_repo_obj.git.status("--porcelain")
