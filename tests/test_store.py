"""Tests for bmadnotion SQLite store."""

import pytest
from pathlib import Path


class TestStoreCreation:
    """Tests for Store initialization."""

    def test_store_creates_db_file(self, tmp_path: Path):
        """AC1 & AC5: Should create database file in .bmadnotion/ directory."""
        from bmadnotion.store import Store

        store = Store(project_root=tmp_path)

        db_path = tmp_path / ".bmadnotion" / "sync.db"
        assert db_path.exists()

    def test_store_creates_tables(self, tmp_path: Path):
        """Should create necessary tables on initialization."""
        from bmadnotion.store import Store
        import sqlite3

        store = Store(project_root=tmp_path)

        db_path = tmp_path / ".bmadnotion" / "sync.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        assert "page_sync_state" in tables
        assert "db_sync_state" in tables

        conn.close()

    def test_store_reuses_existing_db(self, tmp_path: Path):
        """Should reuse existing database file."""
        from bmadnotion.store import Store
        from bmadnotion.models import PageSyncState

        # Create store and add data
        store1 = Store(project_root=tmp_path)
        state = PageSyncState(
            local_path="test.md",
            notion_page_id="abc123",
            last_synced_mtime=1234567890.0,
            content_hash="hash123",
        )
        store1.save_page_state(state)

        # Create new store instance
        store2 = Store(project_root=tmp_path)
        retrieved = store2.get_page_state("test.md")

        assert retrieved is not None
        assert retrieved.notion_page_id == "abc123"


class TestPageSyncState:
    """Tests for PageSyncState CRUD operations."""

    def test_save_and_get_page_state(self, tmp_path: Path):
        """AC2: Should save and retrieve PageSyncState."""
        from bmadnotion.store import Store
        from bmadnotion.models import PageSyncState

        store = Store(project_root=tmp_path)

        state = PageSyncState(
            local_path="prd.md",
            notion_page_id="abc123-def456",
            last_synced_mtime=1234567890.0,
            content_hash="a1b2c3d4e5f6",
        )
        store.save_page_state(state)

        retrieved = store.get_page_state("prd.md")

        assert retrieved is not None
        assert retrieved.local_path == "prd.md"
        assert retrieved.notion_page_id == "abc123-def456"
        assert retrieved.last_synced_mtime == 1234567890.0
        assert retrieved.content_hash == "a1b2c3d4e5f6"

    def test_get_nonexistent_page_state(self, tmp_path: Path):
        """AC4: Should return None for nonexistent page state."""
        from bmadnotion.store import Store

        store = Store(project_root=tmp_path)

        result = store.get_page_state("nonexistent.md")

        assert result is None

    def test_update_page_state(self, tmp_path: Path):
        """Should update existing page state."""
        from bmadnotion.store import Store
        from bmadnotion.models import PageSyncState

        store = Store(project_root=tmp_path)

        # Initial save
        state1 = PageSyncState(
            local_path="prd.md",
            notion_page_id="abc123",
            last_synced_mtime=1000.0,
            content_hash="hash1",
        )
        store.save_page_state(state1)

        # Update
        state2 = PageSyncState(
            local_path="prd.md",
            notion_page_id="abc123",
            last_synced_mtime=2000.0,
            content_hash="hash2",
        )
        store.save_page_state(state2)

        # Verify update
        retrieved = store.get_page_state("prd.md")
        assert retrieved.last_synced_mtime == 2000.0
        assert retrieved.content_hash == "hash2"

    def test_get_all_page_states(self, tmp_path: Path):
        """Should retrieve all page states."""
        from bmadnotion.store import Store
        from bmadnotion.models import PageSyncState

        store = Store(project_root=tmp_path)

        # Save multiple states
        for i in range(3):
            state = PageSyncState(
                local_path=f"doc{i}.md",
                notion_page_id=f"page{i}",
                last_synced_mtime=float(i),
                content_hash=f"hash{i}",
            )
            store.save_page_state(state)

        all_states = store.get_all_page_states()

        assert len(all_states) == 3
        paths = {s.local_path for s in all_states}
        assert paths == {"doc0.md", "doc1.md", "doc2.md"}


