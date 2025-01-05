"""Command line interface for arborist."""

from pathlib import Path
from typing import Annotated

import typer
from rich import print
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from arborist.git import BranchStatus, GitError, GitRepo

app = typer.Typer(help="Git branch management tool")
console = Console()


def get_repo(path: Path) -> GitRepo:
    """Get git repository instance."""
    try:
        return GitRepo(path)
    except GitError as err:
        print(f"Error: {err}")
        raise typer.Exit(code=1) from err


def get_column_widths(
    local_branches: dict[str, BranchStatus],
    remote_branches: dict[str, BranchStatus],
    repo: GitRepo,
    current: str,
) -> tuple[int, int, int, int]:
    """Calculate maximum column widths needed for all content."""
    branch_width = 0
    status_width = 0
    commit_width = 0
    cleanable_width = len("Cleanable?")  # Width of the header

    # Process local branches
    for branch_name in local_branches:
        # Branch name (including current indicator if applicable)
        name_len = len(branch_name)
        if branch_name == current:
            name_len += len("(current)")  # Add space for the indicator
        branch_width = max(branch_width, name_len)

        # Status
        status = local_branches[branch_name]
        status_width = max(status_width, len(status.value))

        # Last commit
        commit = repo.get_branch_last_commit(branch_name)
        commit_width = max(commit_width, len(commit))

    # Process remote branches
    for branch_name in remote_branches:
        branch_width = max(branch_width, len(branch_name))
        status = remote_branches[branch_name]
        status_width = max(status_width, len(status.value))
        commit = repo.get_branch_last_commit(branch_name)
        commit_width = max(commit_width, len(commit))

    return branch_width, status_width, commit_width, cleanable_width


def create_branch_table(title: str, branch_width: int, status_width: int, commit_width: int, cleanable_width: int) -> Table:
    """Create a table with standard branch columns."""
    table = Table(
        title=title,
        show_header=True,
        header_style="bold",
        title_style="bold blue",
        show_edge=True,
    )

    # Add columns with minimum widths and no truncation
    table.add_column("Branch", style="cyan", min_width=branch_width, no_wrap=True)
    table.add_column("Status", style="magenta", min_width=status_width, justify="center", no_wrap=True)
    table.add_column("Last Commit", style="yellow", min_width=commit_width, no_wrap=True)
    table.add_column("Cleanable?", style="green", min_width=cleanable_width, justify="center", no_wrap=True)
    return table


