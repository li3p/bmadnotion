"""Tests for page sync engine."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


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
  enabled: true
  parent_page_id: "parent123"
  documents:
    - path: "prd.md"
      title: "PRD - {project}"
    - path: "architecture.md"
      title: "Architecture - {project}"
""")

    # Create planning-artifacts
    planning = tmp_path / "_bmad-output" / "planning-artifacts"
    planning.mkdir(parents=True)

    (planning / "prd.md").write_text("# PRD\n\nProduct requirements document content.")
    (planning / "architecture.md").write_text("# Architecture\n\nSystem architecture design.")

    return tmp_path


@pytest.fixture
def mock_notion_client():
    """Create a mock Notion client."""
    client = MagicMock()
    client.create_page.return_value = {"id": "new-page-id-123"}
    client.update_page.return_value = {"id": "existing-page-id"}
    client.append_blocks.return_value = None
    client.clear_page_content.return_value = None
    return client


class TestPageSyncEngine:
    """Tests for PageSyncEngine."""

    def test_sync_creates_new_pages(self, sample_bmad_project: Path, mock_notion_client, monkeypatch):
        """AC1: Should create new Notion pages for documents."""
        from bmadnotion.config import load_config
        from bmadnotion.store import Store
        from bmadnotion.page_sync import PageSyncEngine

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        config = load_config(sample_bmad_project)
        store = Store(sample_bmad_project)
        engine = PageSyncEngine(mock_notion_client, store, config)

        result = engine.sync()

        assert result.created == 2
        assert mock_notion_client.create_page.call_count == 2

        # Verify state was saved
        state = store.get_page_state("prd.md")
        assert state is not None
        assert state.notion_page_id == "new-page-id-123"

    def test_sync_updates_existing_pages(self, sample_bmad_project: Path, mock_notion_client, monkeypatch):
        """AC2: Should update existing pages when content changes."""
        from bmadnotion.config import load_config
        from bmadnotion.store import Store
        from bmadnotion.page_sync import PageSyncEngine
        from bmadnotion.models import PageSyncState

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        config = load_config(sample_bmad_project)
        store = Store(sample_bmad_project)

        # Pre-populate store with existing state (old content hash)
        store.save_page_state(PageSyncState(
            local_path="prd.md",
            notion_page_id="existing-page-123",
            last_synced_mtime=0,
            content_hash="old-hash-different",
        ))

        engine = PageSyncEngine(mock_notion_client, store, config)
        result = engine.sync()

        # One updated (prd.md), one created (architecture.md)
        assert result.updated >= 1
        assert mock_notion_client.clear_page_content.call_count >= 1

    def test_sync_skips_unchanged(self, sample_bmad_project: Path, mock_notion_client, monkeypatch):
        """AC3: Should skip documents with unchanged content."""
        from bmadnotion.config import load_config
        from bmadnotion.store import Store
        from bmadnotion.page_sync import PageSyncEngine
        from bmadnotion.scanner import BMADScanner

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        config = load_config(sample_bmad_project)
        store = Store(sample_bmad_project)

        # First sync
        engine = PageSyncEngine(mock_notion_client, store, config)
        engine.sync()

        # Reset mock
        mock_notion_client.reset_mock()

        # Second sync (no changes)
        result = engine.sync()

        assert result.skipped == 2
        assert result.created == 0
        assert result.updated == 0
        assert mock_notion_client.create_page.call_count == 0

    def test_sync_force_mode(self, sample_bmad_project: Path, mock_notion_client, monkeypatch):
        """Should sync all documents when force=True."""
        from bmadnotion.config import load_config
        from bmadnotion.store import Store
        from bmadnotion.page_sync import PageSyncEngine

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        config = load_config(sample_bmad_project)
        store = Store(sample_bmad_project)

        # First sync
        engine = PageSyncEngine(mock_notion_client, store, config)
        engine.sync()

        # Reset mock
        mock_notion_client.reset_mock()

        # Force sync
        result = engine.sync(force=True)

        assert result.updated == 2
        assert result.skipped == 0

    def test_sync_updates_store(self, sample_bmad_project: Path, mock_notion_client, monkeypatch):
        """AC4: Should update store after sync."""
        from bmadnotion.config import load_config
        from bmadnotion.store import Store
        from bmadnotion.page_sync import PageSyncEngine

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        config = load_config(sample_bmad_project)
        store = Store(sample_bmad_project)
        engine = PageSyncEngine(mock_notion_client, store, config)

        engine.sync()

        # Check store was updated
        state = store.get_page_state("prd.md")
        assert state is not None
        assert state.notion_page_id is not None
        assert state.last_synced_mtime > 0
        assert state.content_hash is not None

    def test_sync_dry_run(self, sample_bmad_project: Path, mock_notion_client, monkeypatch):
        """Should not make changes in dry run mode."""
        from bmadnotion.config import load_config
        from bmadnotion.store import Store
        from bmadnotion.page_sync import PageSyncEngine

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        config = load_config(sample_bmad_project)
        store = Store(sample_bmad_project)
        engine = PageSyncEngine(mock_notion_client, store, config)

        result = engine.sync(dry_run=True)

        # Should report what would be done
        assert result.created == 2

        # But no actual API calls
        assert mock_notion_client.create_page.call_count == 0

        # And no store updates
        assert store.get_page_state("prd.md") is None


class TestPageSyncWithMarknotion:
    """Tests for integration with marknotion."""

    def test_converts_markdown_to_blocks(self, sample_bmad_project: Path, mock_notion_client, monkeypatch):
        """Should convert markdown to Notion blocks using marknotion."""
        from bmadnotion.config import load_config
        from bmadnotion.store import Store
        from bmadnotion.page_sync import PageSyncEngine

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        config = load_config(sample_bmad_project)
        store = Store(sample_bmad_project)
        engine = PageSyncEngine(mock_notion_client, store, config)

        engine.sync()

        # Verify append_blocks was called with blocks
        assert mock_notion_client.append_blocks.call_count >= 1
        call_args = mock_notion_client.append_blocks.call_args_list[0]
        blocks = call_args[0][1]  # Second positional argument
        assert isinstance(blocks, list)
        assert len(blocks) > 0


class TestPageSyncDisabled:
    """Tests for disabled page sync."""

    def test_sync_disabled(self, tmp_path: Path, mock_notion_client, monkeypatch):
        """Should do nothing when page_sync is disabled."""
        from bmadnotion.config import load_config
        from bmadnotion.store import Store
        from bmadnotion.page_sync import PageSyncEngine

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        # Create config with page_sync disabled
        (tmp_path / ".bmadnotion.yaml").write_text("""
project: test
notion:
  token_env: NOTION_TOKEN
  workspace_page_id: "abc"
page_sync:
  enabled: false
""")

        config = load_config(tmp_path)
        store = Store(tmp_path)
        engine = PageSyncEngine(mock_notion_client, store, config)

        result = engine.sync()

        assert result.total == 0
        assert mock_notion_client.create_page.call_count == 0
