"""bmadnotion CLI - Command line interface for BMAD to Notion sync."""

import click

from bmadnotion import __version__


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
    mode = "[DRY RUN] " if dry_run else ""
    click.echo(f"{mode}Syncing pages...")
    # TODO: Implement page sync
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
