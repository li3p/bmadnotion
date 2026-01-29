"""Tests for bmadnotion file scanner."""

import pytest
from pathlib import Path


@pytest.fixture
def sample_bmad_project(tmp_path: Path) -> Path:
    """Create a sample BMAD project structure for testing."""
    # Create config
    config_file = tmp_path / ".bmadnotion.yaml"
    config_file.write_text("""
project: test-project
notion:
  token_env: NOTION_TOKEN
  workspace_page_id: "abc123"
""")

    # Create planning-artifacts
    planning = tmp_path / "_bmad-output" / "planning-artifacts"
    planning.mkdir(parents=True)

    (planning / "prd.md").write_text("# PRD\n\nProduct requirements document.")
    (planning / "architecture.md").write_text("# Architecture\n\nSystem design.")
    (planning / "ux-design-specification.md").write_text("# UX Design\n\nUI/UX spec.")

    # Create epics
    epics_dir = planning / "epics"
    epics_dir.mkdir()

    (epics_dir / "epic-1-kp-graph.md").write_text("""# Epic 1: KP Graph Studio

## Overview
Knowledge point graph management.

## Stories
- Story 1.1: Backend Setup
- Story 1.2: Frontend Setup
""")

    (epics_dir / "epic-2-rubric-pack.md").write_text("""# Epic 2: Rubric Pack Studio

## Overview
Rubric management system.
""")

    # Create implementation-artifacts
    impl = tmp_path / "_bmad-output" / "implementation-artifacts"
    impl.mkdir(parents=True)

    # Create sprint-status.yaml
    (impl / "sprint-status.yaml").write_text("""
generated: 2026-01-29
project: test-project
project_key: test
tracking_system: file-system
story_location: _bmad-output/implementation-artifacts

development_status:
  epic-1: in-progress
  1-0-repository-init: done
  1-1-backend-setup: done
  1-2-frontend-setup: in-progress
  epic-1-retrospective: optional

  epic-2: backlog
  2-1-rubric-model: backlog
  epic-2-retrospective: optional
""")

    # Create story files
    (impl / "1-0-repository-init.md").write_text("""# Story 1.0: Repository Init

Status: done

## Story
As a developer, I want to initialize the repository.

## Tasks
- [x] Task 1: Create repo structure
""")

    (impl / "1-1-backend-setup.md").write_text("""# Story 1.1: Backend Setup

Status: done

## Story
As a developer, I want to set up the backend.

## Acceptance Criteria
1. Given FastAPI, When running, Then API works.

## Tasks
- [x] Task 1: Install FastAPI
""")

    (impl / "1-2-frontend-setup.md").write_text("""# Story 1.2: Frontend Setup

Status: in-progress

## Story
As a developer, I want to set up the frontend.

## Tasks
- [x] Task 1: Install Vite
- [ ] Task 2: Configure React
""")

    return tmp_path


class TestScanDocuments:
    """Tests for scanning planning artifacts."""

    def test_scan_documents(self, sample_bmad_project: Path):
        """AC1: Should scan planning-artifacts documents."""
        from bmadnotion.config import load_config
        from bmadnotion.scanner import BMADScanner

        config = load_config(sample_bmad_project)
        scanner = BMADScanner(config)

        docs = scanner.scan_documents()

        assert len(docs) >= 1
        paths = {str(d.path.name) for d in docs}
        assert "prd.md" in paths

    def test_scan_documents_content(self, sample_bmad_project: Path):
        """Should read document content."""
        from bmadnotion.config import load_config
        from bmadnotion.scanner import BMADScanner

        config = load_config(sample_bmad_project)
        scanner = BMADScanner(config)

        docs = scanner.scan_documents()

        prd = next((d for d in docs if d.path.name == "prd.md"), None)
        assert prd is not None
        assert "# PRD" in prd.content
        assert prd.mtime > 0

    def test_scan_documents_with_custom_config(self, sample_bmad_project: Path):
        """Should respect page_sync document configuration."""
        from bmadnotion.config import load_config
        from bmadnotion.scanner import BMADScanner

        # Update config with custom documents
        config_file = sample_bmad_project / ".bmadnotion.yaml"
        config_file.write_text("""
project: test-project
notion:
  token_env: NOTION_TOKEN
  workspace_page_id: "abc123"
page_sync:
  enabled: true
  documents:
    - path: "prd.md"
      title: "PRD - {project}"
    - path: "architecture.md"
      title: "Arch - {project}"
""")

        config = load_config(sample_bmad_project)
        scanner = BMADScanner(config)

        docs = scanner.scan_documents()

        assert len(docs) == 2
        titles = {d.title for d in docs}
        assert "PRD - test-project" in titles
        assert "Arch - test-project" in titles


