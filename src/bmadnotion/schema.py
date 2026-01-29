"""Database schema management for bmadnotion.

Ensures required fields exist in Notion databases for reliable sync.
"""

from typing import Any

from notion_client import Client

# Required fields for each database type
# Note: status, formula, synced content, place cannot be added via API
# They must be added manually in Notion UI
REQUIRED_FIELDS = {
    "projects": {
        "BMADProject": {"name": "BMADProject", "type": "rich_text", "rich_text": {}},
    },
    "sprints": {
        "BMADEpic": {"name": "BMADEpic", "type": "rich_text", "rich_text": {}},
        # Status must be added manually in Notion UI (API limitation)
    },
    "tasks": {
        "BMADStory": {"name": "BMADStory", "type": "rich_text", "rich_text": {}},
    },
}


def _get_existing_properties(client: Client, database_id: str) -> set[str]:
    """Get existing property names from a database.

    Uses data_sources API (2025-09-03) to query a sample row and extract property names.
    """
    # Get data_source_id from database
    db = client.databases.retrieve(database_id=database_id)
    data_sources = db.get("data_sources", [])
    if not data_sources:
        return set()

    ds_id = data_sources[0]["id"]

    # Query one row to get property names
    response = client.data_sources.query(data_source_id=ds_id, page_size=1)
    if not response.get("results"):
        return set()

    props = response["results"][0].get("properties", {})
    return set(props.keys())


def ensure_database_fields(
    client: Client,
    database_id: str,
    database_type: str,
) -> list[str]:
    """Ensure required fields exist in a Notion database.

    Uses data_sources API (2025-09-03) to add properties.
    Note: status, formula, synced content, place types cannot be added via API.

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

    # Get data_source_id from database
    db = client.databases.retrieve(database_id=database_id)
    data_sources = db.get("data_sources", [])
    if not data_sources:
        return []

    ds_id = data_sources[0]["id"]

    # Get existing property names
    existing_props = _get_existing_properties(client, database_id)

    # Find missing fields
    fields_to_add: dict[str, Any] = {}
    for field_name, field_config in required.items():
        if field_name not in existing_props:
            fields_to_add[field_name] = field_config

    if not fields_to_add:
        return []

    # Add missing fields via data_sources PATCH endpoint (2025-09-03 API)
    client.data_sources.update(data_source_id=ds_id, properties=fields_to_add)

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
