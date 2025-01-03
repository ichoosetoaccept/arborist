"""Git repository operations for branch management."""

from enum import Enum
from fnmatch import fnmatch
from pathlib import Path

from git import GitCommandError, InvalidGitRepositoryError, Repo


class BranchStatus(Enum):
    """Branch status."""
    MERGED = "merged"
    UNMERGED = "unmerged"
    GONE = "gone"
    CURRENT = "current"


class GitError(Exception):
    """Git operation error."""
    pass


class GitRepo:
    """Git repository operations."""

    def __init__(self, path: Path = Path(".")) -> None:
        """Initialize git repository."""
        try:
            self.repo = Repo(path)
            if self.repo.bare:
                raise GitError("Cannot operate on bare repository")
        except (GitCommandError, ValueError, InvalidGitRepositoryError) as err:
            raise GitError(f"Failed to open repository: {err}")

    def get_current_branch_name(self) -> str:
        """Get current branch name."""
        try:
            return self.repo.active_branch.name
        except (GitCommandError, TypeError) as err:
            raise GitError(f"Failed to get current branch: {err}")

    def get_branch_status(self) -> dict[str, BranchStatus]:
        """Get status of all branches."""
        try:
            current = self.get_current_branch_name()
            status: dict[str, BranchStatus] = {}

            for branch in self.repo.heads:
                if branch.name == current:
                    status[branch.name] = BranchStatus.CURRENT
                    continue

                # Check if branch is gone (had remote tracking but remote is gone)
                tracking = branch.tracking_branch()
                if tracking and not tracking.is_valid():
                    status[branch.name] = BranchStatus.GONE
                    continue

                # Check if branch is merged
                try:
                    # Get the merge base (common ancestor)
                    merge_base = self.repo.git.merge_base(current, branch.name, "--all").splitlines()
                    # Get all commits in the branch that aren't in the merge base
                    unique_commits = self.repo.git.rev_list(
                        f"{merge_base[0]}..{branch.name}"
                    ).splitlines()
                    # Branch is merged if it has no unique commits
                    status[branch.name] = BranchStatus.MERGED if not unique_commits else BranchStatus.UNMERGED
                except GitCommandError:
                    status[branch.name] = BranchStatus.UNMERGED

            return status
        except GitCommandError as err:
            raise GitError(f"Failed to get branch status: {err}")

    def _get_branches_to_delete(
        self, status: dict[str, BranchStatus], protect: list[str], force: bool
    ) -> list[str]:
        """Get list of branches that should be deleted."""
        current = self.get_current_branch_name()
        to_delete = []

        for branch_name, branch_status in status.items():
            # Skip protected branches
            if any(fnmatch(branch_name, pattern) for pattern in protect):
                continue
            # Skip current branch
            if branch_name == current:
                continue
            # Skip remote tracking branches unless force is used
            branch = self.repo.heads[branch_name]
            if branch.tracking_branch() and not force and branch_status != BranchStatus.GONE:
                continue
            # Include merged and gone branches, or all if force is True
            if branch_status in (BranchStatus.MERGED, BranchStatus.GONE) or force:
                to_delete.append(branch_name)

        return to_delete

    def _delete_branch(self, branch_name: str, force: bool, status: BranchStatus) -> bool:
        """Delete a single branch. Returns True if successful."""
        try:
            branch = self.repo.heads[branch_name]
            
            # Delete remote tracking branch if it exists and branch is gone
            tracking = branch.tracking_branch()
            if tracking and status == BranchStatus.GONE:
                try:
                    tracking_name = tracking.name.split("/", 1)[1]  # Remove remote prefix
                    self.repo.git.branch("-d", "-r", tracking_name)
                except GitCommandError:
                    pass  # Ignore errors when deleting remote tracking branches

            # Delete local branch
            delete_flag = "-D" if force or status == BranchStatus.GONE else "-d"
            self.repo.git.branch(delete_flag, branch_name)
            return True
        except GitCommandError as err:
            print(f"Failed to delete branch {branch_name}: {err}")
            return False

    def clean(
        self,
        protect: list[str],
        force: bool = False,
        interactive: bool = True,
        dry_run: bool = False,
    ) -> None:
        """Clean up branches."""
        try:
            status = self.get_branch_status()
            to_delete = self._get_branches_to_delete(status, protect, force)

            if not to_delete:
                print("No branches to clean")
                return

            # Show what will be deleted
            if dry_run:
                print("\nDry run - branches that would be deleted:")
            else:
                print("\nBranches to delete:")
            for branch_name in to_delete:
                print(f"  {branch_name} ({status[branch_name].value})")

            if interactive and not dry_run:
                response = input("\nProceed with deletion? [y/N] ")
                if response.lower() != "y":
                    print("Operation cancelled")
                    return

            # Delete branches
            deleted = []
            for branch_name in to_delete:
                if dry_run:
                    print(f"Would delete branch: {branch_name}")
                    continue

                if self._delete_branch(branch_name, force, status[branch_name]):
                    deleted.append(branch_name)
                    print(f"Successfully deleted branch: {branch_name}")

            if deleted:
                print(f"\nSuccessfully deleted {len(deleted)} branch(es)")

        except GitCommandError as err:
            raise GitError(f"Failed to clean branches: {err}") 