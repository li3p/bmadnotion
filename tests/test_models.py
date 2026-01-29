"""Tests for bmadnotion data models."""

import pytest
from pathlib import Path
from datetime import datetime


class TestDocumentModel:
    """Tests for Document model (planning artifacts)."""

    def test_document_model_fields(self):
        """AC1: Document model should contain necessary fields."""
        from bmadnotion.models import Document

        doc = Document(
            path=Path("prd.md"),
            title="PRD - bloomy",
            content="# PRD\n\nThis is the PRD content.",
            mtime=1234567890.0,
        )

        assert doc.path == Path("prd.md")
        assert doc.title == "PRD - bloomy"
        assert doc.content == "# PRD\n\nThis is the PRD content."
        assert doc.mtime == 1234567890.0

    def test_document_content_hash(self):
        """Document should compute content hash."""
        from bmadnotion.models import Document

        doc = Document(
            path=Path("prd.md"),
            title="PRD",
            content="# PRD Content",
            mtime=1234567890.0,
        )

        assert doc.content_hash is not None
        assert len(doc.content_hash) == 32  # MD5 hex length

    def test_document_content_hash_changes(self):
        """Content hash should change when content changes."""
        from bmadnotion.models import Document

        doc1 = Document(path=Path("a.md"), title="A", content="content1", mtime=0)
        doc2 = Document(path=Path("a.md"), title="A", content="content2", mtime=0)

        assert doc1.content_hash != doc2.content_hash


class TestEpicModel:
    """Tests for Epic model."""

    def test_epic_model_fields(self):
        """AC2: Epic model should contain necessary fields."""
        from bmadnotion.models import Epic

        epic = Epic(
            key="epic-1",
            title="KP Graph Studio",
            status="in-progress",
            file_path=Path("epic-1-kp-graph.md"),
            mtime=1234567890.0,
        )

        assert epic.key == "epic-1"
        assert epic.title == "KP Graph Studio"
        assert epic.status == "in-progress"
        assert epic.file_path == Path("epic-1-kp-graph.md")
        assert epic.mtime == 1234567890.0

    def test_epic_status_validation(self):
        """Epic status should be validated."""
        from bmadnotion.models import Epic
        from pydantic import ValidationError

        # Valid statuses
        for status in ["backlog", "in-progress", "done"]:
            epic = Epic(key="epic-1", title="Test", status=status)
            assert epic.status == status

        # Invalid status
        with pytest.raises(ValidationError):
            Epic(key="epic-1", title="Test", status="invalid-status")

    def test_epic_optional_fields(self):
        """Epic should work with optional fields."""
        from bmadnotion.models import Epic

        epic = Epic(
            key="epic-1",
            title="Test Epic",
            status="backlog",
        )

        assert epic.file_path is None
        assert epic.mtime is None


class TestStoryModel:
    """Tests for Story model."""

    def test_story_model_fields(self):
        """AC2: Story model should contain necessary fields and epic association."""
        from bmadnotion.models import Story

        story = Story(
            key="1-5-create-knowledge-point",
            epic_key="epic-1",
            title="查看知识点详情",
            status="done",
            file_path=Path("1-5-create-knowledge-point.md"),
            mtime=1234567890.0,
            content="# Story 1.5\n\nStory content here.",
        )

        assert story.key == "1-5-create-knowledge-point"
        assert story.epic_key == "epic-1"
        assert story.title == "查看知识点详情"
        assert story.status == "done"
        assert story.file_path == Path("1-5-create-knowledge-point.md")
        assert story.content is not None

    def test_story_status_validation(self):
        """Story status should be validated."""
        from bmadnotion.models import Story
        from pydantic import ValidationError

        # Valid statuses
        valid_statuses = ["backlog", "ready-for-dev", "in-progress", "review", "done"]
        for status in valid_statuses:
            story = Story(key="1-1-test", epic_key="epic-1", title="Test", status=status)
            assert story.status == status

        # Invalid status
        with pytest.raises(ValidationError):
            Story(key="1-1-test", epic_key="epic-1", title="Test", status="invalid")

    def test_story_optional_fields(self):
        """Story should work with optional fields (backlog story has no file)."""
        from bmadnotion.models import Story

        story = Story(
            key="1-9-future-story",
            epic_key="epic-1",
            title="Future Story",
            status="backlog",
        )

        assert story.file_path is None
        assert story.mtime is None
        assert story.content is None

    def test_story_content_hash(self):
        """Story should compute content hash when content exists."""
        from bmadnotion.models import Story

        story_with_content = Story(
            key="1-1-test",
            epic_key="epic-1",
            title="Test",
            status="done",
            content="# Story content",
        )

        story_without_content = Story(
            key="1-2-test",
            epic_key="epic-1",
            title="Test",
            status="backlog",
        )

        assert story_with_content.content_hash is not None
        assert story_without_content.content_hash is None


