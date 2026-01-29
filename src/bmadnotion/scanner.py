"""BMAD project file scanner."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from bmadnotion.config import Config
from bmadnotion.models import Document, Epic, Story


class SprintStatusNotFoundError(Exception):
    """Raised when sprint-status.yaml is not found."""

    pass


# Default documents to scan when not configured
DEFAULT_DOCUMENTS = [
    {"path": "prd.md", "title": "PRD - {project}"},
    {"path": "architecture.md", "title": "Architecture - {project}"},
    {"path": "ux-design-specification.md", "title": "UX Design - {project}"},
    {"path": "product-brief.md", "title": "Product Brief - {project}"},
]


class BMADScanner:
    """Scanner for BMAD project structure.

    Scans planning-artifacts and implementation-artifacts directories
    to extract documents, epics, and stories for syncing.
    """

    def __init__(self, config: Config):
        """Initialize the scanner.

        Args:
            config: The loaded configuration.
        """
        self.config = config

    def scan_documents(self) -> list[Document]:
        """Scan planning-artifacts for documents to sync.

        Returns:
            List of Document objects representing documents to sync.
        """
        documents = []

        # Use configured documents or defaults
        doc_configs = self.config.page_sync.documents
        if not doc_configs:
            # Use defaults
            doc_configs = [
                type("DocConfig", (), {"path": d["path"], "title": d["title"]})()
                for d in DEFAULT_DOCUMENTS
            ]

        for doc_config in doc_configs:
            doc_path = self.config.paths.planning_artifacts / doc_config.path

            if not doc_path.exists():
                continue

            content = doc_path.read_text()
            mtime = doc_path.stat().st_mtime

            # Format title with project name
            title = doc_config.title.format(project=self.config.project)

            documents.append(Document(
                path=doc_path,
                title=title,
                content=content,
                mtime=mtime,
            ))

        return documents

    def scan_sprint_status(self) -> tuple[list[Epic], list[Story]]:
        """Scan sprint-status.yaml and extract epics and stories.

        Returns:
            Tuple of (epics, stories) lists.

        Raises:
            SprintStatusNotFoundError: If sprint-status.yaml doesn't exist.
        """
        status_path = self.config.paths.sprint_status

        if not status_path.exists():
            raise SprintStatusNotFoundError(
                f"Sprint status file not found: {status_path}\n"
                "Run BMAD sprint-planning workflow to create it."
            )

        with open(status_path) as f:
            status_data = yaml.safe_load(f) or {}

        development_status = status_data.get("development_status", {})

        epics: list[Epic] = []
        stories: list[Story] = []

        current_epic_key: str | None = None

        for key, status in development_status.items():
            # Skip retrospective entries
            if key.endswith("-retrospective"):
                continue

            if key.startswith("epic-"):
                # This is an epic
                epic = self._parse_epic(key, status)
                epics.append(epic)
                current_epic_key = key
            else:
                # This is a story
                epic_key = current_epic_key or self._infer_epic_key(key)
                story = self._parse_story(key, status, epic_key)
                stories.append(story)

        return epics, stories

    def _parse_epic(self, key: str, status: str) -> Epic:
        """Parse an epic from sprint-status.

        Args:
            key: Epic key (e.g., 'epic-1').
            status: Status string.

        Returns:
            Epic object.
        """
        # Try to find epic file and extract title
        epic_num = key.replace("epic-", "")
        title = f"Epic {epic_num}"  # Default title
        file_path = None
        mtime = None

        # Look for epic file
        epics_dir = self.config.paths.planning_artifacts / "epics"
        if epics_dir.exists():
            for epic_file in epics_dir.glob(f"epic-{epic_num}-*.md"):
                file_path = epic_file
                mtime = epic_file.stat().st_mtime

                # Extract title from file
                content = epic_file.read_text()
                title = self._extract_title(content, f"Epic {epic_num}")
                break

        return Epic(
            key=key,
            title=title,
            status=status,
            file_path=file_path,
            mtime=mtime,
        )

    def _parse_story(self, key: str, status: str, epic_key: str) -> Story:
        """Parse a story from sprint-status.

        Args:
            key: Story key (e.g., '1-5-create-knowledge-point').
            status: Status string.
            epic_key: Parent epic key.

        Returns:
            Story object.
        """
        # Extract title from key
        parts = key.split("-", 2)
        if len(parts) >= 3:
            title = parts[2].replace("-", " ").title()
        else:
            title = key

        file_path = None
        mtime = None
        content = None

        # Look for story file
        story_file = self.config.paths.implementation_artifacts / f"{key}.md"
        if story_file.exists():
            file_path = story_file
            mtime = story_file.stat().st_mtime
            content = story_file.read_text()

            # Extract title from file content
            title = self._extract_title(content, title)

        return Story(
            key=key,
            epic_key=epic_key,
            title=title,
            status=status,
            file_path=file_path,
            mtime=mtime,
            content=content,
        )

    def _extract_title(self, content: str, default: str) -> str:
        """Extract title from markdown content.

        Args:
            content: Markdown content.
            default: Default title if not found.

        Returns:
            Extracted or default title.
        """
        # Look for H1 heading
        match = re.search(r"^#\s+(.+?)(?:\n|$)", content, re.MULTILINE)
        if match:
            title = match.group(1).strip()
            # Remove "Epic N:" or "Story N.M:" prefix if present
            title = re.sub(r"^(Epic|Story)\s+[\d.]+:\s*", "", title)
            return title
        return default

    def _infer_epic_key(self, story_key: str) -> str:
        """Infer epic key from story key.

        Args:
            story_key: Story key (e.g., '1-5-create-kp').

        Returns:
            Epic key (e.g., 'epic-1').
        """
        # Extract epic number from story key
        match = re.match(r"^(\d+)-", story_key)
        if match:
            return f"epic-{match.group(1)}"
        return "epic-unknown"