@app.command()
def list(
    path: Annotated[Path, typer.Option(help="Path to git repository")] = Path("."),
    silent: bool = typer.Option(False, hidden=True),  # Hidden parameter for internal use
) -> None:
    """List all branches with their cleanup status."""
    repo = get_repo(path)
    repo.fetch_from_remotes()  # Ensure we have latest state

    try:
        status_dict = repo.get_branch_status()
    except GitError as err:
        if err.needs_confirmation:
            # Print without the confirmation prompt
            message_parts = str(err).split("[y/N]")
            print(f"[yellow]{message_parts[0].strip()}[/yellow]")

            # Ask for confirmation
            confirm = input("Would you like arborist to handle it automatically? [y/N] ")
            if confirm.lower() == "y":
                try:
                    repo._update_main_branch()
                    # Fetch again to ensure we have the latest state
                    repo.fetch_from_remotes()
                    # Try getting branch status again
                    status_dict = repo.get_branch_status()
                except GitError as update_err:
                    print(f"[red]Error:[/red] {update_err}")
                    raise typer.Exit(code=1) from update_err
            else:
                # User chose manual update
                print("\n[yellow]Please update main branch manually and run 'arb list' again[/yellow]")
                raise typer.Exit(code=1) from None  # Explicitly suppress the context
        else:
            print(f"[red]Error:[/red] {err}")
            raise typer.Exit(code=1) from err

    # Split branches into local and remote
    local_branches = {k: v for k, v in status_dict.items() if not k.startswith("origin/")}
    remote_branches = {k: v for k, v in status_dict.items() if k.startswith("origin/")}

    current = repo.get_current_branch_name()
    cleanable_local = []
    cleanable_remote = []

    # Calculate consistent column widths for both tables
    column_widths = get_column_widths(local_branches, remote_branches, repo, current)

    # Create and fill local branches table
    local_table = create_branch_table("Local Branches", *column_widths)
    for branch_name in sorted(local_branches.keys()):
        status = local_branches[branch_name]
        # Color-code the status
        if status == BranchStatus.MERGED:
            status_display = "[green]merged[/green]"
        elif status == BranchStatus.GONE:
            status_display = "[bright_yellow]gone[/bright_yellow]"
        else:
            status_display = status.value if status else ""

        # Format branch name with current indicator
        display_name = branch_name
        if branch_name == current:
            display_name = f"{branch_name} [turquoise2](current)[/turquoise2]"

        # Get last commit info
        last_commit = repo.get_branch_last_commit(branch_name)

        # Check if branch is cleanable
        cleanable = repo.is_branch_cleanable(branch_name)
        cleanable_display = "[green]✅[/green]" if cleanable else "[yellow]✋[/yellow]"

        if cleanable:
            cleanable_local.append(branch_name)

        local_table.add_row(
            display_name,
            status_display,
            last_commit,
            cleanable_display,
        )

    # Create and fill remote branches table
    remote_table = create_branch_table("Remote Branches", *column_widths)
    for branch_name in sorted(remote_branches.keys()):
        status = remote_branches[branch_name]
        # Color-code the status
        if status == BranchStatus.MERGED:
            status_display = "[green]merged[/green]"
        elif status == BranchStatus.GONE:
            status_display = "[bright_yellow]gone[/bright_yellow]"
        else:
            status_display = status.value if status else ""

        # Get last commit info
        last_commit = repo.get_branch_last_commit(branch_name)

        # Check if branch is cleanable
        cleanable = repo.is_branch_cleanable(branch_name)
        cleanable_display = "[green]✅[/green]" if cleanable else "[yellow]✋[/yellow]"

        if cleanable:
            cleanable_remote.append(branch_name)

        remote_table.add_row(
            branch_name,
            status_display,
            last_commit,
            cleanable_display,
        )

    if not silent:
        # Display tables
        console.print(local_table)
        console.print(remote_table)

        # Show message about cleanable branches
        if cleanable_local or cleanable_remote:
            cleanable_branches = []
            if cleanable_local:
                cleanable_branches.extend(cleanable_local)
            if cleanable_remote:
                cleanable_branches.extend(cleanable_remote)

            msg = "The following branches would be deleted if you run [dim]`arb clean`[/dim] next:\n" + "\n".join(
                f"  [blue]{branch}[/blue]" for branch in cleanable_branches
            )
            console.print(
                Panel(
                    msg,
                    title="Cleanable Branches",
                    title_align="left",
                    padding=(0, 2),
                    expand=False,
                )
            )
        else:
            console.print(
                Panel(
                    "[green]Your branches are clean ✨[/green]",
                    style="green",
                    padding=(0, 2),
                    expand=False,
                )
            )


@app.command()
def clean(
    path: Annotated[Path, typer.Option(help="Path to git repository")] = Path("."),
    protect: str = typer.Option("main", "--protect", "-p", help="Comma-separated list of branch patterns to protect"),
    force: bool = typer.Option(False, "--force", "-f", help="Force deletion of unmerged branches"),
    no_interactive: bool = typer.Option(False, "--no-interactive", "-y", help="Skip confirmation prompts"),
) -> None:
    """Clean up merged and gone branches."""
    repo = get_repo(path)
    protect_list = [p.strip() for p in protect.split(",")]

    # Run list command silently to ensure we have latest state
    list(path=path, silent=True)

    try:
        # Get preview table and potentially deleted branches
        preview_table, deleted = repo.clean(protect_list, force, not no_interactive)
        if not preview_table:
            console.print(
                Panel(
                    "[green]Your branches are clean ✨[/green]",
                    style="green",
                    padding=(0, 2),
                    expand=False,
                )
            )
            return

        # Show preview table
        console.print()  # Add a blank line
        console.print(preview_table)

        # If interactive, ask for confirmation
        if not no_interactive:
            console.print()  # Add a blank line
            confirm = input("Proceed with deletion? [y/N] ")
            if confirm.lower() != "y":
                console.print("\n[yellow]Operation cancelled[/yellow] 🛑")
                return

            # Delete branches after confirmation
            deleted = []
            for branch in sorted(preview_table.rows):
                branch_name = branch[0]  # First column contains branch name
                if repo._delete_branch(branch_name, repo.get_branch_status()[branch_name]):
                    deleted.append(branch_name)

        # Show results
        if deleted:
            # Create a table for deleted branches
            result_table = Table(
                title=f"Successfully deleted {len(deleted)} branch(es) 🧹",
                show_header=True,
                header_style="bold",
                title_style="bold green",
                show_edge=True,
            )
            result_table.add_column("Branch", style="cyan")
            for branch in sorted(deleted):
                result_table.add_row(branch)

            console.print()  # Add a blank line
            console.print(result_table)
        else:
            console.print("\n[yellow]No branches were deleted[/yellow] 🤔")

    except GitError as err:
        print(f"Error: {err}")
        raise typer.Exit(code=1) from err


if __name__ == "__main__":
    app()
