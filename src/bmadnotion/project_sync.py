"""Project sync engine for managing BMAD projects in Notion.

Handles finding or creating Project rows in the Projects database,
which serve as the parent for planning documents and link to Sprints/Tasks.
"""

from __future__ import annotations

from typing import Any

from notion_client import Client

from bmadnotion.config import Config
from bmadnotion.models import DbSyncState
from bmadnotion.store import Store


class ProjectSyncEngine:
    """Engine for syncing BMAD projects to the Notion Projects database.

    Manages the Project row that serves as the parent for planning documents
    and provides the relation target for Sprints and Tasks.
    """

    def __init__(self, client: Client, store: Store, config: Config):
        """Initialize the project sync engine.

        Args:
            client: Official notion-client instance.
            store: SQLite store for tracking sync state.
            config: Loaded configuration.
        """
        self.client = client
        self.store = store
        self.config = config

    def get_or_create_project(self, dry_run: bool = False) -> tuple[str, bool]:
        """Get or create the Project row for this BMAD project.

        Args:
            dry_run: If True, don't create anything, return placeholder.

        Returns:
            Tuple of (project_page_id, was_created).
        """
        project_key = self.config.project
        db_config = self.config.database_sync.projects

        if not db_config.database_id:
            raise ValueError("Projects database_id not configured")

        # Check if we already have a synced project
        state = self.store.get_db_state(f"project:{project_key}")
        if state:
            return (state.notion_page_id, False)

        if dry_run:
            return (f"dry-run-project-{project_key}", True)

        # Search for existing project by BMADProject key
        existing = self._find_project_by_key(project_key)
        if existing:
            # Save state and return
            self.store.save_db_state(DbSyncState(
                local_key=f"project:{project_key}",
                entity_type="project",
                notion_page_id=existing,
            ))
            return (existing, False)

        # Create new project
        page_id = self._create_project(project_key)

        # Save state
        self.store.save_db_state(DbSyncState(
            local_key=f"project:{project_key}",
            entity_type="project",
            notion_page_id=page_id,
        ))

        return (page_id, True)

    def _find_project_by_key(self, project_key: str) -> str | None:
        """Find a project by its BMADProject key.

        Args:
            project_key: The BMAD project key to search for.

        Returns:
            Notion page ID if found, None otherwise.
        """
        db_config = self.config.database_sync.projects
        database_id = db_config.database_id
        key_property = db_config.key_property

        # Get data_source_id from database (required for 2025-09-03 API)
        db = self.client.databases.retrieve(database_id=database_id)
        data_sources = db.get("data_sources", [])
        if not data_sources:
            return None  # No data sources, can't query

        ds_id = data_sources[0]["id"]

        # Query using data_sources endpoint
        response = self.client.data_sources.query(
            data_source_id=ds_id,
            filter={
                "property": key_property,
                "rich_text": {"equals": project_key},
            },
        )

        results = response.get("results", [])
        if results:
            return results[0]["id"]
        return None

    def _create_project(self, project_key: str) -> str:
        """Create a new project in the Projects database.

        Args:
            project_key: The BMAD project key.

        Returns:
            Notion page ID of the created project.
        """
        db_config = self.config.database_sync.projects
        database_id = db_config.database_id
        key_property = db_config.key_property
        name_property = db_config.name_property

        # Build properties
        properties: dict[str, Any] = {
            name_property: {"title": [{"text": {"content": project_key}}]},
            key_property: {"rich_text": [{"text": {"content": project_key}}]},
        }

        # Create the project row using official notion-client
        page = self.client.pages.create(
            parent={"database_id": database_id},
            properties=properties,
        )

        return page["id"]

    def get_project_page_id(self) -> str | None:
        """Get the Notion page ID for the current project.

        Returns:
            Notion page ID if the project has been synced, None otherwise.
        """
        project_key = self.config.project
        state = self.store.get_db_state(f"project:{project_key}")
        return state.notion_page_id if state else None
