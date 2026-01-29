"""Database schema management for bmadnotion.

Ensures required fields exist in Notion databases for reliable sync.
"""

from typing import Any

from notion_client import Client

# Required fields for each database type
REQUIRED_FIELDS = {
    "projects": {
        "BMADProject": {"rich_text": {}},
    },
    "sprints": {
        "BMADEpic": {"rich_text": {}},
    },
    "tasks": {
        "BMADStory": {"rich_text": {}},
    },
}


def ensure_database_fields(
    client: Client,
    database_id: str,
    database_type: str,
) -> list[str]:
    """Ensure required fields exist in a Notion database.

    Args:
        client: Official notion-client instance
        database_id: The database ID
        database_type: One of "projects", "sprints", "tasks"

    Returns:
        List of field names that were added
    """
    if database_type not in REQUIRED_FIELDS:
        return []

    required = REQUIRED_FIELDS[database_type]

    # Get current database schema
    db = client.databases.retrieve(database_id=database_id)
    existing_props = set(db.get("properties", {}).keys())

    # Find missing fields
    fields_to_add: dict[str, Any] = {}
    for field_name, field_config in required.items():
        if field_name not in existing_props:
            fields_to_add[field_name] = field_config

    if not fields_to_add:
        return []

    # Add missing fields
    client.databases.update(database_id=database_id, properties=fields_to_add)

    return list(fields_to_add.keys())


def setup_all_databases(client: Client, config: Any) -> dict[str, list[str]]:
    """Ensure all configured databases have required fields.

    Args:
        client: Official notion-client instance
        config: bmadnotion Config object

    Returns:
        Dict mapping database type to list of added fields
    """
    results: dict[str, list[str]] = {}

    db_sync = config.database_sync
    if not db_sync.enabled:
        return results

    # Projects database
    if hasattr(db_sync, "projects") and db_sync.projects.database_id:
        added = ensure_database_fields(client, db_sync.projects.database_id, "projects")
        if added:
            results["projects"] = added

    # Sprints database
    if db_sync.sprints.database_id:
        added = ensure_database_fields(client, db_sync.sprints.database_id, "sprints")
        if added:
            results["sprints"] = added

    # Tasks database
    if db_sync.tasks.database_id:
        added = ensure_database_fields(client, db_sync.tasks.database_id, "tasks")
        if added:
            results["tasks"] = added

    return results
