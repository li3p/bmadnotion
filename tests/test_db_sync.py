"""Tests for database sync engine."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call


@pytest.fixture
def sample_bmad_project(tmp_path: Path) -> Path:
    """Create a sample BMAD project structure for testing."""
    # Create config
    config_file = tmp_path / ".bmadnotion.yaml"
    config_file.write_text("""
project: test-project
notion:
  token_env: NOTION_TOKEN
  workspace_page_id: "workspace123"
page_sync:
  enabled: false
database_sync:
  enabled: true
  sprints:
    database_id: "sprints-db-123"
    name_property: "Name"
    status_property: "Status"
    status_mapping:
      backlog: "Not Started"
      in-progress: "In Progress"
      done: "Done"
  tasks:
    database_id: "tasks-db-456"
    name_property: "Name"
    status_property: "Status"
    require_story_file: false  # Sync all stories for testing
    status_mapping:
      backlog: "Backlog"
      ready-for-dev: "Ready"
      in-progress: "In Progress"
      review: "Review"
      done: "Done"
""")

    # Create implementation-artifacts with sprint-status.yaml
    impl = tmp_path / "_bmad-output" / "implementation-artifacts"
    impl.mkdir(parents=True)
    # Use the real BMAD format: development_status with flat key-value pairs
    (impl / "sprint-status.yaml").write_text("""
development_status:
  epic-1: in-progress
  1-1-backend-setup: done
  1-2-frontend-setup: in-progress
  epic-2: backlog
  2-1-feature-a: backlog
""")

    # Create epic files
    epics_dir = tmp_path / "_bmad-output" / "planning-artifacts" / "epics"
    epics_dir.mkdir(parents=True)
    (epics_dir / "epic-1-main-feature.md").write_text("# Epic 1: Main Feature\n\nDescription here.")
    (epics_dir / "epic-2-secondary.md").write_text("# Epic 2: Secondary Feature\n\nDescription here.")

    # Create story files (only for non-backlog stories)
    stories_dir = tmp_path / "_bmad-output" / "implementation-artifacts"
    (stories_dir / "1-1-backend-setup.md").write_text("""# Story 1.1: Backend Setup

## Acceptance Criteria
- AC1: Setup complete

## Tasks
- [x] Create project
""")
    (stories_dir / "1-2-frontend-setup.md").write_text("""# Story 1.2: Frontend Setup

## Acceptance Criteria
- AC1: Frontend ready

