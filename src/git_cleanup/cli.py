"""CLI interface for git-cleanup."""


import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm

from . import config, git

app = typer.Typer(
    help="Clean up git branches that are gone or merged.",
    add_completion=False,
)
console = Console()


def validate_git_repo() -> None:
    """Validate we're in a git repository."""
    if not git.is_git_repo():
        console.print("[red]Error: Not a git repository[/red]")
        raise typer.Exit(1)


def handle_gone_branches(cfg: config.Config) -> None:
    """Handle branches with gone remotes."""
    console.print("\n🔍 [blue]Checking for branches with gone remotes...[/blue]")
    gone_branches = git.get_gone_branches()
    gone_branches = git.filter_protected_branches(gone_branches, cfg.protected_branches)

    if not gone_branches:
        console.print("[green]No branches with gone remotes found.[/green]")
        return

    console.print(
        f"[yellow]Found {len(gone_branches)} branches with gone remotes:[/yellow]",
    )
    for branch in gone_branches:
        console.print(f"[yellow]  {branch}[/yellow]")

    if not cfg.dry_run_by_default:
        delete_branches(gone_branches, cfg.interactive, force=True)


def handle_merged_branches(cfg: config.Config) -> None:
    """Handle merged branches."""
    console.print("\n🧹 [blue]Checking for merged branches...[/blue]")
    merged_branches = git.get_merged_branches()
    merged_branches = git.filter_protected_branches(
        merged_branches,
        cfg.protected_branches,
    )

    if not merged_branches:
        console.print("[green]No merged branches found.[/green]")
        return

    console.print(f"[yellow]Found {len(merged_branches)} merged branches:[/yellow]")
    for branch in merged_branches:
        console.print(f"[yellow]  {branch}[/yellow]")

    if not cfg.dry_run_by_default:
        delete_branches(merged_branches, cfg.interactive)


def handle_merged_remote_branches(cfg: config.Config) -> None:
    """Handle merged remote branches."""
    console.print("\n🌐 [blue]Checking for merged remote branches...[/blue]")
    merged_remotes = git.get_merged_remote_branches()
    merged_remotes = git.filter_protected_branches(
        merged_remotes,
        cfg.protected_branches,
    )

    if not merged_remotes:
        console.print("[green]No merged remote branches found.[/green]")
        return

    console.print(
        f"[yellow]Found {len(merged_remotes)} merged remote branches:[/yellow]",
    )
    for branch in merged_remotes:
        console.print(f"[yellow]  {branch}[/yellow]")

    if not cfg.dry_run_by_default:
        delete_remote_branches(merged_remotes, cfg.interactive)


def delete_branches(
    branches: list[str],
    interactive: bool = True,
    force: bool = False,
) -> None:
    """Delete the given branches.

    Args:
    ----
        branches: List of branch names to delete
        interactive: Whether to ask for confirmation before deleting (defaults to True)
        force: Whether to force delete branches (-D instead of -d)

    """
    if not branches:
        return

    if interactive:
        console.print("\n[yellow]The following branches will be deleted:[/yellow]")
        for branch in branches:
            console.print(f"  [yellow]{branch}[/yellow]")

        prompt = "\n[yellow]Do you want to proceed with deletion?[/yellow]"
        if not Confirm.ask(prompt, default=False):
            console.print("[blue]Skipping branch deletion.[/blue]")
            return

    for branch in branches:
        try:
            if interactive:
                if not Confirm.ask(f"Delete branch {branch}?", default=False):
                    console.print(f"[blue]Skipping branch {branch}[/blue]")
                    continue
            git.delete_branch(branch, force=force)
            console.print(f"[green]Deleted branch {branch}[/green]")
        except git.GitError as e:
            console.print(f"[red]Error deleting {branch}: {e!s}[/red]")


