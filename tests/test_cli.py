"""Tests for bmadnotion CLI."""

import pytest
from click.testing import CliRunner

from bmadnotion.cli import cli


class TestCLIBasic:
    """Basic CLI tests."""

    def test_cli_help(self, cli_runner: CliRunner):
        """CLI --help should show help information."""
        result = cli_runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "bmadnotion" in result.output.lower()
        assert "sync" in result.output.lower()

    def test_cli_version(self, cli_runner: CliRunner):
        """CLI --version should show version."""
        result = cli_runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_sync_pages_help(self, cli_runner: CliRunner):
        """sync pages --help should show help."""
        result = cli_runner.invoke(cli, ["sync", "pages", "--help"])
        assert result.exit_code == 0
        assert "planning artifacts" in result.output.lower()

    def test_sync_db_help(self, cli_runner: CliRunner):
        """sync db --help should show help."""
        result = cli_runner.invoke(cli, ["sync", "db", "--help"])
        assert result.exit_code == 0
        assert "sprint" in result.output.lower() or "database" in result.output.lower()

    def test_status_command(self, cli_runner: CliRunner):
        """status command should run."""
        result = cli_runner.invoke(cli, ["status"])
        assert result.exit_code == 0

    def test_init_command(self, cli_runner: CliRunner):
        """init command should run."""
        result = cli_runner.invoke(cli, ["init"])
        assert result.exit_code == 0
