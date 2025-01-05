"""Git repository operations."""

from enum import Enum
from fnmatch import fnmatch
from pathlib import Path
from typing import Optional, Tuple

from git import GitCommandError, InvalidGitRepositoryError, Repo
from rich.table import Table


class BranchStatus(Enum):
    """Branch status."""

    MERGED = "merged"
    UNMERGED = "unmerged"
    GONE = "gone"
    EMPTY = ""  # Used for main branch


class GitError(Exception):
    """Git operation error."""

    pass


class GitRepo:
    """Git repository operations."""

    def __init__(self, path: Path) -> None:
        """Initialize repository."""
        try:
            self.repo: Repo = Repo(path)
            if self.repo.bare:
                raise GitError("Cannot operate on bare repository")
        except (GitCommandError, ValueError, InvalidGitRepositoryError) as err:
            raise GitError(f"Failed to open repository: {err}") from err

    def fetch_from_remotes(self) -> None:
        """Fetch latest state from all remotes and update local branches."""
        try:
            for remote in self.repo.remotes:
                # Fetch from remote
                remote.fetch()
                # Update local references to remote branches
                self.repo.git.remote("update", remote.name, "--prune")
                # Pull changes for the current branch if it has an upstream
                current = self.get_current_branch_name()
                if current:
                    try:
                        tracking_branch = self.repo.active_branch.tracking_branch()
                        if tracking_branch:
                            self.repo.git.pull(remote.name, current)
                    except GitCommandError:
                        # If pull fails (e.g., merge conflicts), just continue
                        pass
        except GitCommandError as err:
            raise GitError(f"Failed to fetch from remotes: {err}") from err

    def get_current_branch_name(self) -> str:
        """Get current branch name."""
        try:
            try:
                return self.repo.active_branch.name
            except TypeError:
                # We're in a detached HEAD state
                # In this case, we'll return an empty string since we don't want to protect a detached HEAD
                return ""
        except (GitCommandError, ValueError) as err:
            raise GitError(f"Failed to get current branch: {err}") from err

    def get_branch_status(self) -> dict[str, BranchStatus]:
        """Get the status of all branches."""
        try:
            status: dict[str, BranchStatus] = {}
            current = self.get_current_branch_name()

            # Get all local branches
            local_branches = self.repo.git.branch("--format=%(refname:short)").splitlines()
            for branch_name in local_branches:
                # Skip internal Git refs
                if branch_name.startswith("heads/") or branch_name.startswith("remotes/"):
                    continue

                # Special handling for main branch
                if branch_name == "main":
                    status[branch_name] = BranchStatus.EMPTY
                    continue

                # Always mark current branch as unmerged
                if branch_name == current:
                    status[branch_name] = BranchStatus.UNMERGED
                    continue

                # Check if branch is gone
                try:
                    # Get the remote tracking configuration
                    tracking_config = self.repo.git.config(f"branch.{branch_name}.remote")
                    if tracking_config:
                        remote_name = tracking_config
                        merge_ref = self.repo.git.config(f"branch.{branch_name}.merge")
                        if merge_ref.startswith("refs/heads/"):
                            remote_branch = merge_ref[len("refs/heads/") :]
                            remote_ref = f"{remote_name}/{remote_branch}"
                            try:
                                # Try to get the remote branch
                                self.repo.git.rev_parse(remote_ref)
                            except GitCommandError:
                                # Remote branch doesn't exist, check if it's marked as gone
                                try:
                                    # Get branch status with -vv
                                    branch_info = self.repo.git.branch("-vv", "--list", branch_name)
                                    if ": gone]" in branch_info:
                                        # Branch is marked as gone in Git
                                        status[branch_name] = BranchStatus.GONE
                                    else:
                                        # Check for unpushed commits
                                        try:
                                            # Get number of commits that haven't been pushed
                                            unpushed = self.repo.git.rev_list("--count", f"{branch_name}").strip()
                                            if unpushed == "0":
                                                # No unpushed commits, safe to mark as gone
                                                status[branch_name] = BranchStatus.GONE
                                            else:
                                                # Has unpushed commits, mark as unmerged to prevent data loss
                                                status[branch_name] = BranchStatus.UNMERGED
                                        except GitCommandError:
                                            # If we can't check, be conservative and mark as unmerged
                                            status[branch_name] = BranchStatus.UNMERGED
                                except GitCommandError:
                                    # If we can't check, be conservative and mark as unmerged
                                    status[branch_name] = BranchStatus.UNMERGED
                                continue
                except GitCommandError:
                    # No remote tracking configuration
                    pass

                # Check if branch is merged into main
                try:
                    # Get the branch tip
                    branch_tip = self.repo.git.rev_parse(branch_name).strip()
                    # Get the main tip
                    main_tip = self.repo.git.rev_parse("main").strip()
                    # Branch is merged if it's either:
                    # 1. An ancestor of main (fast-forward merge)
                    # 2. All its commits are in main (merge commit)
                    try:
                        # Check if it's an ancestor (fast-forward case)
                        self.repo.git.merge_base("--is-ancestor", branch_tip, main_tip)
                        status[branch_name] = BranchStatus.MERGED
                    except GitCommandError:
                        # Check if all commits are in main (merge commit case)
                        try:
                            unmerged_commits = self.repo.git.rev_list("--count", f"main..{branch_name}").strip()
                            if unmerged_commits == "0":
                                status[branch_name] = BranchStatus.MERGED
                            else:
                                status[branch_name] = BranchStatus.UNMERGED
                        except GitCommandError:
                            status[branch_name] = BranchStatus.UNMERGED
                except GitCommandError:
                    status[branch_name] = BranchStatus.UNMERGED

            # Get all remote branches
            remote_branches = self.repo.git.branch("-r", "--format=%(refname:short)").splitlines()
            for branch_name in remote_branches:
                # Skip HEAD ref
                if branch_name.endswith("/HEAD"):
                    continue
                # Skip if we already have this branch locally
                if branch_name in status:
                    continue

                # Special handling for origin/main
                if branch_name == "origin/main":
                    status[branch_name] = BranchStatus.EMPTY
                    continue

                try:
                    # Get the branch tip and check merge status
                    branch_tip = self.repo.git.rev_parse(branch_name).strip()
                    main_tip = self.repo.git.rev_parse("main").strip()

                    try:
                        # Check if it's an ancestor (fast-forward case)
                        self.repo.git.merge_base("--is-ancestor", branch_tip, main_tip)
                        status[branch_name] = BranchStatus.MERGED
                    except GitCommandError:
                        # Check if all commits are in main (merge commit case)
                        try:
                            unmerged_commits = self.repo.git.rev_list("--count", f"main..{branch_name}").strip()
                            if unmerged_commits == "0":
                                status[branch_name] = BranchStatus.MERGED
                            else:
                                status[branch_name] = BranchStatus.UNMERGED
                        except GitCommandError:
                            status[branch_name] = BranchStatus.UNMERGED
                except GitCommandError:
                    status[branch_name] = BranchStatus.UNMERGED

            return status
        except GitCommandError as err:
            raise GitError(f"Failed to get branch status: {err}") from err

    def _get_branches_to_delete(self, protect: list[str], force: bool = False) -> dict[str, BranchStatus]:
        """Get branches that can be deleted."""
        status = self.get_branch_status()
        current = self.get_current_branch_name()

        # Remove protected branches
        for branch_name in list(status.keys()):
            # Skip current branch
            if branch_name == current:
                del status[branch_name]
                continue

            # Check if branch is protected
            # For remote branches, check both the full name and the branch part after origin/
            if branch_name.startswith("origin/"):
                branch_without_remote = branch_name.split("/", 1)[1]
                if any(fnmatch(branch_without_remote, pattern.strip()) for pattern in protect):
                    del status[branch_name]
                    continue
            if any(fnmatch(branch_name, pattern.strip()) for pattern in protect):
                del status[branch_name]
                continue

        # Remove unmerged branches unless force is True
        if not force:
            for branch_name, state in list(status.items()):
                if state == BranchStatus.UNMERGED:
                    del status[branch_name]

        return status

    def _delete_branch(self, branch_name: str, status: BranchStatus) -> bool:
        """Delete a single branch. Returns True if successful."""
        try:
            # Never delete main branch
            if branch_name == "main" or (branch_name.startswith("origin/") and branch_name.split("/", 1)[1] == "main"):
                return False

            # Handle remote branches
            if branch_name.startswith("origin/"):
                remote_name, remote_branch = branch_name.split("/", 1)
                try:
                    remote = self.repo.remote(remote_name)
                    # Delete remote branch by pushing an empty reference
                    remote.push(refspec=f":{remote_branch}")
                    return True
                except GitCommandError:
                    return False

            # Delete the local branch
            try:
                # Always use -D for force delete since we've already checked if it's safe to delete
                self.repo.git.branch("-D", branch_name)
                return True
            except GitCommandError:
                return False

        except GitCommandError:
            return False

    def clean(
        self,
        protect: list[str],
        force: bool = False,
        interactive: bool = True,
    ) -> Tuple[Table, list[str]]:
        """Clean up merged and gone branches.

        Returns:
            A tuple of (preview_table, deleted_branches).
            If interactive is True, the branches will only be deleted after user confirmation.
        """
        try:
            # Get branches to delete
            to_delete = self._get_branches_to_delete(protect, force)
            if not to_delete:
                return None, []

            # Create a table for branches to delete
            table = Table(
                title="Branches to Delete",
                show_header=True,
                header_style="bold",
                title_style="bold blue",
                show_edge=True,
            )
            table.add_column("Branch", style="cyan")
            table.add_column("Status", style="magenta", justify="center")

            # Add branches to table
            for branch, status in sorted(to_delete.items()):
                status_display = "[green]merged[/green]" if status == BranchStatus.MERGED else "[bright_yellow]gone[/bright_yellow]"
                table.add_row(branch, status_display)

            # If not interactive, delete branches immediately
            if not interactive:
                deleted = []
                for branch, status in to_delete.items():
                    if self._delete_branch(branch, status):
                        deleted.append(branch)
                return table, deleted

            # Otherwise, return the table and no deleted branches
            return table, []

        except GitCommandError as err:
            raise GitError(f"Failed to clean branches: {err}") from err

    def get_branch_last_commit(self, branch_name: str) -> str:
        """Get the last commit timestamp for a branch."""
        try:
            # Get the last commit timestamp
            return str(
                self.repo.git.log(
                    "-1",
                    "--format=%cd",
                    "--date=format:'%a - %B %d @ %H:%M'",
                    branch_name,
                ).strip("'")
            )
        except GitCommandError:
            return ""

    def is_branch_cleanable(self, branch_name: str, protect: Optional[list[str]] = None) -> bool:
        """Check if a branch can be cleaned up."""
        if protect is None:
            protect = ["main"]

        # Never clean main or current branch
        current = self.get_current_branch_name()
        if branch_name == "main":
            return False
        if branch_name == current:
            return False

        # Check if branch is protected
        # For remote branches, check both the full name and the branch part after origin/
        if branch_name.startswith("origin/"):
            branch_without_remote = branch_name.split("/", 1)[1]
            if any(fnmatch(branch_without_remote, pattern) for pattern in protect):
                return False
        if any(fnmatch(branch_name, pattern) for pattern in protect):
            return False

        # Get branch status
        status = self.get_branch_status()
        if branch_name not in status:
            return False

        # Only merged or gone branches can be cleaned
        branch_status = status[branch_name]
        return branch_status in [BranchStatus.MERGED, BranchStatus.GONE]