def delete_remote_branches(
    branches: list[str],
    interactive: bool = True,
) -> None:
    """Delete the given remote branches.

    Args:
    ----
        branches: List of remote branch names to delete
        interactive: Whether to ask for confirmation before deleting (defaults to True)

    """
    if not branches:
        return

    if interactive:
        console.print(
            "\n[yellow]The following remote branches will be deleted:[/yellow]",
        )
        for branch in branches:
            console.print(f"  [yellow]{branch}[/yellow]")

        prompt = (
            "\n[yellow]Do you want to proceed with remote branch deletion?[/yellow]"
        )
        if not Confirm.ask(prompt, default=False):
            console.print("[blue]Skipping remote branch deletion.[/blue]")
            return

    for branch in branches:
        try:
            if interactive:
                if not Confirm.ask(f"Delete remote branch {branch}?", default=False):
                    console.print(f"[blue]Skipping remote branch {branch}[/blue]")
                    continue
            git.delete_remote_branch(branch)
            console.print(f"[green]Deleted remote branch {branch}[/green]")
        except git.GitError as e:
            console.print(f"[red]Error deleting remote {branch}: {e!s}[/red]")


def optimize_repository(cfg: config.Config) -> None:
    """Optimize the git repository."""
    if cfg.skip_gc or cfg.dry_run_by_default:
        return

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[blue]{task.description}[/blue]"),
            console=console,
        ) as progress:
            task_id = progress.add_task("⚡ Optimizing repository...", total=None)
            git.optimize_repo(
                progress_callback=lambda msg: progress.update(
                    task_id,
                    description=f"⚡ {msg}",
                ),
            )
        console.print("[green]Repository optimized successfully.[/green]")
    except git.GitError as e:
        console.print(f"[red]Error optimizing repository: {e!s}[/red]")


def update_config_from_options(
    cfg: config.Config,
    dry_run: bool | None,
    interactive: bool | None,
    no_gc: bool | None,
    protect: list[str] | None,
) -> None:
    """Update configuration with CLI options."""
    if dry_run is not None:
        cfg.dry_run_by_default = dry_run
    if interactive is not None:
        cfg.interactive = interactive
    if no_gc is not None:
        cfg.skip_gc = no_gc
    if protect:
        cfg.protected_branches.extend(protect)


# CLI option definitions
dry_run_option = typer.Option(
    False,
    "--dry-run",
    "-d",
    help="Show what would be deleted without actually deleting",
)
no_interactive_option = typer.Option(
    False,
    "--no-interactive",
    "-n",
    help="Don't ask for confirmation before deleting branches",
)
no_gc_option = typer.Option(
    False,
    "--no-gc",
    help="Skip garbage collection",
)


def parse_protect_option(value: str) -> list[str]:
    """Parse comma-separated protect option into list of branch names."""
    if not value:
        return []
    return [branch.strip() for branch in value.split(",")]


protect_option = typer.Option(
    "",
    "--protect",
    "-p",
    help="Additional protected branches (comma-separated)",
    callback=parse_protect_option,
)


@app.command()
def main(
    dry_run: bool = dry_run_option,
    no_interactive: bool = no_interactive_option,
    no_gc: bool = no_gc_option,
    protect: str = protect_option,
) -> None:
    """Clean up git branches that are gone or merged."""
    # Validate git repository
    validate_git_repo()

    # Load and update configuration
    cfg = config.load_config()
    update_config_from_options(cfg, dry_run, not no_interactive, no_gc, protect)

    # Start cleanup
    console.print("🧹 [blue]Starting git cleanup...[/blue]")

    if cfg.dry_run_by_default:
        console.print("[yellow]DRY RUN: No changes will be made[/yellow]")

    # Update repository state
    if not cfg.dry_run_by_default:
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[blue]{task.description}[/blue]"),
                console=console,
            ) as progress:
                task_id = progress.add_task(
                    "🔄 Updating repository state...",
                    total=None,
                )
                git.fetch_and_prune(
                    progress_callback=lambda msg: progress.update(
                        task_id,
                        description=f"🔄 {msg}",
                    ),
                )
        except git.GitError as e:
            console.print(f"[red]Error updating repository state: {e!s}[/red]")

    # Process branches
    handle_gone_branches(cfg)
    handle_merged_branches(cfg)
    handle_merged_remote_branches(cfg)

    # Optimize repository
    optimize_repository(cfg)

    console.print("\n✨ [green]Cleanup complete![/green]")


if __name__ == "__main__":
    app()
