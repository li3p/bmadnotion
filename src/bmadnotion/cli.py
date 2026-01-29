"""bmadnotion CLI - Command line interface for BMAD to Notion sync."""

from pathlib import Path

import click
from dotenv import load_dotenv
from notion_client import Client

from bmadnotion import __version__
from bmadnotion.config import ConfigNotFoundError, TokenNotFoundError, load_config
from bmadnotion.store import Store

# Import NotionClient from marknotion for use in commands
try:
    from marknotion import NotionClient
except ImportError:
    NotionClient = None  # type: ignore

# Load .env file if present (supports NOTION_TOKEN in .env)
load_dotenv()


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


def _detect_bmad_project(project_root: Path) -> dict | None:
    """Detect BMAD project configuration.

    Returns:
        Dict with project info or None if not a BMAD project.
    """
    import yaml

    bmad_config_path = project_root / "_bmad" / "bmm" / "config.yaml"
    if not bmad_config_path.exists():
        return None

    with open(bmad_config_path) as f:
        bmad_config = yaml.safe_load(f) or {}

    # Resolve paths
    def resolve_path(p: str) -> Path:
        return Path(p.replace("{project-root}", str(project_root)))

    planning_artifacts = resolve_path(
        bmad_config.get("planning_artifacts", "_bmad-output/planning-artifacts")
    )
    implementation_artifacts = resolve_path(
        bmad_config.get("implementation_artifacts", "_bmad-output/implementation-artifacts")
    )

    return {
        "project_name": bmad_config.get("project_name", project_root.name),
        "planning_artifacts": planning_artifacts,
        "implementation_artifacts": implementation_artifacts,
    }


def _scan_planning_artifacts(planning_dir: Path) -> list[dict]:
    """Scan planning artifacts directory for documents to sync."""
    documents = []
    artifact_patterns = [
        ("prd.md", "PRD"),
        ("architecture.md", "Architecture"),
        ("ux-design-specification.md", "UX Design"),
        ("epics.md", "Epics"),
    ]

    for filename, title in artifact_patterns:
        path = planning_dir / filename
        if path.exists():
            documents.append({"path": filename, "title": title})

    # Also scan for product-brief-*.md
    for brief in planning_dir.glob("product-brief-*.md"):
        documents.append({"path": brief.name, "title": "Product Brief"})

    return documents


def _auto_detect_databases(token: str) -> dict[str, str]:
    """Auto-detect database IDs from Notion."""
    import re

    if NotionClient is None:
        return {}

    click.echo("Searching for databases in Notion...")
    client = NotionClient(token=token, on_retry=None)

    db_ids = {}
    for db_name in ["Projects", "Sprints", "Tasks"]:
        results = client.search(db_name, object_type="database")
        for result in results:
            title_parts = result.get("title", [])
            title = "".join(t.get("plain_text", "") for t in title_parts)
            if title.lower() == db_name.lower():
                url = result.get("url", "")
                match = re.search(r"([a-f0-9]{32})", url, re.IGNORECASE)
                if match:
                    h = match.group(1).lower()
                    formatted_id = f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"
                    db_ids[db_name.lower()] = formatted_id
                break

    return db_ids


