"""Tests for bmadnotion configuration system."""

import os
import pytest
from pathlib import Path


class TestLoadConfig:
    """Tests for loading configuration."""

    def test_load_config_from_yaml(self, tmp_path: Path):
        """AC1: Should load .bmadnotion.yaml configuration file."""
        from bmadnotion.config import load_config

        config_file = tmp_path / ".bmadnotion.yaml"
        config_file.write_text("""
project: test-project
notion:
  token_env: NOTION_TOKEN
  workspace_page_id: "abc123"
paths:
  bmad_output: "_bmad-output"
  planning_artifacts: "_bmad-output/planning-artifacts"
  implementation_artifacts: "_bmad-output/implementation-artifacts"
""")

        config = load_config(tmp_path)

        assert config.project == "test-project"
        assert config.notion.workspace_page_id == "abc123"
        assert config.notion.token_env == "NOTION_TOKEN"

    def test_config_not_found(self, tmp_path: Path):
        """AC2: Should raise clear error when config file is missing."""
        from bmadnotion.config import load_config, ConfigNotFoundError

        with pytest.raises(ConfigNotFoundError) as exc:
            load_config(tmp_path)

        assert ".bmadnotion.yaml" in str(exc.value)

    def test_notion_token_from_env(self, tmp_path: Path, monkeypatch):
        """AC3: Should read Notion token from environment variable."""
        from bmadnotion.config import load_config

        monkeypatch.setenv("MY_NOTION_TOKEN", "secret_test_token_123")

        config_file = tmp_path / ".bmadnotion.yaml"
        config_file.write_text("""
project: test-project
notion:
  token_env: MY_NOTION_TOKEN
  workspace_page_id: "abc123"
""")

        config = load_config(tmp_path)
        token = config.get_notion_token()

        assert token == "secret_test_token_123"

    def test_notion_token_missing_env(self, tmp_path: Path, monkeypatch):
        """AC3: Should raise error when token env var is not set."""
        from bmadnotion.config import load_config, TokenNotFoundError

        # Ensure the env var is not set
        monkeypatch.delenv("NOTION_TOKEN", raising=False)

        config_file = tmp_path / ".bmadnotion.yaml"
        config_file.write_text("""
project: test-project
notion:
  token_env: NOTION_TOKEN
  workspace_page_id: "abc123"
""")

        config = load_config(tmp_path)

        with pytest.raises(TokenNotFoundError) as exc:
            config.get_notion_token()

        assert "NOTION_TOKEN" in str(exc.value)

    def test_auto_discover_bmad_paths(self, tmp_path: Path):
        """AC4: Should auto-discover paths from _bmad/bmm/config.yaml."""
        from bmadnotion.config import load_config

        # Create _bmad/bmm/config.yaml
        bmad_config_dir = tmp_path / "_bmad" / "bmm"
        bmad_config_dir.mkdir(parents=True)
        (bmad_config_dir / "config.yaml").write_text("""
planning_artifacts: "{project-root}/_bmad-output/planning-artifacts"
implementation_artifacts: "{project-root}/_bmad-output/implementation-artifacts"
output_folder: "{project-root}/_bmad-output"
""")

        # Create minimal .bmadnotion.yaml (no paths specified)
        config_file = tmp_path / ".bmadnotion.yaml"
        config_file.write_text("""
project: test-project
notion:
  token_env: NOTION_TOKEN
  workspace_page_id: "abc123"
""")

        config = load_config(tmp_path)

        # Paths should be auto-discovered
        assert config.paths.planning_artifacts == tmp_path / "_bmad-output" / "planning-artifacts"
        assert config.paths.implementation_artifacts == tmp_path / "_bmad-output" / "implementation-artifacts"


class TestConfigPaths:
    """Tests for configuration path handling."""

    def test_paths_resolved_to_absolute(self, tmp_path: Path):
        """Paths should be resolved to absolute paths."""
        from bmadnotion.config import load_config

        config_file = tmp_path / ".bmadnotion.yaml"
        config_file.write_text("""
project: test-project
notion:
  token_env: NOTION_TOKEN
  workspace_page_id: "abc123"
paths:
  bmad_output: "_bmad-output"
  planning_artifacts: "_bmad-output/planning-artifacts"
  implementation_artifacts: "_bmad-output/implementation-artifacts"
  sprint_status: "_bmad-output/implementation-artifacts/sprint-status.yaml"
""")

        config = load_config(tmp_path)

        assert config.paths.bmad_output.is_absolute()
        assert config.paths.planning_artifacts.is_absolute()
        assert str(config.paths.planning_artifacts).startswith(str(tmp_path))

    def test_default_paths(self, tmp_path: Path):
        """Should use default paths when not specified."""
        from bmadnotion.config import load_config

        config_file = tmp_path / ".bmadnotion.yaml"
        config_file.write_text("""
project: test-project
notion:
  token_env: NOTION_TOKEN
  workspace_page_id: "abc123"
""")

        config = load_config(tmp_path)

        # Default paths should be set
        assert config.paths.bmad_output == tmp_path / "_bmad-output"
        assert config.paths.sprint_status == tmp_path / "_bmad-output" / "implementation-artifacts" / "sprint-status.yaml"


class TestPageSyncConfig:
    """Tests for page sync configuration."""

    def test_page_sync_documents(self, tmp_path: Path):
        """Should parse page sync document configuration."""
        from bmadnotion.config import load_config

        config_file = tmp_path / ".bmadnotion.yaml"
        config_file.write_text("""
project: my-project
notion:
  token_env: NOTION_TOKEN
  workspace_page_id: "abc123"
page_sync:
  enabled: true
  parent_page_id: "parent123"
  documents:
    - path: "prd.md"
      title: "PRD - {project}"
    - path: "architecture.md"
      title: "Architecture - {project}"
""")

        config = load_config(tmp_path)

        assert config.page_sync.enabled is True
        assert config.page_sync.parent_page_id == "parent123"
        assert len(config.page_sync.documents) == 2
        assert config.page_sync.documents[0].path == "prd.md"
        assert config.page_sync.documents[0].title == "PRD - {project}"


class TestDatabaseSyncConfig:
    """Tests for database sync configuration."""

    def test_database_sync_status_mapping(self, tmp_path: Path):
        """Should parse database sync status mapping."""
        from bmadnotion.config import load_config

        config_file = tmp_path / ".bmadnotion.yaml"
        config_file.write_text("""
project: my-project
notion:
  token_env: NOTION_TOKEN
  workspace_page_id: "abc123"
database_sync:
  enabled: true
  sprints:
    database_id: "sprints-db-id"
    status_mapping:
      backlog: "Not Started"
      in-progress: "In Progress"
      done: "Done"
  tasks:
    database_id: "tasks-db-id"
    status_mapping:
      backlog: "Backlog"
      ready-for-dev: "Ready"
      in-progress: "In Progress"
      review: "Review"
      done: "Done"
""")

        config = load_config(tmp_path)

        assert config.database_sync.enabled is True
        assert config.database_sync.sprints.database_id == "sprints-db-id"
        assert config.database_sync.sprints.status_mapping["in-progress"] == "In Progress"
        assert config.database_sync.tasks.status_mapping["ready-for-dev"] == "Ready"
