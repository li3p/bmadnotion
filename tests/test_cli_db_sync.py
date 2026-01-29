"""Tests for database sync CLI commands."""

import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from click.testing import CliRunner


@pytest.fixture
def cli_runner():
    """Create a Click CLI runner."""
    return CliRunner()


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """Create a sample project for CLI testing."""
    # Create config
    (tmp_path / ".bmadnotion.yaml").write_text("""
project: cli-test
notion:
  token_env: NOTION_TOKEN
  workspace_page_id: "workspace123"
page_sync:
  enabled: false
database_sync:
  enabled: true
  sprints:
    database_id: "sprints-db-123"
  tasks:
    database_id: "tasks-db-456"
""")

    # Create implementation-artifacts with sprint-status.yaml
    impl = tmp_path / "_bmad-output" / "implementation-artifacts"
    impl.mkdir(parents=True)
    (impl / "sprint-status.yaml").write_text("""
development_status:
  epic-1: in-progress
  1-1-backend-setup: done
""")

    # Create epic file
    epics_dir = tmp_path / "_bmad-output" / "planning-artifacts" / "epics"
    epics_dir.mkdir(parents=True)
    (epics_dir / "epic-1-main.md").write_text("# Epic 1: Main Feature\n\nDescription.")

    # Create story file
    (impl / "1-1-backend-setup.md").write_text("# Story 1.1: Backend Setup\n\nContent here.")

    return tmp_path


class TestSyncDbCommand:
    """Tests for 'bmadnotion sync db' command."""

    def test_sync_db_requires_config(self, cli_runner: CliRunner, tmp_path: Path):
        """Should error when no config file exists."""
        from bmadnotion.cli import cli

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(cli, ["sync", "db"])
        finally:
            os.chdir(original_cwd)

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_sync_db_requires_token(self, cli_runner: CliRunner, sample_project: Path, monkeypatch):
        """Should error when NOTION_TOKEN is not set."""
        from bmadnotion.cli import cli

        # Ensure NOTION_TOKEN is not set
        monkeypatch.delenv("NOTION_TOKEN", raising=False)

        original_cwd = os.getcwd()
        try:
            os.chdir(sample_project)
            result = cli_runner.invoke(cli, ["sync", "db"])
        finally:
            os.chdir(original_cwd)

        # Should fail due to missing token
        assert result.exit_code != 0
        assert "token" in result.output.lower() or "notion_token" in result.output.lower()

    @patch("bmadnotion.cli.NotionClient")
    def test_sync_db_success(self, mock_client_class, cli_runner: CliRunner, sample_project: Path):
        """AC1: Should execute database sync successfully."""
        from bmadnotion.cli import cli

        # Setup mock
        mock_client = MagicMock()
        mock_client.create_database_entry.return_value = {"id": "page123"}
        mock_client_class.return_value = mock_client

        original_cwd = os.getcwd()
        try:
            os.chdir(sample_project)
            result = cli_runner.invoke(
                cli,
                ["sync", "db"],
                env={"NOTION_TOKEN": "test-token"}
            )
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        # Should show some sync output
        assert "sync" in result.output.lower() or "epic" in result.output.lower() or "stor" in result.output.lower()

    @patch("bmadnotion.cli.NotionClient")
    def test_sync_db_dry_run(self, mock_client_class, cli_runner: CliRunner, sample_project: Path):
        """AC2: Should preview changes without syncing."""
        from bmadnotion.cli import cli

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        original_cwd = os.getcwd()
        try:
            os.chdir(sample_project)
            result = cli_runner.invoke(
                cli,
                ["sync", "db", "--dry-run"],
                env={"NOTION_TOKEN": "test-token"}
            )
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        assert "dry" in result.output.lower() or "would" in result.output.lower()
        # No actual API calls
        assert mock_client.create_database_entry.call_count == 0

    @patch("bmadnotion.cli.NotionClient")
    def test_sync_db_force(self, mock_client_class, cli_runner: CliRunner, sample_project: Path):
        """AC2: Should force sync with --force flag."""
        from bmadnotion.cli import cli

        mock_client = MagicMock()
        mock_client.create_database_entry.return_value = {"id": "page123"}
        mock_client_class.return_value = mock_client

        original_cwd = os.getcwd()
        try:
            os.chdir(sample_project)

            # First sync
            cli_runner.invoke(
                cli,
                ["sync", "db"],
                env={"NOTION_TOKEN": "test-token"}
            )

            mock_client.reset_mock()

            # Force sync
            result = cli_runner.invoke(
                cli,
                ["sync", "db", "--force"],
                env={"NOTION_TOKEN": "test-token"}
            )
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0

    @patch("bmadnotion.cli.NotionClient")
    def test_sync_db_shows_stats(self, mock_client_class, cli_runner: CliRunner, sample_project: Path):
        """AC3: Should display sync statistics."""
        from bmadnotion.cli import cli

        mock_client = MagicMock()
        mock_client.create_database_entry.return_value = {"id": "page123"}
        mock_client_class.return_value = mock_client

        original_cwd = os.getcwd()
        try:
            os.chdir(sample_project)
            result = cli_runner.invoke(
                cli,
                ["sync", "db"],
                env={"NOTION_TOKEN": "test-token"}
            )
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        # Should show epic and story stats
        output_lower = result.output.lower()
        assert "epic" in output_lower or "sprint" in output_lower
        assert "stor" in output_lower or "task" in output_lower


