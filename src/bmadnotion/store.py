"""SQLite store for sync state management."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Literal

from bmadnotion.models import DbSyncState, PageSyncState


class Store:
    """SQLite store for tracking sync state.

    Stores sync state in .bmadnotion/sync.db within the project root.
    """

    def __init__(self, project_root: Path):
        """Initialize the store.

        Args:
            project_root: Path to the project root directory.
        """
        self.project_root = project_root
        self.db_dir = project_root / ".bmadnotion"
        self.db_path = self.db_dir / "sync.db"

        # Ensure directory exists
        self.db_dir.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create page_sync_state table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS page_sync_state (
                local_path TEXT PRIMARY KEY,
                notion_page_id TEXT NOT NULL,
                last_synced_mtime REAL NOT NULL,
                content_hash TEXT NOT NULL
            )
        """)

        # Create db_sync_state table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS db_sync_state (
                local_key TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                notion_page_id TEXT NOT NULL,
                last_synced_mtime REAL,
                content_hash TEXT
            )
        """)

        conn.commit()
        conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        return sqlite3.connect(self.db_path)

    # --- PageSyncState operations ---

    def save_page_state(self, state: PageSyncState) -> None:
        """Save or update a page sync state.

        Args:
            state: The page sync state to save.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO page_sync_state
            (local_path, notion_page_id, last_synced_mtime, content_hash)
            VALUES (?, ?, ?, ?)
        """, (
            state.local_path,
            state.notion_page_id,
            state.last_synced_mtime,
            state.content_hash,
        ))

        conn.commit()
        conn.close()

    def get_page_state(self, local_path: str) -> PageSyncState | None:
        """Get page sync state by local path.

        Args:
            local_path: The local file path.

        Returns:
            The page sync state, or None if not found.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT local_path, notion_page_id, last_synced_mtime, content_hash
            FROM page_sync_state
            WHERE local_path = ?
        """, (local_path,))

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return PageSyncState(
            local_path=row[0],
            notion_page_id=row[1],
            last_synced_mtime=row[2],
            content_hash=row[3],
        )

    def get_all_page_states(self) -> list[PageSyncState]:
        """Get all page sync states.

        Returns:
            List of all page sync states.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT local_path, notion_page_id, last_synced_mtime, content_hash
            FROM page_sync_state
        """)

        rows = cursor.fetchall()
        conn.close()

        return [
            PageSyncState(
                local_path=row[0],
                notion_page_id=row[1],
                last_synced_mtime=row[2],
                content_hash=row[3],
            )
            for row in rows
        ]

    def delete_page_state(self, local_path: str) -> None:
        """Delete a page sync state.

        Args:
            local_path: The local file path to delete.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM page_sync_state
            WHERE local_path = ?
        """, (local_path,))

        conn.commit()
        conn.close()

    # --- DbSyncState operations ---

    def save_db_state(self, state: DbSyncState) -> None:
        """Save or update a database sync state.

        Args:
            state: The database sync state to save.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO db_sync_state
            (local_key, entity_type, notion_page_id, last_synced_mtime, content_hash)
            VALUES (?, ?, ?, ?, ?)
        """, (
            state.local_key,
            state.entity_type,
            state.notion_page_id,
            state.last_synced_mtime,
            state.content_hash,
        ))

        conn.commit()
        conn.close()

    def get_db_state(self, local_key: str) -> DbSyncState | None:
        """Get database sync state by local key.

        Args:
            local_key: The local key (e.g., 'epic-1' or '1-5-create-kp').

        Returns:
            The database sync state, or None if not found.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT local_key, entity_type, notion_page_id, last_synced_mtime, content_hash
            FROM db_sync_state
            WHERE local_key = ?
        """, (local_key,))

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return DbSyncState(
            local_key=row[0],
            entity_type=row[1],
            notion_page_id=row[2],
            last_synced_mtime=row[3],
            content_hash=row[4],
        )

    def get_all_db_states(self) -> list[DbSyncState]:
        """Get all database sync states.

        Returns:
            List of all database sync states.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT local_key, entity_type, notion_page_id, last_synced_mtime, content_hash
            FROM db_sync_state
        """)

        rows = cursor.fetchall()
        conn.close()

        return [
            DbSyncState(
                local_key=row[0],
                entity_type=row[1],
                notion_page_id=row[2],
                last_synced_mtime=row[3],
                content_hash=row[4],
            )
            for row in rows
        ]

    def get_db_states_by_type(
        self, entity_type: Literal["epic", "story"]
    ) -> list[DbSyncState]:
        """Get database sync states by entity type.

        Args:
            entity_type: The entity type to filter by.

        Returns:
            List of database sync states of the specified type.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT local_key, entity_type, notion_page_id, last_synced_mtime, content_hash
            FROM db_sync_state
            WHERE entity_type = ?
        """, (entity_type,))

        rows = cursor.fetchall()
        conn.close()

        return [
            DbSyncState(
                local_key=row[0],
                entity_type=row[1],
                notion_page_id=row[2],
                last_synced_mtime=row[3],
                content_hash=row[4],
            )
            for row in rows
        ]

    def delete_db_state(self, local_key: str) -> None:
        """Delete a database sync state.

        Args:
            local_key: The local key to delete.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM db_sync_state
            WHERE local_key = ?
        """, (local_key,))

        conn.commit()
        conn.close()
