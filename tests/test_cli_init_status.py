"""Tests for init and status CLI commands."""

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
def bmad_project(tmp_path: Path) -> Path:
    """Create a BMAD project structure for testing init command."""
    # Create _bmad/bmm/config.yaml (required for init)
    bmad_dir = tmp_path / "_bmad" / "bmm"
    bmad_dir.mkdir(parents=True)
    (bmad_dir / "config.yaml").write_text("""
project_name: test-project
planning_artifacts: "{project-root}/_bmad-output/planning-artifacts"
implementation_artifacts: "{project-root}/_bmad-output/implementation-artifacts"
""")

    # Create planning-artifacts
    planning = tmp_path / "_bmad-output" / "planning-artifacts"
    planning.mkdir(parents=True)
    (planning / "prd.md").write_text("# PRD\n\nContent here.")
    (planning / "architecture.md").write_text("# Architecture\n\nContent here.")

    # Create implementation-artifacts with sprint-status
    impl = tmp_path / "_bmad-output" / "implementation-artifacts"
    impl.mkdir(parents=True)
    (impl / "sprint-status.yaml").write_text("""
development_status:
  epic-1: in-progress
  1-1-backend-setup: done
""")
    (impl / "1-1-backend-setup.md").write_text("# Story 1.1\n\nContent.")

    return tmp_path


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """Create a sample project for testing."""
    # Create config
    (tmp_path / ".bmadnotion.yaml").write_text("""
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
database_sync:
  enabled: true
  sprints:
    database_id: "sprints-db-123"
  tasks:
    database_id: "tasks-db-456"
""")

    # Create planning-artifacts
    planning = tmp_path / "_bmad-output" / "planning-artifacts"
    planning.mkdir(parents=True)
    (planning / "prd.md").write_text("# PRD\n\nContent here.")

    # Create epics dir
    epics_dir = planning / "epics"
    epics_dir.mkdir()
    (epics_dir / "epic-1-main.md").write_text("# Epic 1: Main Feature\n\nDescription.")

    # Create implementation-artifacts with sprint-status
    impl = tmp_path / "_bmad-output" / "implementation-artifacts"
    impl.mkdir(parents=True)
    (impl / "sprint-status.yaml").write_text("""
development_status:
  epic-1: in-progress
  1-1-backend-setup: done
""")
    (impl / "1-1-backend-setup.md").write_text("# Story 1.1\n\nContent.")

    return tmp_path


