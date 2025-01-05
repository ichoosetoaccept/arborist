"""Tests for branch status functionality."""

from pathlib import Path

from arborist.git import BranchStatus, GitRepo


def test_main_branch_empty_status(test_env: tuple[Path, Path]) -> None:
    """Test that main branch has empty status."""
    local_path, _ = test_env
    repo = GitRepo(local_path)
    status = repo.get_branch_status()
    assert status["main"] == BranchStatus.EMPTY


def test_main_branch_last_commit(test_env: tuple[Path, Path]) -> None:
    """Test that main branch last commit is formatted correctly."""
    local_path, _ = test_env
    repo = GitRepo(local_path)
    timestamp = repo.get_branch_last_commit("main")
    # We can't test the exact timestamp since it depends on when the test runs
    assert " @ " in timestamp  # Check for time separator
    assert " - " in timestamp  # Check for date separator
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    assert any(day in timestamp for day in days)


def test_feature_branch_last_commit(test_env: tuple[Path, Path]) -> None:
    """Test that feature branch last commit is formatted correctly."""
    local_path, _ = test_env
    repo = GitRepo(local_path)
    timestamp = repo.get_branch_last_commit("feature/test")
    # We can't test the exact timestamp since it depends on when the test runs
    assert " @ " in timestamp  # Check for time separator
    assert " - " in timestamp  # Check for date separator
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    assert any(day in timestamp for day in days)


def test_remote_branch_last_commit(test_env: tuple[Path, Path]) -> None:
    """Test that remote branch last commit is formatted correctly."""
    local_path, _ = test_env
    repo = GitRepo(local_path)
    timestamp = repo.get_branch_last_commit("origin/feature/remote")
    # We can't test the exact timestamp since it depends on when the test runs
    assert " @ " in timestamp  # Check for time separator
    assert " - " in timestamp  # Check for date separator
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    assert any(day in timestamp for day in days)


def test_main_branch_not_cleanable(test_env: tuple[Path, Path]) -> None:
    """Test that main branch is never cleanable."""
    local_path, _ = test_env
    repo = GitRepo(local_path)
    assert not repo.is_branch_cleanable("main")


def test_current_branch_not_cleanable(test_env: tuple[Path, Path]) -> None:
    """Test that current branch is never cleanable."""
    local_path, _ = test_env
    repo = GitRepo(local_path)
    assert not repo.is_branch_cleanable("feature/current")


def test_merged_branch_cleanable(test_env: tuple[Path, Path]) -> None:
    """Test that merged branches are cleanable."""
    local_path, _ = test_env
    repo = GitRepo(local_path)
    status = repo.get_branch_status()
    assert status["feature/merged"] == BranchStatus.MERGED
    assert repo.is_branch_cleanable("feature/merged")


def test_unmerged_branch_not_cleanable(test_env: tuple[Path, Path]) -> None:
    """Test that unmerged branches are not cleanable."""
    local_path, _ = test_env
    repo = GitRepo(local_path)
    assert not repo.is_branch_cleanable("feature/test")


def test_protected_branch_not_cleanable(test_env: tuple[Path, Path]) -> None:
    """Test that protected branches are not cleanable."""
    local_path, _ = test_env
    repo = GitRepo(local_path)
    assert not repo.is_branch_cleanable("feature/merged", protect=["feature/*"])


def test_gone_branch_cleanable(test_env: tuple[Path, Path]) -> None:
    """Test that gone branches are cleanable."""
    local_path, _ = test_env
    repo = GitRepo(local_path)
    status = repo.get_branch_status()
    assert status["feature/gone"] == BranchStatus.GONE
    assert repo.is_branch_cleanable("feature/gone")


def test_nonexistent_branch_not_cleanable(test_env: tuple[Path, Path]) -> None:
    """Test that nonexistent branches are not cleanable."""
    local_path, _ = test_env
    repo = GitRepo(local_path)
    assert not repo.is_branch_cleanable("nonexistent/branch")


def test_delete_local_branch(test_env: tuple[Path, Path]) -> None:
    """Test deleting a local branch."""
    local_path, _ = test_env
    repo = GitRepo(local_path)
    assert repo._delete_branch("feature/test", BranchStatus.MERGED)
    # Verify branch is gone
    assert "feature/test" not in repo.get_branch_status()


def test_delete_remote_branch(test_env: tuple[Path, Path]) -> None:
    """Test deleting a remote branch."""
    local_path, _ = test_env
    repo = GitRepo(local_path)
    assert repo._delete_branch("origin/feature/remote", BranchStatus.MERGED)
    # Verify branch is gone from remote
    remote_branches = [ref.remote_head for ref in repo.repo.remote().refs]
    assert "feature/remote" not in remote_branches


def test_cannot_delete_main_branch_with_force(test_env: tuple[Path, Path]) -> None:
    """Test that main branch cannot be deleted even with force."""
    local_path, _ = test_env
    repo = GitRepo(local_path)

    # Try to delete main branch directly
    assert not repo._delete_branch("main", BranchStatus.MERGED)

    # Verify main branch still exists
    branches = repo.get_branch_status()
    assert "main" in branches


def test_skip_internal_git_refs(test_repo: Path) -> None:
    """Test that internal Git refs are skipped."""
    repo = GitRepo(test_repo)
    status = repo.get_branch_status()

    # Verify no internal refs are present
    for branch_name in status:
        assert not branch_name.startswith("heads/"), f"Found internal ref: {branch_name}"
        assert not branch_name.startswith("remotes/"), f"Found internal ref: {branch_name}"


def test_delete_nonexistent_remote_branch(test_repo: Path) -> None:
    """Test deleting a nonexistent remote branch."""
    repo = GitRepo(test_repo)
    # Try to delete a nonexistent remote branch
    result = repo._delete_branch("origin/nonexistent", BranchStatus.GONE)
    assert not result, "Should return False when deleting nonexistent remote branch"


def test_delete_nonexistent_local_branch(test_repo: Path) -> None:
    """Test deleting a nonexistent local branch."""
    repo = GitRepo(test_repo)
    # Try to delete a nonexistent local branch
    result = repo._delete_branch("nonexistent", BranchStatus.GONE)
    assert not result, "Should return False when deleting nonexistent local branch"


def test_unpushed_commits_not_gone(test_env: tuple[Path, Path]) -> None:
    """Test that a branch with unpushed commits is not marked as gone even if remote is gone."""
    local_path, _ = test_env
    repo = GitRepo(local_path)
    test_repo = repo.repo

    # Create and push a test branch
    test_repo.git.checkout("-b", "test/unpushed")
    test_file = local_path / "test_unpushed.txt"
    test_file.write_text("initial content")
    test_repo.index.add(["test_unpushed.txt"])
    test_repo.index.commit("Initial commit")
    test_repo.git.push("-u", "origin", "test/unpushed")

    # Make a new commit without pushing
    test_file.write_text("updated content")
    test_repo.index.add(["test_unpushed.txt"])
    test_repo.index.commit("Unpushed commit")

    # Delete the remote branch to simulate gone remote
    test_repo.git.push("origin", "--delete", "test/unpushed")

    # Get branch status
    status = repo.get_branch_status()
    print("\nDEBUG: Branch status:")
    for branch, branch_status in status.items():
        print(f"{branch}: {branch_status.value}")

    # Verify branch is not marked as gone
    assert status["test/unpushed"] == BranchStatus.UNMERGED
    assert not repo.is_branch_cleanable("test/unpushed")

    # Switch back to main
    test_repo.git.checkout("main")
