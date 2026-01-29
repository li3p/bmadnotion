"""Pytest configuration and fixtures for bmadnotion tests."""

import pytest
from pathlib import Path
from click.testing import CliRunner


@pytest.fixture
def cli_runner():
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory with basic structure."""
    # Create BMAD output directories
    planning = tmp_path / "_bmad-output" / "planning-artifacts"
    planning.mkdir(parents=True)

    impl = tmp_path / "_bmad-output" / "implementation-artifacts"
    impl.mkdir(parents=True)

    epics = planning / "epics"
    epics.mkdir()

    return tmp_path


@pytest.fixture
def sample_bmad_project(tmp_project: Path) -> Path:
    """Create a sample BMAD project with test data."""
    # Create planning artifacts
    planning = tmp_project / "_bmad-output" / "planning-artifacts"

    (planning / "prd.md").write_text("""# Product Requirements Document

## Overview
This is a test PRD.

## Requirements
- REQ-001: User authentication
- REQ-002: Dashboard
""")

    (planning / "architecture.md").write_text("""# Architecture

## Overview
System architecture document.

## Components
- Frontend: React
- Backend: FastAPI
""")

    # Create epic file
    epics = planning / "epics"
    (epics / "epic-1-user-auth.md").write_text("""# Epic 1: User Authentication

## Story 1.1: Login Page
As a user,
I want to log in with my credentials,
So that I can access the system.

**Acceptance Criteria:**
- Given valid credentials, login succeeds
- Given invalid credentials, show error

## Story 1.2: Logout
As a user,
I want to log out,
So that my session is ended.
""")

    # Create sprint status
    impl = tmp_project / "_bmad-output" / "implementation-artifacts"
    (impl / "sprint-status.yaml").write_text("""generated: 2026-01-29
project: test-project
project_key: test
tracking_system: file-system
story_location: _bmad-output/implementation-artifacts

development_status:
  epic-1: in-progress
  1-1-login-page: done
  1-2-logout: ready-for-dev
  epic-1-retrospective: optional
""")

    # Create story file for 1-1
    (impl / "1-1-login-page.md").write_text("""# Story 1.1: Login Page

Status: done

## Story
As a user,
I want to log in with my credentials,
so that I can access the system.

## Acceptance Criteria
1. Given valid credentials, login succeeds
2. Given invalid credentials, show error

## Tasks / Subtasks
- [x] Task 1: Create login form
- [x] Task 2: Implement authentication API
""")

    # Create bmadnotion config
    (tmp_project / ".bmadnotion.yaml").write_text("""project: test-project
notion:
  token_env: NOTION_TOKEN
  workspace_page_id: "test-workspace-id"

paths:
  bmad_output: "_bmad-output"
  planning_artifacts: "_bmad-output/planning-artifacts"
  implementation_artifacts: "_bmad-output/implementation-artifacts"
  epics_dir: "_bmad-output/planning-artifacts/epics"
  sprint_status: "_bmad-output/implementation-artifacts/sprint-status.yaml"

page_sync:
  enabled: true
  parent_page_id: "test-parent-id"
  documents:
    - path: "prd.md"
      title: "PRD - {project}"
    - path: "architecture.md"
      title: "Architecture - {project}"

database_sync:
  enabled: true
  sprints:
    database_id: "test-sprints-db"
    status_mapping:
      backlog: "Not Started"
      in-progress: "In Progress"
      done: "Done"
  tasks:
    database_id: "test-tasks-db"
    status_mapping:
      backlog: "Backlog"
      ready-for-dev: "Ready"
      in-progress: "In Progress"
      review: "Review"
      done: "Done"
""")

    return tmp_project