class TestInitCommand:
    """Tests for 'bmadnotion init' command."""

    def test_init_requires_bmad_project(self, cli_runner: CliRunner, tmp_path: Path):
        """Should fail if not a BMAD project."""
        from bmadnotion.cli import cli

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(cli, ["init", "--skip-notion"])
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 1
        assert "not a bmad project" in result.output.lower()

    def test_init_creates_config(self, cli_runner: CliRunner, bmad_project: Path):
        """AC1: Should create .bmadnotion.yaml configuration file."""
        from bmadnotion.cli import cli

        original_cwd = os.getcwd()
        try:
            os.chdir(bmad_project)
            # Use --skip-notion to avoid Notion API calls, provide input for project name prompt
            result = cli_runner.invoke(
                cli,
                ["init", "--skip-notion"],
                input="test-project\n",  # Project name confirmation
            )
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0, f"Failed with output: {result.output}"
        config_file = bmad_project / ".bmadnotion.yaml"
        assert config_file.exists()
        content = config_file.read_text()
        assert "test-project" in content
        assert "notion" in content

    def test_init_uses_project_option(self, cli_runner: CliRunner, bmad_project: Path):
        """Should use --project option to skip prompt."""
        from bmadnotion.cli import cli

        original_cwd = os.getcwd()
        try:
            os.chdir(bmad_project)
            result = cli_runner.invoke(
                cli,
                ["init", "--project", "my-project", "--skip-notion"],
            )
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        config_file = bmad_project / ".bmadnotion.yaml"
        assert config_file.exists()
        content = config_file.read_text()
        assert "my-project" in content

    def test_init_warns_if_config_exists(self, cli_runner: CliRunner, bmad_project: Path):
        """Should warn if config already exists."""
        from bmadnotion.cli import cli

        # Create existing config
        (bmad_project / ".bmadnotion.yaml").write_text("project: existing")

        original_cwd = os.getcwd()
        try:
            os.chdir(bmad_project)
            result = cli_runner.invoke(
                cli,
                ["init", "--skip-notion"],
                input="n\n",  # Don't overwrite
            )
        finally:
            os.chdir(original_cwd)

        # Should ask about overwrite
        assert "overwrite" in result.output.lower() or "exists" in result.output.lower()
        # Original content should be preserved
        content = (bmad_project / ".bmadnotion.yaml").read_text()
        assert "existing" in content

    def test_init_force_overwrites(self, cli_runner: CliRunner, bmad_project: Path):
        """Should overwrite config with --force."""
        from bmadnotion.cli import cli

        # Create existing config
        (bmad_project / ".bmadnotion.yaml").write_text("project: old-project")

        original_cwd = os.getcwd()
        try:
            os.chdir(bmad_project)
            result = cli_runner.invoke(
                cli,
                ["init", "--project", "new-project", "--force", "--skip-notion"],
            )
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        content = (bmad_project / ".bmadnotion.yaml").read_text()
        assert "new-project" in content

    def test_init_detects_artifacts(self, cli_runner: CliRunner, bmad_project: Path):
        """Should detect planning artifacts."""
        from bmadnotion.cli import cli

        original_cwd = os.getcwd()
        try:
            os.chdir(bmad_project)
            result = cli_runner.invoke(
                cli,
                ["init", "--project", "test", "--skip-notion"],
            )
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        assert "prd.md" in result.output.lower()
        assert "architecture.md" in result.output.lower()


class TestStatusCommand:
    """Tests for 'bmadnotion status' command."""

    def test_status_requires_config(self, cli_runner: CliRunner, tmp_path: Path):
        """Should error when no config file exists."""
        from bmadnotion.cli import cli

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(cli, ["status"])
        finally:
            os.chdir(original_cwd)

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_status_shows_sync_state(self, cli_runner: CliRunner, sample_project: Path, monkeypatch):
        """AC2: Should display sync status."""
        from bmadnotion.cli import cli

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        original_cwd = os.getcwd()
        try:
            os.chdir(sample_project)
            result = cli_runner.invoke(cli, ["status"])
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        # Should show some status info
        output_lower = result.output.lower()
        assert any(word in output_lower for word in ["page", "document", "epic", "story", "status", "sync"])

    def test_status_shows_pending_changes(self, cli_runner: CliRunner, sample_project: Path, monkeypatch):
        """AC3: Should show what needs to be synced."""
        from bmadnotion.cli import cli

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        original_cwd = os.getcwd()
        try:
            os.chdir(sample_project)
            result = cli_runner.invoke(cli, ["status"])
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        # Should show pending items (nothing synced yet)
        output_lower = result.output.lower()
        assert any(word in output_lower for word in ["pending", "new", "not synced", "to sync", "1"])

    @patch("bmadnotion.cli.NotionClient")
    def test_status_after_sync(self, mock_client_class, cli_runner: CliRunner, sample_project: Path, monkeypatch):
        """Should show synced status after successful sync."""
        from bmadnotion.cli import cli

        monkeypatch.setenv("NOTION_TOKEN", "test-token")

        mock_client = MagicMock()
        mock_client.create_page.return_value = {"id": "page123"}
        mock_client.create_database_entry.return_value = {"id": "entry123"}
        mock_client_class.return_value = mock_client

        original_cwd = os.getcwd()
        try:
            os.chdir(sample_project)
            # First sync
            cli_runner.invoke(cli, ["sync"], env={"NOTION_TOKEN": "test-token"})
            # Then check status
            result = cli_runner.invoke(cli, ["status"])
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        output_lower = result.output.lower()
        # Should show synced items
        assert any(word in output_lower for word in ["synced", "up to date", "✓", "done"])
