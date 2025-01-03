"""Command line interface for arborist."""

from pathlib import Path
from typing import Annotated

import typer
from rich import print
from rich.console import Console
from rich.table import Table

from arborist.git import GitError, GitRepo

app = typer.Typer(help="Git branch management tool")
console = Console()


def get_repo(path: Path) -> GitRepo:
    """Get git repository instance."""
    try:
        return GitRepo(path)
    except GitError as err:
        print(f"Error: {err}")
        raise typer.Exit(code=1)


@app.command()
def list(
    path: Annotated[Path, typer.Option(help="Path to git repository")] = Path("."),
) -> None:
    """List all branches with their cleanup status."""
    repo = get_repo(path)
    status_dict = repo.get_branch_status()

    table = Table()
    table.add_column("Branch", style="cyan")
    table.add_column("Status", style="magenta")

    current = repo.get_current_branch_name()
    for branch, state in sorted(status_dict.items()):
        table.add_row(
            f"{branch} {'(current)' if branch == current else ''}",
            state.value,
        )

    console.print(table)


@app.command()
def clean(
    path: Annotated[Path, typer.Option(help="Path to git repository")] = Path("."),
    protect: str = typer.Option(
        "main", "--protect", "-p", help="Comma-separated list of branch patterns to protect"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Force deletion of unmerged branches"),
    no_interactive: bool = typer.Option(False, "--no-interactive", "-y", help="Skip confirmation prompts"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be done without doing it"),
) -> None:
    """Clean up merged and gone branches."""
    repo = get_repo(path)
    protect_list = [p.strip() for p in protect.split(",")]
    try:
        repo.clean(protect_list, force, not no_interactive, dry_run)
    except GitError as err:
        print(f"Error: {err}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