class TestCombinedSyncCommand:
    """Tests for 'bmadnotion sync' combined command (Task 3.3)."""

    @patch("bmadnotion.cli.NotionClient")
    def test_sync_all(self, mock_client_class, cli_runner: CliRunner, sample_project: Path):
        """AC1: sync without subcommand should sync all."""
        from bmadnotion.cli import cli

        # Add page_sync documents to config
        config_path = sample_project / ".bmadnotion.yaml"
        config_path.write_text("""
project: cli-test
notion:
  token_env: NOTION_TOKEN
  workspace_page_id: "workspace123"
page_sync:
  enabled: true
  parent_page_id: "parent123"
  documents:
    - path: "prd.md"
      title: "PRD"
database_sync:
  enabled: true
  sprints:
    database_id: "sprints-db-123"
  tasks:
    database_id: "tasks-db-456"
""")
        # Create PRD file
        planning = sample_project / "_bmad-output" / "planning-artifacts"
        planning.mkdir(parents=True, exist_ok=True)
        (planning / "prd.md").write_text("# PRD\n\nContent.")

        mock_client = MagicMock()
        mock_client.create_page.return_value = {"id": "page123"}
        mock_client.create_database_entry.return_value = {"id": "entry123"}
        mock_client_class.return_value = mock_client

        original_cwd = os.getcwd()
        try:
            os.chdir(sample_project)
            result = cli_runner.invoke(
                cli,
                ["sync"],
                env={"NOTION_TOKEN": "test-token"}
            )
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        # Should have synced both pages and database
        output_lower = result.output.lower()
        assert "page" in output_lower or "created" in output_lower
        assert "epic" in output_lower or "sprint" in output_lower or "stor" in output_lower

    @patch("bmadnotion.cli.NotionClient")
    def test_sync_error_isolation(self, mock_client_class, cli_runner: CliRunner, sample_project: Path):
        """AC4: Error in one sync should not stop others."""
        from bmadnotion.cli import cli

        mock_client = MagicMock()
        # Page sync will fail
        mock_client.create_page.side_effect = Exception("Page sync failed")
        # But database sync should work
        mock_client.create_database_entry.return_value = {"id": "entry123"}
        mock_client_class.return_value = mock_client

        # Add page_sync documents
        config_path = sample_project / ".bmadnotion.yaml"
        config_path.write_text("""
project: cli-test
notion:
  token_env: NOTION_TOKEN
  workspace_page_id: "workspace123"
page_sync:
  enabled: true
  parent_page_id: "parent123"
  documents:
    - path: "prd.md"
      title: "PRD"
database_sync:
  enabled: true
  sprints:
    database_id: "sprints-db-123"
  tasks:
    database_id: "tasks-db-456"
""")
        planning = sample_project / "_bmad-output" / "planning-artifacts"
        planning.mkdir(parents=True, exist_ok=True)
        (planning / "prd.md").write_text("# PRD\n\nContent.")

        original_cwd = os.getcwd()
        try:
            os.chdir(sample_project)
            result = cli_runner.invoke(
                cli,
                ["sync"],
                env={"NOTION_TOKEN": "test-token"}
            )
        finally:
            os.chdir(original_cwd)

        # Should complete (possibly with errors) but not crash
        # Database sync should still have been attempted
        assert mock_client.create_database_entry.call_count > 0