class TestDbSyncState:
    """Tests for DbSyncState CRUD operations."""

    def test_save_and_get_db_state(self, tmp_path: Path):
        """AC3: Should save and retrieve DbSyncState."""
        from bmadnotion.store import Store
        from bmadnotion.models import DbSyncState

        store = Store(project_root=tmp_path)

        state = DbSyncState(
            local_key="epic-1",
            entity_type="epic",
            notion_page_id="xyz789",
            last_synced_mtime=1234567890.0,
            content_hash=None,
        )
        store.save_db_state(state)

        retrieved = store.get_db_state("epic-1")

        assert retrieved is not None
        assert retrieved.local_key == "epic-1"
        assert retrieved.entity_type == "epic"
        assert retrieved.notion_page_id == "xyz789"

    def test_get_nonexistent_db_state(self, tmp_path: Path):
        """AC4: Should return None for nonexistent db state."""
        from bmadnotion.store import Store

        store = Store(project_root=tmp_path)

        result = store.get_db_state("nonexistent-key")

        assert result is None

    def test_save_story_with_content_hash(self, tmp_path: Path):
        """Should save story with content hash."""
        from bmadnotion.store import Store
        from bmadnotion.models import DbSyncState

        store = Store(project_root=tmp_path)

        state = DbSyncState(
            local_key="1-5-create-kp",
            entity_type="story",
            notion_page_id="page123",
            last_synced_mtime=1234567890.0,
            content_hash="storyhash123",
        )
        store.save_db_state(state)

        retrieved = store.get_db_state("1-5-create-kp")

        assert retrieved.entity_type == "story"
        assert retrieved.content_hash == "storyhash123"

    def test_get_all_db_states(self, tmp_path: Path):
        """Should retrieve all db states."""
        from bmadnotion.store import Store
        from bmadnotion.models import DbSyncState

        store = Store(project_root=tmp_path)

        # Save epics and stories
        store.save_db_state(DbSyncState(
            local_key="epic-1", entity_type="epic", notion_page_id="e1"
        ))
        store.save_db_state(DbSyncState(
            local_key="epic-2", entity_type="epic", notion_page_id="e2"
        ))
        store.save_db_state(DbSyncState(
            local_key="1-1-story", entity_type="story", notion_page_id="s1"
        ))

        all_states = store.get_all_db_states()

        assert len(all_states) == 3

    def test_get_db_states_by_type(self, tmp_path: Path):
        """Should filter db states by entity type."""
        from bmadnotion.store import Store
        from bmadnotion.models import DbSyncState

        store = Store(project_root=tmp_path)

        # Save epics and stories
        store.save_db_state(DbSyncState(
            local_key="epic-1", entity_type="epic", notion_page_id="e1"
        ))
        store.save_db_state(DbSyncState(
            local_key="epic-2", entity_type="epic", notion_page_id="e2"
        ))
        store.save_db_state(DbSyncState(
            local_key="1-1-story", entity_type="story", notion_page_id="s1"
        ))
        store.save_db_state(DbSyncState(
            local_key="1-2-story", entity_type="story", notion_page_id="s2"
        ))

        epics = store.get_db_states_by_type("epic")
        stories = store.get_db_states_by_type("story")

        assert len(epics) == 2
        assert len(stories) == 2
        assert all(s.entity_type == "epic" for s in epics)
        assert all(s.entity_type == "story" for s in stories)


class TestStoreDelete:
    """Tests for delete operations."""

    def test_delete_page_state(self, tmp_path: Path):
        """Should delete page state."""
        from bmadnotion.store import Store
        from bmadnotion.models import PageSyncState

        store = Store(project_root=tmp_path)

        state = PageSyncState(
            local_path="to-delete.md",
            notion_page_id="abc",
            last_synced_mtime=0,
            content_hash="hash",
        )
        store.save_page_state(state)
        assert store.get_page_state("to-delete.md") is not None

        store.delete_page_state("to-delete.md")

        assert store.get_page_state("to-delete.md") is None

    def test_delete_db_state(self, tmp_path: Path):
        """Should delete db state."""
        from bmadnotion.store import Store
        from bmadnotion.models import DbSyncState

        store = Store(project_root=tmp_path)

        state = DbSyncState(
            local_key="to-delete",
            entity_type="epic",
            notion_page_id="abc",
        )
        store.save_db_state(state)
        assert store.get_db_state("to-delete") is not None

        store.delete_db_state("to-delete")

        assert store.get_db_state("to-delete") is None