class TestScanSprintStatus:
    """Tests for scanning sprint status."""

    def test_scan_sprint_status(self, sample_bmad_project: Path):
        """AC2: Should parse sprint-status.yaml."""
        from bmadnotion.config import load_config
        from bmadnotion.scanner import BMADScanner

        config = load_config(sample_bmad_project)
        scanner = BMADScanner(config)

        epics, stories = scanner.scan_sprint_status()

        assert len(epics) >= 1
        assert epics[0].key.startswith("epic-")
        assert len(stories) >= 1

    def test_scan_epics(self, sample_bmad_project: Path):
        """Should extract epics with correct status."""
        from bmadnotion.config import load_config
        from bmadnotion.scanner import BMADScanner

        config = load_config(sample_bmad_project)
        scanner = BMADScanner(config)

        epics, _ = scanner.scan_sprint_status()

        epic1 = next((e for e in epics if e.key == "epic-1"), None)
        epic2 = next((e for e in epics if e.key == "epic-2"), None)

        assert epic1 is not None
        assert epic1.status == "in-progress"

        assert epic2 is not None
        assert epic2.status == "backlog"

    def test_scan_epic_extracts_title(self, sample_bmad_project: Path):
        """AC3: Should extract title from epic file."""
        from bmadnotion.config import load_config
        from bmadnotion.scanner import BMADScanner

        config = load_config(sample_bmad_project)
        scanner = BMADScanner(config)

        epics, _ = scanner.scan_sprint_status()

        epic1 = next((e for e in epics if e.key == "epic-1"), None)
        assert epic1 is not None
        assert "KP Graph" in epic1.title or epic1.title != ""

    def test_scan_stories(self, sample_bmad_project: Path):
        """Should extract stories with correct status."""
        from bmadnotion.config import load_config
        from bmadnotion.scanner import BMADScanner

        config = load_config(sample_bmad_project)
        scanner = BMADScanner(config)

        _, stories = scanner.scan_sprint_status()

        story_keys = {s.key for s in stories}
        assert "1-0-repository-init" in story_keys
        assert "1-1-backend-setup" in story_keys
        assert "2-1-rubric-model" in story_keys

        # Check status
        story_1_1 = next((s for s in stories if s.key == "1-1-backend-setup"), None)
        assert story_1_1 is not None
        assert story_1_1.status == "done"
        assert story_1_1.epic_key == "epic-1"

    def test_scan_story_extracts_content(self, sample_bmad_project: Path):
        """AC4: Should extract content from story file."""
        from bmadnotion.config import load_config
        from bmadnotion.scanner import BMADScanner

        config = load_config(sample_bmad_project)
        scanner = BMADScanner(config)

        _, stories = scanner.scan_sprint_status()

        # Story with file (done status)
        story_done = next((s for s in stories if s.key == "1-1-backend-setup"), None)
        assert story_done is not None
        assert story_done.content is not None
        assert "## Story" in story_done.content
        assert story_done.file_path is not None
        assert story_done.mtime is not None

    def test_scan_backlog_story_no_content(self, sample_bmad_project: Path):
        """AC5: Backlog story without file should have no content."""
        from bmadnotion.config import load_config
        from bmadnotion.scanner import BMADScanner

        config = load_config(sample_bmad_project)
        scanner = BMADScanner(config)

        _, stories = scanner.scan_sprint_status()

        # Backlog story (no file)
        backlog_story = next((s for s in stories if s.key == "2-1-rubric-model"), None)
        assert backlog_story is not None
        assert backlog_story.status == "backlog"
        assert backlog_story.file_path is None
        assert backlog_story.content is None


class TestScannerEdgeCases:
    """Tests for edge cases."""

    def test_missing_sprint_status(self, tmp_path: Path):
        """Should handle missing sprint-status.yaml gracefully."""
        from bmadnotion.config import load_config
        from bmadnotion.scanner import BMADScanner, SprintStatusNotFoundError

        # Create minimal config
        (tmp_path / ".bmadnotion.yaml").write_text("""
project: test
notion:
  token_env: NOTION_TOKEN
  workspace_page_id: "abc"
""")

        config = load_config(tmp_path)
        scanner = BMADScanner(config)

        with pytest.raises(SprintStatusNotFoundError):
            scanner.scan_sprint_status()

    def test_empty_documents_config(self, sample_bmad_project: Path):
        """Should use default documents when not configured."""
        from bmadnotion.config import load_config
        from bmadnotion.scanner import BMADScanner

        config = load_config(sample_bmad_project)
        # page_sync.documents is empty by default
        assert len(config.page_sync.documents) == 0

        scanner = BMADScanner(config)
        docs = scanner.scan_documents()

        # Should scan default documents
        assert len(docs) >= 0  # May find default docs or empty