class TestPageSyncState:
    """Tests for PageSyncState model."""

    def test_page_sync_state_fields(self):
        """AC3: PageSyncState should track synced pages."""
        from bmadnotion.models import PageSyncState

        state = PageSyncState(
            local_path="prd.md",
            notion_page_id="abc123-def456",
            last_synced_mtime=1234567890.0,
            content_hash="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
        )

        assert state.local_path == "prd.md"
        assert state.notion_page_id == "abc123-def456"
        assert state.last_synced_mtime == 1234567890.0
        assert state.content_hash == "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"

    def test_page_sync_state_serialization(self):
        """AC4: PageSyncState should support serialization."""
        from bmadnotion.models import PageSyncState

        state = PageSyncState(
            local_path="prd.md",
            notion_page_id="abc123",
            last_synced_mtime=1234567890.0,
            content_hash="md5hash123",
        )

        # Serialize to dict
        data = state.model_dump()
        assert isinstance(data, dict)
        assert data["local_path"] == "prd.md"

        # Deserialize back
        restored = PageSyncState.model_validate(data)
        assert restored == state


class TestDbSyncState:
    """Tests for DbSyncState model."""

    def test_db_sync_state_fields(self):
        """AC3: DbSyncState should track synced database entries."""
        from bmadnotion.models import DbSyncState

        state = DbSyncState(
            local_key="epic-1",
            entity_type="epic",
            notion_page_id="xyz789",
            last_synced_mtime=1234567890.0,
            content_hash=None,
        )

        assert state.local_key == "epic-1"
        assert state.entity_type == "epic"
        assert state.notion_page_id == "xyz789"

    def test_db_sync_state_entity_types(self):
        """DbSyncState should validate entity types."""
        from bmadnotion.models import DbSyncState
        from pydantic import ValidationError

        # Valid types
        for entity_type in ["epic", "story"]:
            state = DbSyncState(
                local_key="test",
                entity_type=entity_type,
                notion_page_id="abc",
            )
            assert state.entity_type == entity_type

        # Invalid type
        with pytest.raises(ValidationError):
            DbSyncState(
                local_key="test",
                entity_type="invalid",
                notion_page_id="abc",
            )

    def test_db_sync_state_serialization(self):
        """AC4: DbSyncState should support serialization."""
        from bmadnotion.models import DbSyncState

        state = DbSyncState(
            local_key="1-5-create-kp",
            entity_type="story",
            notion_page_id="page123",
            last_synced_mtime=1234567890.0,
            content_hash="contenthash",
        )

        # Serialize to dict
        data = state.model_dump()
        assert isinstance(data, dict)

        # Deserialize back
        restored = DbSyncState.model_validate(data)
        assert restored == state


class TestSyncResult:
    """Tests for SyncResult model."""

    def test_sync_result_fields(self):
        """SyncResult should track sync operation results."""
        from bmadnotion.models import SyncResult

        result = SyncResult(
            created=3,
            updated=2,
            skipped=5,
            failed=0,
            errors=[],
        )

        assert result.created == 3
        assert result.updated == 2
        assert result.skipped == 5
        assert result.failed == 0
        assert result.total == 10

    def test_sync_result_with_errors(self):
        """SyncResult should track errors."""
        from bmadnotion.models import SyncResult

        result = SyncResult(
            created=1,
            updated=0,
            skipped=0,
            failed=2,
            errors=["Failed to sync prd.md: API error", "Failed to sync arch.md: timeout"],
        )

        assert result.failed == 2
        assert len(result.errors) == 2
        assert "prd.md" in result.errors[0]
