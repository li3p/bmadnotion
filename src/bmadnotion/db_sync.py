"""Database sync engine for syncing sprint data to Notion databases."""

from __future__ import annotations

from marknotion import markdown_to_blocks

from bmadnotion.config import Config
from bmadnotion.models import DbSyncResult, DbSyncState, Epic, Story
from bmadnotion.scanner import BMADScanner
from bmadnotion.store import Store


class DbSyncEngine:
    """Engine for syncing sprint data to Notion databases.

    Syncs Epics to Sprints database and Stories to Tasks database.
    Uses status mapping from config and tracks sync state in SQLite.
    """

    def __init__(self, client, store: Store, config: Config):
        """Initialize the database sync engine.

        Args:
            client: Notion client instance.
            store: SQLite store for tracking sync state.
            config: Loaded configuration.
        """
        self.client = client
        self.store = store
        self.config = config
        self.scanner = BMADScanner(config)

    def sync(self, force: bool = False, dry_run: bool = False) -> DbSyncResult:
        """Sync sprint data to Notion databases.

        Args:
            force: If True, sync all items regardless of changes.
            dry_run: If True, report what would be done without making changes.

        Returns:
            DbSyncResult with statistics about the sync operation.
        """
        # Check if database sync is enabled
        if not self.config.database_sync.enabled:
            return DbSyncResult()

        # Scan sprint status
        epics, stories = self.scanner.scan_sprint_status()

        result = DbSyncResult()

        # First sync epics (needed for story relations)
        epic_id_map: dict[str, str] = {}  # epic_key -> notion_page_id
        for epic in epics:
            try:
                action, page_id = self._sync_epic(epic, force=force, dry_run=dry_run)
                epic_id_map[epic.key] = page_id
                if action == "created":
                    result.epics_created += 1
                elif action == "updated":
                    result.epics_updated += 1
                elif action == "skipped":
                    result.epics_skipped += 1
            except Exception as e:
                result.epics_failed += 1
                result.errors.append(f"Failed to sync epic {epic.key}: {e}")

        # Then sync stories (with relations to epics)
        for story in stories:
            try:
                epic_page_id = epic_id_map.get(story.epic_key)
                action = self._sync_story(story, epic_page_id, force=force, dry_run=dry_run)
                if action == "created":
                    result.stories_created += 1
                elif action == "updated":
                    result.stories_updated += 1
                elif action == "skipped":
                    result.stories_skipped += 1
            except Exception as e:
                result.stories_failed += 1
                result.errors.append(f"Failed to sync story {story.key}: {e}")

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

        # Map status
        status_mapping = self.config.database_sync.sprints.status_mapping
        mapped_status = status_mapping.get(epic.status, epic.status)

        # Build properties
        properties = {
            "Name": {"title": [{"text": {"content": epic.title}}]},
            "Status": {"status": {"name": mapped_status}},
        }

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
        self, story: Story, epic_page_id: str | None, force: bool, dry_run: bool
    ) -> str:
        """Sync a single story.

        Args:
            story: Story to sync.
            epic_page_id: Notion page ID of the parent epic (for relation).
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

        # Map status
        status_mapping = self.config.database_sync.tasks.status_mapping
        mapped_status = status_mapping.get(story.status, story.status)

        # Build properties
        properties = {
            "Name": {"title": [{"text": {"content": story.title}}]},
            "Status": {"status": {"name": mapped_status}},
        }

        # Add Sprint relation if epic_page_id is available
        if epic_page_id:
            properties["Sprint"] = {"relation": [{"id": epic_page_id}]}

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
