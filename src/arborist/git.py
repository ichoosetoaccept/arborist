"""Git repository operations."""

from enum import Enum
from fnmatch import fnmatch
from pathlib import Path

from git import GitCommandError, InvalidGitRepositoryError, Repo


class BranchStatus(Enum):
    """Branch status."""

    MERGED = "merged"
    UNMERGED = "unmerged"
    GONE = "gone"


class GitError(Exception):
    """Git operation error."""

    pass


class GitRepo:
    """Git repository operations."""

    def __init__(self, path: Path) -> None:
        """Initialize repository."""
        try:
            self.repo = Repo(path)
            if self.repo.bare:
                raise GitError("Cannot operate on bare repository")
        except (GitCommandError, ValueError, InvalidGitRepositoryError) as err:
            raise GitError(f"Failed to open repository: {err}") from err

    def get_current_branch_name(self) -> str:
        """Get current branch name."""
        try:
            return self.repo.active_branch.name
        except (GitCommandError, TypeError) as err:
            raise GitError(f"Failed to get current branch: {err}") from err

    def get_branch_status(self) -> dict[str, BranchStatus]:
        """Get status of all local branches."""
        try:
            status: dict[str, BranchStatus] = {}
            current = self.get_current_branch_name()

            # Get all branches
            for branch in self.repo.heads:
                # Skip current branch
                if branch.name == current:
                    continue

                # Check if branch is gone
                tracking = branch.tracking_branch()
                if tracking and not tracking.is_valid():
                    status[branch.name] = BranchStatus.GONE
                    continue

                # Check if branch is merged
                try:
                    # Get the merge base (common ancestor)
                    merge_base = self.repo.git.merge_base(
                        current, branch.name, "--all"
                    ).splitlines()
                    # Get all commits in the branch that aren't in the merge base
                    unique_commits = self.repo.git.rev_list(
                        f"{merge_base[0]}..{branch.name}"
                    ).splitlines()
                    # Branch is merged if it has no unique commits
                    status[branch.name] = (
                        BranchStatus.MERGED if not unique_commits else BranchStatus.UNMERGED
                    )
                except GitCommandError:
                    status[branch.name] = BranchStatus.UNMERGED

            return status
        except GitCommandError as err:
            raise GitError(f"Failed to get branch status: {err}") from err

    def _get_branches_to_delete(
        self, protect: list[str], force: bool = False
    ) -> dict[str, BranchStatus]:
        """Get branches that can be deleted."""
        status = self.get_branch_status()
        current = self.get_current_branch_name()

        # Remove protected branches
        for branch in list(status.keys()):
            # Skip current branch
            if branch == current:
                del status[branch]
                continue
            # Skip protected branches
            if any(fnmatch(branch, pattern) for pattern in protect):
                del status[branch]
                continue

        # Remove unmerged branches unless force is True
        if not force:
            for branch, state in list(status.items()):
                if state == BranchStatus.UNMERGED:
                    del status[branch]

        return status

    def _delete_branch(self, branch_name: str, status: BranchStatus) -> bool:
        """Delete a single branch. Returns True if successful."""
        try:
            branch = self.repo.heads[branch_name]

            # Delete remote tracking branch if it exists and branch is gone
            tracking = branch.tracking_branch()
            if tracking and status == BranchStatus.GONE:
                tracking.remote.push(refspec=f":{tracking.remote_head}")

            # Delete local branch
            self.repo.delete_head(branch_name, force=True)
            return True
        except GitCommandError:
            return False

    def clean(
        self,
        protect: list[str],
        force: bool = False,
        interactive: bool = True,
        dry_run: bool = False,
    ) -> None:
        """Clean up merged and gone branches."""
        try:
            # Get branches to delete
            to_delete = self._get_branches_to_delete(protect, force)
            if not to_delete:
                print("No branches to clean")
                return

            # Show what will be deleted
            if dry_run:
                print("\nDry run - branches that would be deleted:")
            else:
                print("\nBranches to delete:")
            for branch, status in to_delete.items():
                if dry_run:
                    print(f"Would delete branch: {branch} ({status.value})")
                else:
                    print(f"  {branch} ({status.value})")

            # Confirm deletion
            if not dry_run and interactive:
                confirm = input("\nProceed with deletion? [y/N] ")
                if confirm.lower() != "y":
                    print("Operation cancelled")
                    return

            # Delete branches
            if not dry_run:
                deleted = []
                for branch, status in to_delete.items():
                    if self._delete_branch(branch, status):
                        deleted.append(branch)
                print(f"\nSuccessfully deleted {len(deleted)} branch(es)")

        except GitCommandError as err:
            raise GitError(f"Failed to clean branches: {err}") from err
