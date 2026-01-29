"""Data models for bmadnotion."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, computed_field

# Type aliases for status values
EpicStatus = Literal["backlog", "in-progress", "done"]
StoryStatus = Literal["backlog", "ready-for-dev", "in-progress", "review", "done"]
EntityType = Literal["project", "epic", "story"]


class Document(BaseModel):
    """A planning artifact document to sync to Notion Pages.

    Represents documents like PRD, Architecture, UX Design, etc.
    """

    path: Path
    """Relative path to the document file."""

    title: str
    """Title for the Notion page."""

    content: str
    """Markdown content of the document."""

    mtime: float
    """File modification time (Unix timestamp)."""

    @computed_field
    @property
    def content_hash(self) -> str:
        """MD5 hash of the content for change detection."""
        return hashlib.md5(self.content.encode()).hexdigest()


class Epic(BaseModel):
    """An Epic from sprint-status.yaml.

    Epics are synced to the Sprints database in Notion.
    """

    key: str
    """Epic key, e.g., 'epic-1'."""

    title: str
    """Epic title extracted from epic file."""

    status: EpicStatus
    """Current status: backlog, in-progress, or done."""

    file_path: Path | None = None
    """Path to the epic file (if exists)."""

    mtime: float | None = None
    """File modification time (if file exists)."""


class Story(BaseModel):
    """A Story from sprint-status.yaml.

    Stories are synced to the Tasks database in Notion.
    """

    key: str
    """Story key, e.g., '1-5-create-knowledge-point'."""

    epic_key: str
    """Parent epic key, e.g., 'epic-1'."""

    title: str
    """Story title."""

    status: StoryStatus
    """Current status: backlog, ready-for-dev, in-progress, review, or done."""

    file_path: Path | None = None
    """Path to the story file (if exists, for ready-for-dev and above)."""

    mtime: float | None = None
    """File modification time (if file exists)."""

    content: str | None = None
    """Story file content (if file exists)."""

    @computed_field
    @property
    def content_hash(self) -> str | None:
        """MD5 hash of the content for change detection."""
        if self.content is None:
            return None
        return hashlib.md5(self.content.encode()).hexdigest()


class PageSyncState(BaseModel):
    """Tracks the sync state of a page (planning artifact).

    Stored in SQLite to track what has been synced to Notion.
    """

    local_path: str
    """Relative path to the local file."""

    notion_page_id: str
    """Notion page ID."""

    last_synced_mtime: float
    """File mtime at last sync."""

    content_hash: str
    """Content hash at last sync."""


class DbSyncState(BaseModel):
    """Tracks the sync state of a database entry (project, epic, or story).

    Stored in SQLite to track what has been synced to Notion.
    """

    local_key: str
    """Local key (e.g., 'project:myproject', 'epic-1', or '1-5-create-kp')."""

    entity_type: EntityType
    """Type of entity: 'project', 'epic', or 'story'."""

    notion_page_id: str
    """Notion page ID in the database."""

    last_synced_mtime: float | None = None
    """File mtime at last sync (if applicable)."""

    content_hash: str | None = None
    """Content hash at last sync (for stories with content)."""


class SyncResult(BaseModel):
    """Result of a sync operation."""

    created: int = 0
    """Number of new items created."""

    updated: int = 0
    """Number of existing items updated."""

    skipped: int = 0
    """Number of items skipped (no changes)."""

    failed: int = 0
    """Number of items that failed to sync."""

    errors: list[str] = Field(default_factory=list)
    """Error messages for failed items."""

    @computed_field
    @property
    def total(self) -> int:
        """Total number of items processed."""
        return self.created + self.updated + self.skipped + self.failed


class DbSyncResult(BaseModel):
    """Result of a database sync operation (epics and stories)."""

    epics_created: int = 0
    """Number of new epics created."""

    epics_updated: int = 0
    """Number of existing epics updated."""

    epics_skipped: int = 0
    """Number of epics skipped (no changes)."""

    epics_failed: int = 0
    """Number of epics that failed to sync."""

    stories_created: int = 0
    """Number of new stories created."""

    stories_updated: int = 0
    """Number of existing stories updated."""

    stories_skipped: int = 0
    """Number of stories skipped (no changes)."""

    stories_failed: int = 0
    """Number of stories that failed to sync."""

    errors: list[str] = Field(default_factory=list)
    """Error messages for failed items."""

    @computed_field
    @property
    def total(self) -> int:
        """Total number of items processed."""
        return (
            self.epics_created + self.epics_updated + self.epics_skipped + self.epics_failed +
            self.stories_created + self.stories_updated + self.stories_skipped + self.stories_failed
        )
