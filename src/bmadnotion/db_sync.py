"""Database sync engine for syncing sprint data to Notion databases."""

from __future__ import annotations

from typing import TYPE_CHECKING

from marknotion import markdown_to_blocks

from bmadnotion.config import Config
from bmadnotion.models import DbSyncResult, DbSyncState, Epic, Story
from bmadnotion.scanner import BMADScanner
from bmadnotion.store import Store

if TYPE_CHECKING:
    from collections.abc import Callable

    from marknotion import NotionClient as MarknotionClient
    from notion_client import Client as OfficialClient


class DbSyncEngine:
    """Engine for syncing sprint data to Notion databases.

    Syncs Epics to Sprints database and Stories to Tasks database.
    Stories are linked to both their Epic (Sprint) and the Project.
    Uses status mapping from config and tracks sync state in SQLite.
    """

    def __init__(
        self,
        client: "MarknotionClient",
        store: Store,
        config: Config,
        notion_client: "OfficialClient | None" = None,
    ):
        """Initialize the database sync engine.

        Args:
            client: Marknotion client (for block operations).
            store: SQLite store for tracking sync state.
            config: Loaded configuration.
            notion_client: Official notion-client (for database operations).
        """
        self.client = client
        self.notion_client = notion_client
        self.store = store
        self.config = config
        self.scanner = BMADScanner(config)

    def sync(
        self,
        force: bool = False,
        dry_run: bool = False,
        project_page_id: str | None = None,
        on_progress: "Callable[[str, str, str, int, int], None] | None" = None,
        filter_key: str | None = None,
    ) -> DbSyncResult:
        """Sync sprint data to Notion databases.

        Args:
            force: If True, sync all items regardless of changes.
            dry_run: If True, report what would be done without making changes.
            project_page_id: Notion page ID of the Project row (for relation).
            on_progress: Callback (type, key, status, current, total) called after each item.
            filter_key: If provided, only sync the epic or story with this key.

        Returns:
            DbSyncResult with statistics about the sync operation.
        """
        # Check if database sync is enabled
        if not self.config.database_sync.enabled:
            return DbSyncResult()

        # Scan sprint status
        epics, stories = self.scanner.scan_sprint_status()

        # Filter stories if require_story_file is enabled
        if self.config.database_sync.tasks.require_story_file:
            stories = [s for s in stories if s.file_path is not None]

        # Filter to specific key if requested
        if filter_key:
            if filter_key.startswith("epic-"):
                epics = [e for e in epics if e.key == filter_key]
                stories = []  # Don't sync stories when filtering to a specific epic
            else:
                # Assume it's a story key
                stories = [s for s in stories if s.key == filter_key]
                # Still need parent epic for relation
                if stories:
                    epic_keys = {s.epic_key for s in stories}
                    epics = [e for e in epics if e.key in epic_keys]

        total_epics = len(epics)
        total_stories = len(stories)

        result = DbSyncResult()

        # First sync epics (needed for story relations)
        epic_id_map: dict[str, str] = {}  # epic_key -> notion_page_id
        for i, epic in enumerate(epics, 1):
            try:
                action, page_id = self._sync_epic(epic, force=force, dry_run=dry_run)
                epic_id_map[epic.key] = page_id
                if action == "created":
                    result.epics_created += 1
                elif action == "updated":
                    result.epics_updated += 1
                elif action == "skipped":
                    result.epics_skipped += 1
                if on_progress:
                    on_progress("epic", epic.key, action, i, total_epics)
            except Exception as e:
                result.epics_failed += 1
                result.errors.append(f"Failed to sync epic {epic.key}: {e}")
                if on_progress:
                    on_progress("epic", epic.key, "failed", i, total_epics)

        # Then sync stories (with relations to epics and project)
        for i, story in enumerate(stories, 1):
            try:
                epic_page_id = epic_id_map.get(story.epic_key)
                action = self._sync_story(
                    story,
                    epic_page_id=epic_page_id,
                    project_page_id=project_page_id,
                    force=force,
                    dry_run=dry_run,
                )
                if action == "created":
                    result.stories_created += 1
                elif action == "updated":
                    result.stories_updated += 1
                elif action == "skipped":
                    result.stories_skipped += 1
                if on_progress:
                    on_progress("story", story.key, action, i, total_stories)
            except Exception as e:
                result.stories_failed += 1
                result.errors.append(f"Failed to sync story {story.key}: {e}")
                if on_progress:
                    on_progress("story", story.key, "failed", i, total_stories)

        return result

    def _sync_epic(
        self, epic: Epic, force: bool, dry_run: bool
    ) -> tuple[str, str]:
        """Sync a single epic.

        Args:
            epic: Epic to sync.
            force: Force sync regardless of changes.
            dry_run: Don't make actual changes.

        Returns:
            Tuple of (action, notion_page_id) where action is "created", "updated", or "skipped".
        """
        # Check existing state
        state = self.store.get_db_state(epic.key)

        # For epics, we use mtime to detect changes (no content hash)
        mtime_changed = (
            state is not None
            and epic.mtime
            and state.last_synced_mtime != epic.mtime
        )
        needs_sync = force or state is None or mtime_changed

        if not needs_sync and state:
            return ("skipped", state.notion_page_id)

        # Get property names from config
        sprints_config = self.config.database_sync.sprints
        name_property = sprints_config.name_property
        status_property = sprints_config.status_property
        key_property = sprints_config.key_property

        # Build properties
        properties = {
            name_property: {"title": [{"text": {"content": epic.title}}]},
            key_property: {"rich_text": [{"text": {"content": epic.key}}]},
        }

        # Only add status if status_property is configured
        if status_property:
            mapped_status = sprints_config.status_mapping.get(epic.status, epic.status)
            properties[status_property] = {"status": {"name": mapped_status}}

        if dry_run:
            # Return a placeholder ID for dry run
            return ("created" if state is None else "updated", f"dry-run-{epic.key}")

        database_id = self.config.database_sync.sprints.database_id
        if not database_id:
            raise ValueError("Sprints database_id not configured")

        if state is None:
            # Create new entry
            page = self.client.create_database_entry(
                database_id=database_id,
                properties=properties,
            )
            page_id = page["id"]

            # Save state
            self.store.save_db_state(DbSyncState(
                local_key=epic.key,
                entity_type="epic",
                notion_page_id=page_id,
                last_synced_mtime=epic.mtime,
            ))

            return ("created", page_id)
        else:
            # Update existing entry
            page_id = state.notion_page_id

            self.client.update_database_entry(
                page_id=page_id,
                properties=properties,
            )

            # Update state
            self.store.save_db_state(DbSyncState(
                local_key=epic.key,
                entity_type="epic",
                notion_page_id=page_id,
                last_synced_mtime=epic.mtime,
            ))

            return ("updated", page_id)

    def _sync_story(
        self,
        story: Story,
        epic_page_id: str | None,
        project_page_id: str | None,
        force: bool,
        dry_run: bool,
    ) -> str:
        """Sync a single story.

        Args:
            story: Story to sync.
            epic_page_id: Notion page ID of the parent epic (for Sprint relation).
            project_page_id: Notion page ID of the project (for Project relation).
            force: Force sync regardless of changes.
            dry_run: Don't make actual changes.

        Returns:
            Action taken: "created", "updated", or "skipped".
        """
        # Check existing state
        state = self.store.get_db_state(story.key)

        # For stories, use content hash if available, otherwise mtime
        if story.content_hash:
            hash_changed = (
                state is not None and state.content_hash != story.content_hash
            )
            needs_sync = force or state is None or hash_changed
        else:
            mtime_changed = (
                state is not None
                and story.mtime
                and state.last_synced_mtime != story.mtime
            )
            needs_sync = force or state is None or mtime_changed

        if not needs_sync:
            return "skipped"

        # Get property names from config
        tasks_config = self.config.database_sync.tasks
        name_property = tasks_config.name_property
        status_property = tasks_config.status_property
        key_property = tasks_config.key_property

        # Map status
        mapped_status = tasks_config.status_mapping.get(story.status, story.status)

        # Build properties
        properties = {
            name_property: {"title": [{"text": {"content": story.title}}]},
            status_property: {"status": {"name": mapped_status}},
            key_property: {"rich_text": [{"text": {"content": story.key}}]},
        }

        # Add Sprint relation if epic_page_id is available
        if epic_page_id:
            properties["Sprint"] = {"relation": [{"id": epic_page_id}]}

        # Add Project relation if project_page_id is available
        if project_page_id:
            properties["Project"] = {"relation": [{"id": project_page_id}]}

        if dry_run:
            return "created" if state is None else "updated"

        database_id = self.config.database_sync.tasks.database_id
        if not database_id:
            raise ValueError("Tasks database_id not configured")

        if state is None:
            # Create new entry
            page = self.client.create_database_entry(
                database_id=database_id,
                properties=properties,
            )
            page_id = page["id"]

            # Add content blocks if story has content
            if story.content:
                blocks = markdown_to_blocks(story.content)
                self.client.append_blocks(page_id, blocks)

            # Save state
            self.store.save_db_state(DbSyncState(
                local_key=story.key,
                entity_type="story",
                notion_page_id=page_id,
                last_synced_mtime=story.mtime,
                content_hash=story.content_hash,
            ))

            return "created"
        else:
            # Update existing entry
            page_id = state.notion_page_id

            self.client.update_database_entry(
                page_id=page_id,
                properties=properties,
            )

            # Update content if story has content
            if story.content:
                self.client.clear_page_content(page_id)
                blocks = markdown_to_blocks(story.content)
                self.client.append_blocks(page_id, blocks)

            # Update state
            self.store.save_db_state(DbSyncState(
                local_key=story.key,
                entity_type="story",
                notion_page_id=page_id,
                last_synced_mtime=story.mtime,
                content_hash=story.content_hash,
            ))

            return "updated"