## Tasks
- [ ] Setup React
""")

    return tmp_path


@pytest.fixture
def mock_notion_client():
    """Create a mock Notion client."""
    client = MagicMock()
    # Mock create_database_entry to return unique IDs
    client.create_database_entry.side_effect = lambda **kwargs: {
        "id": f"notion-{kwargs.get('properties', {}).get('Name', {}).get('title', [{}])[0].get('text', {}).get('content', 'unknown')}-id"
    }
    client.update_database_entry.return_value = {"id": "updated-id"}
    client.append_blocks.return_value = None
    client.clear_page_content.return_value = None
    return client


class TestDbSyncEngine:
    """Tests for DbSyncEngine."""

    def test_sync_creates_epics(self, sample_bmad_project: Path, mock_notion_client, monkeypatch):
        """AC1: Should sync epics to Sprints database."""
        from bmadnotion.config import load_config
        from bmadnotion.store import Store
        from bmadnotion.db_sync import DbSyncEngine

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        config = load_config(sample_bmad_project)
        store = Store(sample_bmad_project)
        engine = DbSyncEngine(mock_notion_client, store, config)

        result = engine.sync()

        # Should have created 2 epics
        assert result.epics_created == 2
        # Verify state was saved
        state = store.get_db_state("epic-1")
        assert state is not None
        assert state.entity_type == "epic"

    def test_sync_creates_stories(self, sample_bmad_project: Path, mock_notion_client, monkeypatch):
        """AC2: Should sync stories to Tasks database."""
        from bmadnotion.config import load_config
        from bmadnotion.store import Store
        from bmadnotion.db_sync import DbSyncEngine

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        config = load_config(sample_bmad_project)
        store = Store(sample_bmad_project)
        engine = DbSyncEngine(mock_notion_client, store, config)

        result = engine.sync()

        # Should have created 3 stories
        assert result.stories_created == 3
        # Verify state was saved
        state = store.get_db_state("1-1-backend-setup")
        assert state is not None
        assert state.entity_type == "story"

    def test_story_relates_to_epic(self, sample_bmad_project: Path, mock_notion_client, monkeypatch):
        """AC3: Story should relate to corresponding Epic."""
        from bmadnotion.config import load_config
        from bmadnotion.store import Store
        from bmadnotion.db_sync import DbSyncEngine

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        # Make create_database_entry return predictable IDs
        def mock_create(**kwargs):
            props = kwargs.get("properties", {})
            name = props.get("Name", {}).get("title", [{}])[0].get("text", {}).get("content", "unknown")
            return {"id": f"page-{name}"}

        mock_notion_client.create_database_entry.side_effect = mock_create

        config = load_config(sample_bmad_project)
        store = Store(sample_bmad_project)
        engine = DbSyncEngine(mock_notion_client, store, config)

        engine.sync()

        # Check that story creation included Sprint relation
        create_calls = mock_notion_client.create_database_entry.call_args_list
        story_calls = [c for c in create_calls if c.kwargs.get("database_id") == "tasks-db-456"]

        assert len(story_calls) > 0
        # First story should have Sprint relation
        first_story_props = story_calls[0].kwargs.get("properties", {})
        assert "Sprint" in first_story_props
        assert first_story_props["Sprint"]["relation"] is not None

    def test_story_content_as_blocks(self, sample_bmad_project: Path, mock_notion_client, monkeypatch):
        """AC4: Story content should be converted to Notion blocks."""
        from bmadnotion.config import load_config
        from bmadnotion.store import Store
        from bmadnotion.db_sync import DbSyncEngine

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        config = load_config(sample_bmad_project)
        store = Store(sample_bmad_project)
        engine = DbSyncEngine(mock_notion_client, store, config)

        engine.sync()

        # Verify append_blocks was called for stories with content
        assert mock_notion_client.append_blocks.call_count >= 2  # 2 non-backlog stories

    def test_status_mapping(self, sample_bmad_project: Path, mock_notion_client, monkeypatch):
        """AC5: Status should be correctly mapped."""
        from bmadnotion.config import load_config
        from bmadnotion.store import Store
        from bmadnotion.db_sync import DbSyncEngine

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        config = load_config(sample_bmad_project)
        store = Store(sample_bmad_project)
        engine = DbSyncEngine(mock_notion_client, store, config)

        engine.sync()

        # Check epic status mapping
        epic_calls = [
            c for c in mock_notion_client.create_database_entry.call_args_list
            if c.kwargs.get("database_id") == "sprints-db-123"
        ]
        assert len(epic_calls) == 2

        # Find in-progress epic
        for call in epic_calls:
            props = call.kwargs.get("properties", {})
            status = props.get("Status", {}).get("status", {}).get("name")
            # Should be mapped values, not raw values
            assert status in ["Not Started", "In Progress", "Done"]

    def test_sync_updates_existing(self, sample_bmad_project: Path, mock_notion_client, monkeypatch):
        """Should update existing entries when content changes."""
        from bmadnotion.config import load_config
        from bmadnotion.store import Store
        from bmadnotion.db_sync import DbSyncEngine
        from bmadnotion.models import DbSyncState

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        config = load_config(sample_bmad_project)
        store = Store(sample_bmad_project)

        # Pre-populate store with existing state (old content hash)
        store.save_db_state(DbSyncState(
            local_key="1-1-backend-setup",
            entity_type="story",
            notion_page_id="existing-page-123",
            last_synced_mtime=0,
            content_hash="old-hash-different",
        ))

        engine = DbSyncEngine(mock_notion_client, store, config)
        result = engine.sync()

        # Should have updated the story
        assert result.stories_updated >= 1
        assert mock_notion_client.update_database_entry.call_count >= 1

    def test_sync_skips_unchanged(self, sample_bmad_project: Path, mock_notion_client, monkeypatch):
        """Should skip unchanged entries."""
        from bmadnotion.config import load_config
        from bmadnotion.store import Store
        from bmadnotion.db_sync import DbSyncEngine

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        config = load_config(sample_bmad_project)
        store = Store(sample_bmad_project)
        engine = DbSyncEngine(mock_notion_client, store, config)

        # First sync
        engine.sync()

        # Reset mock
        mock_notion_client.reset_mock()

        # Second sync (no changes)
        result = engine.sync()

        assert result.epics_skipped == 2
        assert result.stories_skipped == 3
        assert mock_notion_client.create_database_entry.call_count == 0

    def test_sync_force_mode(self, sample_bmad_project: Path, mock_notion_client, monkeypatch):
        """Should sync all when force=True."""
        from bmadnotion.config import load_config
        from bmadnotion.store import Store
        from bmadnotion.db_sync import DbSyncEngine

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        config = load_config(sample_bmad_project)
        store = Store(sample_bmad_project)
        engine = DbSyncEngine(mock_notion_client, store, config)

        # First sync
        engine.sync()

        # Reset mock
        mock_notion_client.reset_mock()

        # Force sync
        result = engine.sync(force=True)

        assert result.epics_updated == 2
        assert result.stories_updated == 3

    def test_sync_dry_run(self, sample_bmad_project: Path, mock_notion_client, monkeypatch):
        """Should not make changes in dry run mode."""
        from bmadnotion.config import load_config
        from bmadnotion.store import Store
        from bmadnotion.db_sync import DbSyncEngine

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        config = load_config(sample_bmad_project)
        store = Store(sample_bmad_project)
        engine = DbSyncEngine(mock_notion_client, store, config)

        result = engine.sync(dry_run=True)

        # Should report what would be done
        assert result.epics_created == 2
        assert result.stories_created == 3

        # But no actual API calls
        assert mock_notion_client.create_database_entry.call_count == 0

        # And no store updates
        assert store.get_db_state("epic-1") is None


class TestDbSyncDisabled:
    """Tests for disabled database sync."""

    def test_sync_disabled(self, tmp_path: Path, mock_notion_client, monkeypatch):
        """Should do nothing when database_sync is disabled."""
        from bmadnotion.config import load_config
        from bmadnotion.store import Store
        from bmadnotion.db_sync import DbSyncEngine

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        # Create config with database_sync disabled
        (tmp_path / ".bmadnotion.yaml").write_text("""
project: test
notion:
  token_env: NOTION_TOKEN
  workspace_page_id: "abc"
database_sync:
  enabled: false
""")

        config = load_config(tmp_path)
        store = Store(tmp_path)
        engine = DbSyncEngine(mock_notion_client, store, config)

        result = engine.sync()

        assert result.total == 0
        assert mock_notion_client.create_database_entry.call_count == 0
