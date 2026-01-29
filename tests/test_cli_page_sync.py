"""Tests for page sync CLI commands."""

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
  enabled: true
  parent_page_id: "parent123"
  documents:
    - path: "prd.md"
      title: "PRD - {project}"
""")

    # Create planning-artifacts
    planning = tmp_path / "_bmad-output" / "planning-artifacts"
    planning.mkdir(parents=True)
    (planning / "prd.md").write_text("# PRD\n\nContent here.")

    return tmp_path


class TestSyncPagesCommand:
    """Tests for 'bmadnotion sync pages' command."""

    def test_sync_pages_requires_config(self, cli_runner: CliRunner, tmp_path: Path):
        """Should error when no config file exists."""
        from bmadnotion.cli import cli

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(cli, ["sync", "pages"])
        finally:
            os.chdir(original_cwd)

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_sync_pages_requires_token(self, cli_runner: CliRunner, sample_project: Path, monkeypatch):
        """Should error when NOTION_TOKEN is not set."""
        from bmadnotion.cli import cli

        # Ensure NOTION_TOKEN is not set
        monkeypatch.delenv("NOTION_TOKEN", raising=False)

        original_cwd = os.getcwd()
        try:
            os.chdir(sample_project)
            result = cli_runner.invoke(cli, ["sync", "pages"])
        finally:
            os.chdir(original_cwd)

        # Should fail due to missing token
        assert result.exit_code != 0
        assert "token" in result.output.lower() or "notion_token" in result.output.lower()

    @patch("bmadnotion.cli.NotionClient")
    def test_sync_pages_success(self, mock_client_class, cli_runner: CliRunner, sample_project: Path):
        """AC1: Should execute page sync successfully."""
        from bmadnotion.cli import cli

        # Setup mock
        mock_client = MagicMock()
        mock_client.create_page.return_value = {"id": "page123"}
        mock_client_class.return_value = mock_client

        original_cwd = os.getcwd()
        try:
            os.chdir(sample_project)
            result = cli_runner.invoke(
                cli,
                ["sync", "pages"],
                env={"NOTION_TOKEN": "test-token"}
            )
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        assert "sync" in result.output.lower() or "created" in result.output.lower()

    @patch("bmadnotion.cli.NotionClient")
    def test_sync_pages_dry_run(self, mock_client_class, cli_runner: CliRunner, sample_project: Path):
        """AC3: Should preview changes without syncing."""
        from bmadnotion.cli import cli

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        original_cwd = os.getcwd()
        try:
            os.chdir(sample_project)
            result = cli_runner.invoke(
                cli,
                ["sync", "pages", "--dry-run"],
                env={"NOTION_TOKEN": "test-token"}
            )
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        assert "dry" in result.output.lower() or "would" in result.output.lower()
        # No actual API calls
        assert mock_client.create_page.call_count == 0

    @patch("bmadnotion.cli.NotionClient")
    def test_sync_pages_force(self, mock_client_class, cli_runner: CliRunner, sample_project: Path):
        """AC2: Should force sync with --force flag."""
        from bmadnotion.cli import cli

        mock_client = MagicMock()
        mock_client.create_page.return_value = {"id": "page123"}
        mock_client_class.return_value = mock_client

        original_cwd = os.getcwd()
        try:
            os.chdir(sample_project)

            # First sync
            cli_runner.invoke(
                cli,
                ["sync", "pages"],
                env={"NOTION_TOKEN": "test-token"}
            )

            mock_client.reset_mock()

            # Force sync
            result = cli_runner.invoke(
                cli,
                ["sync", "pages", "--force"],
                env={"NOTION_TOKEN": "test-token"}
            )
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0

    @patch("bmadnotion.cli.NotionClient")
    def test_sync_pages_shows_stats(self, mock_client_class, cli_runner: CliRunner, sample_project: Path):
        """AC4: Should display sync statistics."""
        from bmadnotion.cli import cli

        mock_client = MagicMock()
        mock_client.create_page.return_value = {"id": "page123"}
        mock_client_class.return_value = mock_client

        original_cwd = os.getcwd()
        try:
            os.chdir(sample_project)
            result = cli_runner.invoke(
                cli,
                ["sync", "pages"],
                env={"NOTION_TOKEN": "test-token"}
            )
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        # Should show some stats
        output_lower = result.output.lower()
        assert any(word in output_lower for word in ["created", "updated", "skipped", "synced", "1"])
