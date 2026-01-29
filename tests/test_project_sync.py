"""Tests for project sync engine."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock


@pytest.fixture
def sample_config(tmp_path: Path) -> Path:
    """Create a sample config with Projects database configured."""
    config_file = tmp_path / ".bmadnotion.yaml"
    config_file.write_text("""
project: test-project
notion:
  token_env: NOTION_TOKEN
  workspace_page_id: "workspace123"
database_sync:
  enabled: true
  projects:
    database_id: "projects-db-123"
    key_property: "BMADProject"
    name_property: "Project name"
  sprints:
    database_id: "sprints-db-123"
  tasks:
    database_id: "tasks-db-123"
""")
    return tmp_path


@pytest.fixture
def mock_notion_client():
    """Create a mock official notion-client."""
    client = MagicMock()
    # Mock request method (used for database query in notion-client 2.x)
    client.request.return_value = {"results": []}
    # Mock pages.create
    client.pages.create.return_value = {"id": "new-project-page-123"}
    return client


class TestProjectSyncEngine:
    """Tests for ProjectSyncEngine."""

    def test_creates_new_project(self, sample_config: Path, mock_notion_client, monkeypatch):
        """Should create a new Project row when none exists."""
        from bmadnotion.config import load_config
        from bmadnotion.store import Store
        from bmadnotion.project_sync import ProjectSyncEngine

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        config = load_config(sample_config)
        store = Store(sample_config)
        engine = ProjectSyncEngine(mock_notion_client, store, config)

        page_id, was_created = engine.get_or_create_project()

        assert was_created is True
        assert page_id == "new-project-page-123"
        assert mock_notion_client.pages.create.call_count == 1

        # Verify state was saved
        state = store.get_db_state("project:test-project")
        assert state is not None
        assert state.notion_page_id == "new-project-page-123"

    def test_finds_existing_project(self, sample_config: Path, mock_notion_client, monkeypatch):
        """Should find existing Project row by BMADProject key."""
        from bmadnotion.config import load_config
        from bmadnotion.store import Store
        from bmadnotion.project_sync import ProjectSyncEngine

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        # Mock finding existing project
        mock_notion_client.request.return_value = {
            "results": [{"id": "existing-project-456"}]
        }

        config = load_config(sample_config)
        store = Store(sample_config)
        engine = ProjectSyncEngine(mock_notion_client, store, config)

        page_id, was_created = engine.get_or_create_project()

        assert was_created is False
        assert page_id == "existing-project-456"
        assert mock_notion_client.pages.create.call_count == 0

    def test_returns_cached_project(self, sample_config: Path, mock_notion_client, monkeypatch):
        """Should return cached Project ID from store."""
        from bmadnotion.config import load_config
        from bmadnotion.store import Store
        from bmadnotion.project_sync import ProjectSyncEngine
        from bmadnotion.models import DbSyncState

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        config = load_config(sample_config)
        store = Store(sample_config)

        # Pre-populate store
        store.save_db_state(DbSyncState(
            local_key="project:test-project",
            entity_type="project",
            notion_page_id="cached-project-789",
        ))

        engine = ProjectSyncEngine(mock_notion_client, store, config)
        page_id, was_created = engine.get_or_create_project()

        assert was_created is False
        assert page_id == "cached-project-789"
        # No API calls needed
        assert mock_notion_client.request.call_count == 0
        assert mock_notion_client.pages.create.call_count == 0

    def test_dry_run_mode(self, sample_config: Path, mock_notion_client, monkeypatch):
        """Should not create anything in dry run mode."""
        from bmadnotion.config import load_config
        from bmadnotion.store import Store
        from bmadnotion.project_sync import ProjectSyncEngine

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        config = load_config(sample_config)
        store = Store(sample_config)
        engine = ProjectSyncEngine(mock_notion_client, store, config)

        page_id, was_created = engine.get_or_create_project(dry_run=True)

        assert was_created is True
        assert page_id.startswith("dry-run-project-")
        assert mock_notion_client.pages.create.call_count == 0
        assert store.get_db_state("project:test-project") is None

    def test_raises_error_without_database_id(self, tmp_path: Path, mock_notion_client, monkeypatch):
        """Should raise error when Projects database_id is not configured."""
        from bmadnotion.config import load_config
        from bmadnotion.store import Store
        from bmadnotion.project_sync import ProjectSyncEngine

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        # Config without projects database_id
        (tmp_path / ".bmadnotion.yaml").write_text("""
project: test
notion:
  token_env: NOTION_TOKEN
  workspace_page_id: "abc"
database_sync:
  enabled: true
  projects:
    database_id: null
  sprints:
    database_id: "sprints-123"
  tasks:
    database_id: "tasks-123"
""")

        config = load_config(tmp_path)
        store = Store(tmp_path)
        engine = ProjectSyncEngine(mock_notion_client, store, config)

        with pytest.raises(ValueError, match="Projects database_id not configured"):
            engine.get_or_create_project()

    def test_get_project_page_id(self, sample_config: Path, mock_notion_client, monkeypatch):
        """Should return project page ID from store."""
        from bmadnotion.config import load_config
        from bmadnotion.store import Store
        from bmadnotion.project_sync import ProjectSyncEngine
        from bmadnotion.models import DbSyncState

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        config = load_config(sample_config)
        store = Store(sample_config)

        # Initially no project
        engine = ProjectSyncEngine(mock_notion_client, store, config)
        assert engine.get_project_page_id() is None

        # After saving state
        store.save_db_state(DbSyncState(
            local_key="project:test-project",
            entity_type="project",
            notion_page_id="project-page-123",
        ))

        assert engine.get_project_page_id() == "project-page-123"


class TestProjectSyncProperties:
    """Tests for project properties."""

    def test_sets_bmad_project_key(self, sample_config: Path, mock_notion_client, monkeypatch):
        """Should set BMADProject key property when creating."""
        from bmadnotion.config import load_config
        from bmadnotion.store import Store
        from bmadnotion.project_sync import ProjectSyncEngine

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        config = load_config(sample_config)
        store = Store(sample_config)
        engine = ProjectSyncEngine(mock_notion_client, store, config)

        engine.get_or_create_project()

        # Verify pages.create was called with correct properties
        call_args = mock_notion_client.pages.create.call_args
        properties = call_args.kwargs["properties"]

        assert "BMADProject" in properties
        assert properties["BMADProject"]["rich_text"][0]["text"]["content"] == "test-project"

        assert "Project name" in properties
        assert properties["Project name"]["title"][0]["text"]["content"] == "test-project"
