"""bmadnotion CLI - Command line interface for BMAD to Notion sync."""

from pathlib import Path

import click

from bmadnotion import __version__
from bmadnotion.config import ConfigNotFoundError, TokenNotFoundError, load_config
from bmadnotion.store import Store

# Import NotionClient from marknotion for use in commands
try:
    from marknotion import NotionClient
except ImportError:
    NotionClient = None  # type: ignore


def get_project_root() -> Path:
    """Get the project root (current working directory)."""
    return Path.cwd()


@click.group()
@click.version_option(version=__version__, prog_name="bmadnotion")
def cli():
    """Sync BMAD project artifacts to Notion.

    bmadnotion syncs your BMAD project's planning artifacts and sprint
    tracking to Notion, keeping your documentation and progress in sync.
    """
    pass


@cli.command()
@click.option("--project", "-p", help="Project name")
def init(project: str | None):
    """Initialize bmadnotion configuration.

    Creates a .bmadnotion.yaml configuration file in the current directory.
    """
    click.echo("Initializing bmadnotion...")
    # TODO: Implement init command
    click.echo("Created .bmadnotion.yaml")


@cli.group(invoke_without_command=True)
@click.option("--force", "-f", is_flag=True, help="Force full sync, ignore cache")
@click.option("--dry-run", is_flag=True, help="Preview changes without syncing")
@click.pass_context
def sync(ctx, force: bool, dry_run: bool):
    """Sync artifacts to Notion.

    Without a subcommand, syncs all artifacts (both pages and database).
    """
    ctx.ensure_object(dict)
    ctx.obj["force"] = force
    ctx.obj["dry_run"] = dry_run

    if ctx.invoked_subcommand is None:
        # No subcommand given, sync all
        ctx.invoke(sync_pages, force=force, dry_run=dry_run)
        ctx.invoke(sync_db, force=force, dry_run=dry_run)


@sync.command("pages")
@click.option("--force", "-f", is_flag=True, help="Force full sync, ignore cache")
@click.option("--dry-run", is_flag=True, help="Preview changes without syncing")
def sync_pages(force: bool, dry_run: bool):
    """Sync planning artifacts to Notion Pages.

    Syncs documents like PRD, Architecture, and UX Design to Notion pages.
    """
    from bmadnotion.page_sync import PageSyncEngine

    project_root = get_project_root()

    # Load configuration
    try:
        config = load_config(project_root)
    except ConfigNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    # Check if page sync is enabled
    if not config.page_sync.enabled:
        click.echo("Page sync is disabled in configuration.")
        return

    # Get Notion token
    try:
        token = config.get_notion_token()
    except TokenNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    # Create Notion client
    if NotionClient is None:
        click.echo("Error: marknotion is not installed.", err=True)
        raise SystemExit(1)

    client = NotionClient(token=token)
    store = Store(project_root)
    engine = PageSyncEngine(client, store, config)

    # Perform sync
    mode = "[DRY RUN] " if dry_run else ""
    click.echo(f"{mode}Syncing pages...")

    result = engine.sync(force=force, dry_run=dry_run)

    # Display results
    if dry_run:
        click.echo(f"Would create: {result.created}")
        click.echo(f"Would update: {result.updated}")
        click.echo(f"Would skip: {result.skipped}")
    else:
        click.echo(f"Created: {result.created}")
        click.echo(f"Updated: {result.updated}")
        click.echo(f"Skipped: {result.skipped}")

    if result.failed > 0:
        click.echo(f"Failed: {result.failed}", err=True)
        for error in result.errors:
            click.echo(f"  - {error}", err=True)

    click.echo("Done.")


@sync.command("db")
@click.option("--force", "-f", is_flag=True, help="Force full sync, ignore cache")
@click.option("--dry-run", is_flag=True, help="Preview changes without syncing")
def sync_db(force: bool, dry_run: bool):
    """Sync sprint status to Notion Database.

    Syncs Epics and Stories from sprint-status.yaml to Notion databases.
    """
    mode = "[DRY RUN] " if dry_run else ""
    click.echo(f"{mode}Syncing database...")
    # TODO: Implement database sync
    click.echo("Done.")


@cli.command()
def status():
    """Show sync status.

    Displays the current sync state, showing what's changed locally
    and what needs to be synced to Notion.
    """
    click.echo("Checking sync status...")
    # TODO: Implement status command
    click.echo("All synced.")


@cli.group()
def config():
    """Manage configuration."""
    pass


@config.command("show")
def config_show():
    """Show current configuration."""
    click.echo("Configuration:")
    # TODO: Implement config show
    click.echo("  (not implemented yet)")


if __name__ == "__main__":
    cli()