@cli.command()
@click.option("--project", "-p", help="Project name (overrides auto-detected name)")
@click.option("--skip-notion", is_flag=True, help="Skip Notion setup (config file only)")
@click.option("--force", "-f", is_flag=True, help="Overwrite existing config")
def init(project: str | None, skip_notion: bool, force: bool):
    """Initialize bmadnotion for a BMAD project.

    This command performs a complete setup:
    1. Detects BMAD project structure
    2. Scans for planning artifacts and sprint status
    3. Auto-detects Notion database IDs
    4. Sets up required database fields
    5. Creates Project row in Notion

    Requires: _bmad/bmm/config.yaml (BMAD project)
    """
    import os

    import yaml

    project_root = get_project_root()
    config_path = project_root / ".bmadnotion.yaml"

    # Step 1: Detect BMAD project
    click.echo("Detecting BMAD project...")
    bmad_info = _detect_bmad_project(project_root)

    if not bmad_info:
        click.secho("Error: Not a BMAD project.", fg="red", err=True)
        click.echo("Required: _bmad/bmm/config.yaml")
        click.echo("Run 'bmad-installer init' to initialize a BMAD project first.")
        raise SystemExit(1)

    project_name = project or bmad_info["project_name"]
    planning_dir = bmad_info["planning_artifacts"]
    impl_dir = bmad_info["implementation_artifacts"]

    click.echo(f"  Project: {project_name}")
    click.echo(f"  Planning: {planning_dir}")
    click.echo(f"  Implementation: {impl_dir}")

    # Step 2: Scan artifacts
    click.echo("")
    click.echo("Scanning artifacts...")

    documents = _scan_planning_artifacts(planning_dir)
    click.echo(f"  Found {len(documents)} planning documents")
    for doc in documents:
        click.echo(f"    - {doc['path']}")

    sprint_status = impl_dir / "sprint-status.yaml"
    has_sprint_status = sprint_status.exists()
    if has_sprint_status:
        click.echo("  Found sprint-status.yaml")
    else:
        click.secho("  No sprint-status.yaml (run sprint-planning workflow)", fg="yellow")

    # Check existing config
    if config_path.exists() and not force:
        click.echo("")
        click.secho(f"Config already exists: {config_path}", fg="yellow")
        if not click.confirm("Overwrite?"):
            click.echo("Aborted.")
            return

    # Step 3: Get Notion token
    click.echo("")
    token = os.environ.get("NOTION_TOKEN")

    if not token and not skip_notion:
        click.echo("NOTION_TOKEN not found in environment.")
        token = click.prompt("Enter your Notion integration token", hide_input=True, default="")
        if token:
            # Offer to save to .env
            env_path = project_root / ".env"
            if click.confirm("Save token to .env file?"):
                with open(env_path, "a") as f:
                    f.write(f"\nNOTION_TOKEN={token}\n")
                click.echo(f"  Saved to {env_path}")

    # Step 4: Auto-detect databases
    db_ids = {}
    if token and not skip_notion:
        db_ids = _auto_detect_databases(token)
        click.echo("")
        click.echo("Found databases:")
        for name in ["projects", "sprints", "tasks"]:
            db_id = db_ids.get(name)
            if db_id:
                click.echo(f"  {name.capitalize()}: {db_id}")
            else:
                click.secho(f"  {name.capitalize()}: Not found", fg="yellow")

        if not any(db_ids.values()):
            click.echo("")
            click.secho("No databases found. Make sure your integration has access.", fg="yellow")

    # Step 5: Prompt for project name confirmation
    click.echo("")
    if not project:
        confirmed_name = click.prompt("Project name", default=project_name)
        project_name = confirmed_name

    # Step 6: Generate config
    click.echo("")
    click.echo("Creating configuration...")

    config_data = {
        "project": project_name,
        "notion": {
            "token_env": "NOTION_TOKEN",
        },
        "paths": {
            "planning_artifacts": str(planning_dir.relative_to(project_root)),
            "implementation_artifacts": str(impl_dir.relative_to(project_root)),
            "sprint_status": str((impl_dir / "sprint-status.yaml").relative_to(project_root)),
        },
        "page_sync": {
            "enabled": len(documents) > 0,
            "documents": [
                {"path": d["path"], "title": f"{d['title']} - {{project}}"}
                for d in documents
            ],
        },
        "database_sync": {
            "enabled": has_sprint_status,
            "projects": {
                "database_id": db_ids.get("projects", ""),
                "key_property": "BMADProject",
                "name_property": "Project name",
            },
            "sprints": {
                "database_id": db_ids.get("sprints", ""),
                "key_property": "BMADEpic",
                "status_mapping": {
                    "backlog": "Not Started",
                    "in-progress": "In Progress",
                    "done": "Done",
                },
            },
            "tasks": {
                "database_id": db_ids.get("tasks", ""),
                "key_property": "BMADStory",
                "status_mapping": {
                    "backlog": "Backlog",
                    "ready-for-dev": "Ready",
                    "in-progress": "In Progress",
                    "review": "Review",
                    "done": "Done",
                },
            },
        },
    }

    with open(config_path, "w") as f:
        yaml.dump(config_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    click.echo(f"  Created {config_path}")

    # Step 7: Setup database fields
    if token and db_ids and not skip_notion:
        click.echo("")
        click.echo("Setting up database fields...")

        from bmadnotion.schema import setup_all_databases

        try:
            cfg = load_config(project_root)
            notion_client = Client(auth=token)
            results = setup_all_databases(notion_client, cfg)

            if results:
                for db_type, fields in results.items():
                    click.echo(f"  Added to {db_type}: {', '.join(fields)}")
            else:
                click.echo("  All fields already exist")
        except Exception as e:
            click.secho(f"  Warning: {e}", fg="yellow")

    # Step 8: Create Project row
    if token and db_ids.get("projects") and not skip_notion:
        click.echo("")
        click.echo("Creating Project row...")

        try:
            notion_client = Client(auth=token)
            store = Store(project_root)

            # Get data_source_id from database (required for 2025-09-03 API)
            db = notion_client.databases.retrieve(database_id=db_ids["projects"])
            data_sources = db.get("data_sources", [])
            if not data_sources:
                raise ValueError("No data sources found in Projects database")
            ds_id = data_sources[0]["id"]

            # Query using data_sources endpoint
            response = notion_client.data_sources.query(
                data_source_id=ds_id,
                filter={
                    "property": "BMADProject",
                    "rich_text": {"equals": project_name},
                },
            )

            if response.get("results"):
                page_id = response["results"][0]["id"]
                click.echo(f"  Project already exists: {project_name}")
            else:
                page = notion_client.pages.create(
                    parent={"database_id": db_ids["projects"]},
                    properties={
                        "Project name": {"title": [{"text": {"content": project_name}}]},
                        "BMADProject": {"rich_text": [{"text": {"content": project_name}}]},
                    },
                )
                page_id = page["id"]
                click.echo(f"  Created Project: {project_name}")

            # Save to store
            from bmadnotion.models import DbSyncState

            state = DbSyncState(
                local_key=f"project:{project_name}",
                entity_type="project",
                notion_page_id=page_id,
            )
            store.save_db_state(state)

        except Exception as e:
            click.secho(f"  Warning: Could not create project: {e}", fg="yellow")

    # Done
    click.echo("")
    click.secho("Setup complete!", fg="green")
    click.echo("")
    click.echo("Next steps:")
    if not token or skip_notion:
        click.echo("  1. Set NOTION_TOKEN environment variable")
        click.echo("  2. Update database IDs in .bmadnotion.yaml")
        click.echo("  3. Run 'bmad setup-db' to add sync key fields")
        click.echo("  4. Run 'bmad sync' to sync your project")
    else:
        click.echo("  Run 'bmad sync' to sync your project")


def _get_or_create_project(
    notion_client: Client,
    store: Store,
    config,
    dry_run: bool = False,
) -> str | None:
    """Get or create the Project row and return its page ID.

    Args:
        notion_client: Official notion-client instance (for database operations).
        store: SQLite store for tracking sync state.
        config: Loaded configuration.
        dry_run: If True, don't create anything.

    Returns:
        Notion page ID of the Project row, or None if Projects database not configured.
    """
    from bmadnotion.project_sync import ProjectSyncEngine

    db_config = config.database_sync.projects
    if not db_config.database_id:
        return None

    engine = ProjectSyncEngine(notion_client, store, config)
    page_id, was_created = engine.get_or_create_project(dry_run=dry_run)

    if was_created and not dry_run:
        click.echo(f"Created Project row: {config.project}")
    elif was_created:
        click.echo(f"[DRY RUN] Would create Project row: {config.project}")

    return page_id


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
        _sync_all(force=force, dry_run=dry_run)


def _check_gitignore(project_root: Path) -> bool:
    """Check if .bmadnotion/ is in .gitignore."""
    gitignore = project_root / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text()
        return ".bmadnotion" in content or ".bmadnotion/" in content
    return False


def _sync_all(force: bool, dry_run: bool):
    """Sync all artifacts (pages and database) with shared Project context."""
    from bmadnotion.db_sync import DbSyncEngine
    from bmadnotion.page_sync import PageSyncEngine
    from bmadnotion.scanner import BMADScanner, SprintStatusNotFoundError

    project_root = get_project_root()

    # Load configuration
    try:
        config = load_config(project_root)
    except ConfigNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    # Get Notion token
    try:
        token = config.get_notion_token()
    except TokenNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    # Create clients
    if NotionClient is None:
        click.echo("Error: marknotion is not installed.", err=True)
        raise SystemExit(1)

    marknotion_client = NotionClient(token=token, on_retry=None)
    notion_client = Client(auth=token)
    store = Store(project_root)

    mode = "[DRY RUN] " if dry_run else ""

    # Show sync info header
    click.echo(f"Project: {config.project}")
    click.echo(f"State DB: {store.db_path}")
    if not _check_gitignore(project_root):
        click.secho("Note: Add '.bmadnotion/' to .gitignore", fg="yellow")
    click.echo("")

    # Scan and show what will be synced
    scanner = BMADScanner(config)

    if config.page_sync.enabled:
        documents = scanner.scan_documents()
        pending_docs = []
        changed_docs = []
        for doc in documents:
            state = store.get_page_state(doc.path.name)
            if state is None:
                pending_docs.append(doc.path.name)
            elif state.content_hash != doc.content_hash:
                changed_docs.append(doc.path.name)

        click.echo(f"Pages: {len(documents)} found")
        if pending_docs:
            click.echo(f"  New: {', '.join(pending_docs)}")
        if changed_docs:
            click.echo(f"  Changed: {', '.join(changed_docs)}")
        if not pending_docs and not changed_docs and not force:
            click.echo("  All up to date")

    if config.database_sync.enabled:
        try:
            epics, stories = scanner.scan_sprint_status()
            pending_epics = sum(1 for e in epics if not store.get_db_state(e.key))
            pending_stories = sum(1 for s in stories if not store.get_db_state(s.key))
            click.echo(f"Epics: {len(epics)} found ({pending_epics} new)")
            click.echo(f"Stories: {len(stories)} found ({pending_stories} new)")
        except SprintStatusNotFoundError:
            click.echo("Sprint status: Not found")

    click.echo("")

    # Get or create Project row first
    project_page_id = None
    if config.database_sync.enabled and config.database_sync.projects.database_id:
        click.echo(f"{mode}Ensuring Project row exists...")
        project_page_id = _get_or_create_project(notion_client, store, config, dry_run)

    # Sync pages
    if config.page_sync.enabled:
        click.echo(f"{mode}Syncing pages...")
        page_engine = PageSyncEngine(marknotion_client, store, config)
        page_result = page_engine.sync(
            force=force,
            dry_run=dry_run,
            project_page_id=project_page_id,
        )

        if dry_run:
            click.echo(f"  Would create: {page_result.created}")
            click.echo(f"  Would update: {page_result.updated}")
            click.echo(f"  Would skip: {page_result.skipped}")
        else:
            click.echo(f"  Created: {page_result.created}")
            click.echo(f"  Updated: {page_result.updated}")
            click.echo(f"  Skipped: {page_result.skipped}")

        if page_result.failed > 0:
            click.echo(f"  Failed: {page_result.failed}", err=True)
            for error in page_result.errors:
                click.echo(f"    - {error}", err=True)

    # Sync database
    if config.database_sync.enabled:
        click.echo(f"{mode}Syncing database...")
        db_engine = DbSyncEngine(marknotion_client, store, config)

        try:
            db_result = db_engine.sync(
                force=force,
                dry_run=dry_run,
                project_page_id=project_page_id,
            )

            click.echo("")
            click.echo("Epics (Sprints):")
            if dry_run:
                click.echo(f"  Would create: {db_result.epics_created}")
                click.echo(f"  Would update: {db_result.epics_updated}")
                click.echo(f"  Would skip: {db_result.epics_skipped}")
            else:
                click.echo(f"  Created: {db_result.epics_created}")
                click.echo(f"  Updated: {db_result.epics_updated}")
                click.echo(f"  Skipped: {db_result.epics_skipped}")

            click.echo("")
            click.echo("Stories (Tasks):")
            if dry_run:
                click.echo(f"  Would create: {db_result.stories_created}")
                click.echo(f"  Would update: {db_result.stories_updated}")
                click.echo(f"  Would skip: {db_result.stories_skipped}")
            else:
                click.echo(f"  Created: {db_result.stories_created}")
                click.echo(f"  Updated: {db_result.stories_updated}")
                click.echo(f"  Skipped: {db_result.stories_skipped}")

            if db_result.epics_failed > 0 or db_result.stories_failed > 0:
                click.echo("")
                click.echo(
                    f"Failed: {db_result.epics_failed + db_result.stories_failed}",
                    err=True,
                )
                for error in db_result.errors:
                    click.echo(f"  - {error}", err=True)

        except SprintStatusNotFoundError as e:
            click.echo(f"  Warning: {e}")

    click.echo("")
    click.echo("Done.")


@sync.command("pages")
@click.option("--force", "-f", is_flag=True, help="Force full sync, ignore cache")
@click.option("--dry-run", is_flag=True, help="Preview changes without syncing")
def sync_pages(force: bool, dry_run: bool):
    """Sync planning artifacts to Notion Pages.

    Syncs documents like PRD, Architecture, and UX Design to Notion pages.
    Documents are created as sub-pages of the Project row if configured.
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

    # Create clients
    if NotionClient is None:
        click.echo("Error: marknotion is not installed.", err=True)
        raise SystemExit(1)

    marknotion_client = NotionClient(token=token)
    notion_client = Client(auth=token)
    store = Store(project_root)

    mode = "[DRY RUN] " if dry_run else ""

    # Get or create Project row
    project_page_id = _get_or_create_project(notion_client, store, config, dry_run)

    # Progress callback
    def on_progress(doc_name: str, status: str, current: int, total: int) -> None:
        symbol = {"created": "✓", "updated": "✓", "skipped": "○", "failed": "✗"}.get(status, "?")
        click.echo(f"  [{current}/{total}] {symbol} {doc_name} ({status})")

    # Perform sync
    click.echo(f"{mode}Syncing pages...")
    engine = PageSyncEngine(marknotion_client, store, config)
    result = engine.sync(
        force=force,
        dry_run=dry_run,
        project_page_id=project_page_id,
        on_progress=on_progress,
    )

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
    Stories are linked to both their Epic (Sprint) and the Project.
    """
    from bmadnotion.db_sync import DbSyncEngine
    from bmadnotion.scanner import SprintStatusNotFoundError

    project_root = get_project_root()

    # Load configuration
    try:
        config = load_config(project_root)
    except ConfigNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    # Check if database sync is enabled
    if not config.database_sync.enabled:
        click.echo("Database sync is disabled in configuration.")
        return

    # Get Notion token
    try:
        token = config.get_notion_token()
    except TokenNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    # Create clients
    if NotionClient is None:
        click.echo("Error: marknotion is not installed.", err=True)
        raise SystemExit(1)

    marknotion_client = NotionClient(token=token)
    notion_client = Client(auth=token)
    store = Store(project_root)

    mode = "[DRY RUN] " if dry_run else ""

    # Get or create Project row
    project_page_id = _get_or_create_project(notion_client, store, config, dry_run)

    # Progress callback
    def on_progress(item_type: str, key: str, status: str, current: int, total: int) -> None:
        symbol = {"created": "✓", "updated": "✓", "skipped": "○", "failed": "✗"}.get(status, "?")
        prefix = "Epic" if item_type == "epic" else "Story"
        click.echo(f"  [{current}/{total}] {symbol} {prefix}: {key} ({status})")

    # Perform sync
    click.echo(f"{mode}Syncing database...")
    engine = DbSyncEngine(marknotion_client, store, config)

    try:
        result = engine.sync(
            force=force,
            dry_run=dry_run,
            project_page_id=project_page_id,
            on_progress=on_progress,
        )
    except SprintStatusNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    # Display results
    click.echo("")
    click.echo("Epics (Sprints):")
    if dry_run:
        click.echo(f"  Would create: {result.epics_created}")
        click.echo(f"  Would update: {result.epics_updated}")
        click.echo(f"  Would skip: {result.epics_skipped}")
    else:
        click.echo(f"  Created: {result.epics_created}")
        click.echo(f"  Updated: {result.epics_updated}")
        click.echo(f"  Skipped: {result.epics_skipped}")

    click.echo("")
    click.echo("Stories (Tasks):")
    if dry_run:
        click.echo(f"  Would create: {result.stories_created}")
        click.echo(f"  Would update: {result.stories_updated}")
        click.echo(f"  Would skip: {result.stories_skipped}")
    else:
        click.echo(f"  Created: {result.stories_created}")
        click.echo(f"  Updated: {result.stories_updated}")
        click.echo(f"  Skipped: {result.stories_skipped}")

    if result.epics_failed > 0 or result.stories_failed > 0:
        click.echo("")
        click.echo(f"Failed: {result.epics_failed + result.stories_failed}", err=True)
        for error in result.errors:
            click.echo(f"  - {error}", err=True)

    click.echo("")
    click.echo("Done.")


@cli.command()
def status():
    """Show sync status.

    Displays the current sync state, showing what's changed locally
    and what needs to be synced to Notion.
    """
    from bmadnotion.scanner import BMADScanner, SprintStatusNotFoundError

    project_root = get_project_root()

    # Load configuration
    try:
        config = load_config(project_root)
    except ConfigNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    store = Store(project_root)
    scanner = BMADScanner(config)

    click.echo(f"Project: {config.project}")
    click.echo("")

    # Page sync status
    if config.page_sync.enabled:
        click.echo("=== Page Sync (Planning Artifacts) ===")
        documents = scanner.scan_documents()

        synced = 0
        pending = 0
        changed = 0

        for doc in documents:
            state = store.get_page_state(doc.path.name)
            if state is None:
                pending += 1
                click.echo(f"  [NEW] {doc.path.name}")
            elif state.content_hash != doc.content_hash:
                changed += 1
                click.echo(f"  [CHANGED] {doc.path.name}")
            else:
                synced += 1

        if synced > 0 and pending == 0 and changed == 0:
            click.echo(f"  All {synced} documents synced")
        else:
            click.echo(f"\n  Synced: {synced}, Pending: {pending}, Changed: {changed}")
        click.echo("")
    else:
        click.echo("=== Page Sync: Disabled ===")
        click.echo("")

    # Database sync status
    if config.database_sync.enabled:
        click.echo("=== Database Sync (Sprint Status) ===")

        try:
            epics, stories = scanner.scan_sprint_status()

            epics_synced = 0
            epics_pending = 0
            epics_changed = 0

            for epic in epics:
                state = store.get_db_state(epic.key)
                if state is None:
                    epics_pending += 1
                elif epic.mtime and state.last_synced_mtime != epic.mtime:
                    epics_changed += 1
                else:
                    epics_synced += 1

            stories_synced = 0
            stories_pending = 0
            stories_changed = 0

            for story in stories:
                state = store.get_db_state(story.key)
                if state is None:
                    stories_pending += 1
                elif story.content_hash and state.content_hash != story.content_hash:
                    stories_changed += 1
                elif story.mtime and state.last_synced_mtime != story.mtime:
                    stories_changed += 1
                else:
                    stories_synced += 1

            click.echo(
                f"  Epics:   Synced: {epics_synced}, "
                f"Pending: {epics_pending}, Changed: {epics_changed}"
            )
            click.echo(
                f"  Stories: Synced: {stories_synced}, "
                f"Pending: {stories_pending}, Changed: {stories_changed}"
            )

            all_synced = (
                epics_pending == 0
                and epics_changed == 0
                and stories_pending == 0
                and stories_changed == 0
            )
            if all_synced:
                click.echo("\n  All items up to date")

        except SprintStatusNotFoundError:
            click.echo("  No sprint-status.yaml found")

        click.echo("")
    else:
        click.echo("=== Database Sync: Disabled ===")
        click.echo("")


@cli.group()
def config():
    """Manage configuration."""
    pass


@config.command("show")
def config_show():
    """Show current configuration."""

    project_root = get_project_root()

    try:
        config = load_config(project_root)
    except ConfigNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    click.echo(f"Project: {config.project}")
    click.echo(f"Config file: {project_root / '.bmadnotion.yaml'}")
    click.echo("")

    click.echo("Notion:")
    click.echo(f"  Token env: {config.notion.token_env}")
    click.echo(f"  Workspace page: {config.notion.workspace_page_id}")
    click.echo("")

    click.echo("Page Sync:")
    click.echo(f"  Enabled: {config.page_sync.enabled}")
    if config.page_sync.enabled:
        click.echo(f"  Parent page: {config.page_sync.parent_page_id}")
        click.echo(f"  Documents: {len(config.page_sync.documents)}")
        for doc in config.page_sync.documents:
            click.echo(f"    - {doc.path}: {doc.title}")
    click.echo("")

    click.echo("Database Sync:")
    click.echo(f"  Enabled: {config.database_sync.enabled}")
    if config.database_sync.enabled:
        click.echo(f"  Projects DB: {config.database_sync.projects.database_id}")
        click.echo(f"  Sprints DB: {config.database_sync.sprints.database_id}")
        click.echo(f"  Tasks DB: {config.database_sync.tasks.database_id}")


@config.command("set-db")
@click.option("--projects", help="Projects database ID")
@click.option("--sprints", help="Sprints database ID")
@click.option("--tasks", help="Tasks database ID")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def config_set_db(
    projects: str | None,
    sprints: str | None,
    tasks: str | None,
    yes: bool,
):
    """Update database IDs in configuration.

    If no IDs are provided, auto-detects from Notion.

    Examples:
        bmad config set-db                    # Auto-detect from Notion
        bmad config set-db --projects abc123  # Set specific ID
        bmad config set-db -y                 # Auto-detect, skip confirmation
    """
    import yaml

    project_root = get_project_root()
    config_path = project_root / ".bmadnotion.yaml"

    if not config_path.exists():
        click.echo("Error: .bmadnotion.yaml not found. Run 'bmad init' first.", err=True)
        raise SystemExit(1)

    # If any ID is provided manually, use those
    if projects or sprints or tasks:
        db_ids = {
            "projects": projects,
            "sprints": sprints,
            "tasks": tasks,
        }
    else:
        # Auto-detect from Notion
        try:
            cfg = load_config(project_root)
            token = cfg.get_notion_token()
        except (ConfigNotFoundError, TokenNotFoundError) as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(1)

        db_ids = _auto_detect_databases(token)

        # Show results
        click.echo("")
        click.echo("Found databases:")
        for name in ["projects", "sprints", "tasks"]:
            db_id = db_ids.get(name)
            status = db_id if db_id else click.style("Not found", fg="yellow")
            click.echo(f"  {name.capitalize()}: {status}")

        if not any(db_ids.values()):
            click.echo("")
            click.echo("No databases found. Make sure your integration has access to them.")
            raise SystemExit(1)

        # Confirm
        if not yes:
            click.echo("")
            if not click.confirm("Update .bmadnotion.yaml with these IDs?"):
                click.echo("Aborted.")
                return

    # Update config file
    with open(config_path) as f:
        config_content = yaml.safe_load(f)

    if "database_sync" not in config_content:
        config_content["database_sync"] = {"enabled": True}

    db_sync = config_content["database_sync"]

    for name in ["projects", "sprints", "tasks"]:
        if db_ids.get(name):
            if name not in db_sync:
                db_sync[name] = {}
            db_sync[name]["database_id"] = db_ids[name]

    with open(config_path, "w") as f:
        yaml.dump(config_content, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    click.echo("")
    click.echo(f"Updated {config_path}")


@cli.command("setup-db")
def setup_db():
    """Set up required fields in Notion databases.

    Adds sync key fields (BMADProject, BMADEpic, BMADStory) to the configured
    databases if they don't already exist.
    """
    from bmadnotion.schema import setup_all_databases

    project_root = get_project_root()

    # Load configuration
    try:
        config = load_config(project_root)
    except ConfigNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    # Check if database sync is enabled
    if not config.database_sync.enabled:
        click.echo("Database sync is disabled in configuration.")
        return

    # Get Notion token
    try:
        token = config.get_notion_token()
    except TokenNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    click.echo("Setting up database fields...")

    # Create Notion client
    client = Client(auth=token)

    try:
        results = setup_all_databases(client, config)

        if not results:
            click.echo("All required fields already exist.")
        else:
            for db_type, fields in results.items():
                click.echo(f"  Added to {db_type}: {', '.join(fields)}")

        # Remind about Status property (cannot be added via API)
        click.echo()
        click.echo("Note: If your Sprints database doesn't have a 'Status' property,")
        click.echo("      please add it manually in Notion UI (API limitation).")

        click.echo("Done.")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
