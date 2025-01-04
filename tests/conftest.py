"""Test configuration and fixtures."""

from pathlib import Path
from typing import Generator

import pytest
from git import Actor, Repo


@pytest.fixture
def test_env(tmp_path: Path) -> Generator[tuple[Path, Path], None, None]:
    """Create a test environment with local and remote repositories.

    Returns:
        Tuple of (local_repo_path, remote_repo_path)
    """
    # Create temporary directories for both repos
    remote_path = tmp_path / "remote"
    local_path = tmp_path / "local"
    remote_path.mkdir()
    local_path.mkdir()

    # Initialize remote repo
    Repo.init(remote_path, bare=True)

    # Initialize local repo
    local_repo = Repo.init(local_path)

    # Set up git config
    author = Actor("Test User", "test@example.com")
    local_repo.config_writer().set_value("user", "name", author.name).release()
    local_repo.config_writer().set_value("user", "email", author.email).release()

    # Create initial commit in local repo and set up main branch
    readme = local_path / "README.md"
    readme.write_text("# Test Repository")
    local_repo.index.add(["README.md"])
    local_repo.index.commit("Initial commit", author=author)

    # Ensure we're on main branch
    if "main" not in local_repo.heads:
        # Create main branch if it doesn't exist
        local_repo.create_head("main")
    main_branch = local_repo.heads.main
    main_branch.checkout()

    # Add remote
    origin = local_repo.create_remote("origin", url=str(remote_path))

    # Push to remote and set up tracking
    origin.push("main")
    main_branch.set_tracking_branch(origin.refs.main)

    # Create some test branches
    def create_branch(name: str, content: str, merge: bool = False) -> None:
        """Create a branch with some content."""
        # Start from main
        main_branch.checkout()

        # Create and checkout new branch
        branch = local_repo.create_head(name)
        branch.checkout()

        # Add some content
        test_file = local_path / f"{name}.txt"
        # Ensure parent directories exist
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text(content)
        local_repo.index.add([f"{name}.txt"])
        local_repo.index.commit(f"Add {name}", author=author)

        # Push branch to remote and set up tracking
        origin.push(name)
        branch.set_tracking_branch(origin.refs[name])

        if merge:
            # Switch back to main and merge
            main_branch.checkout()
            local_repo.git.merge(name, "--no-ff")  # Use --no-ff to force a merge commit
            origin.push("main")

    # Create test branches
    create_branch("feature/test", "Test branch content")
    # Add another commit to make it unmerged
    test_file = local_path / "feature/test.txt"
    test_file.write_text("More test branch content")
    local_repo.index.add(["feature/test.txt"])
    local_repo.index.commit("Update test branch", author=author)
    local_repo.remote("origin").push("feature/test")

    create_branch("feature/merged", "Merged branch content", merge=True)
    create_branch("feature/current", "Current branch content")

    # Create a branch that will be deleted in remote
    create_branch("feature/gone", "Gone branch content")
    origin.push(":feature/gone")  # Delete in remote

    # Create a remote-only branch
    main_branch.checkout()
    local_repo.create_head("feature/remote", "main")
    test_file = local_path / "feature_remote.txt"
    test_file.write_text("Remote branch content")
    local_repo.index.add(["feature_remote.txt"])
    local_repo.index.commit("Add remote branch", author=author)
    origin.push("feature/remote")
    local_repo.delete_head("feature/remote")

    # Switch to feature/current as the active branch
    local_repo.heads["feature/current"].checkout()

    yield local_path, remote_path

    # Cleanup is handled by pytest's tmp_path fixture
