"""Page sync engine for syncing planning artifacts to Notion pages."""

from __future__ import annotations

from typing import TYPE_CHECKING

from marknotion import markdown_to_blocks

if TYPE_CHECKING:
    from collections.abc import Callable

from bmadnotion.config import Config
from bmadnotion.models import Document, PageSyncState, SyncResult
from bmadnotion.scanner import BMADScanner
from bmadnotion.store import Store


class PageSyncEngine:
    """Engine for syncing planning artifacts to Notion pages.

    Syncs documents like PRD, Architecture, UX Design to Notion pages.
    Documents are created as sub-pages under the Project row in the Projects database.
    Uses content hash to detect changes and avoid unnecessary syncs.
    """

    def __init__(self, client, store: Store, config: Config):
        """Initialize the page sync engine.

        Args:
            client: Notion client instance (marknotion.NotionClient).
            store: SQLite store for tracking sync state.
            config: Loaded configuration.
        """
        self.client = client
        self.store = store
        self.config = config
        self.scanner = BMADScanner(config)

    def sync(
        self,
        force: bool = False,
        dry_run: bool = False,
        project_page_id: str | None = None,
        on_progress: "Callable[[str, str, int, int], None] | None" = None,
        filter_path: str | None = None,
    ) -> SyncResult:
        """Sync planning artifacts to Notion pages.

        Args:
            force: If True, sync all documents regardless of changes.
            dry_run: If True, report what would be done without making changes.
            project_page_id: Notion page ID of the Project row (parent for documents).
                           If not provided, uses config.page_sync.parent_page_id.
            on_progress: Callback (doc_name, status, current, total) called after each doc.
            filter_path: If provided, only sync the document with this filename.

        Returns:
            SyncResult with statistics about the sync operation.
        """
        # Check if page sync is enabled
        if not self.config.page_sync.enabled:
            return SyncResult()

        # Determine parent page ID
        parent_page_id = project_page_id or self.config.page_sync.parent_page_id
        if not parent_page_id:
            return SyncResult(
                failed=1,
                errors=["No parent page ID. Set project_page_id or page_sync.parent_page_id."],
            )

        # Scan documents
        documents = self.scanner.scan_documents()

        # Filter to specific document if requested
        if filter_path:
            documents = [d for d in documents if d.path.name == filter_path]
            if not documents:
                return SyncResult(
                    failed=1,
                    errors=[f"Document not found: {filter_path}"],
                )

        total = len(documents)

        created = 0
        updated = 0
        skipped = 0
        failed = 0
        errors: list[str] = []

        for i, doc in enumerate(documents, 1):
            try:
                result = self._sync_document(
                    doc,
                    parent_page_id=parent_page_id,
                    force=force,
                    dry_run=dry_run,
                )
                if result == "created":
                    created += 1
                elif result == "updated":
                    updated += 1
                elif result == "skipped":
                    skipped += 1
                if on_progress:
                    on_progress(doc.path.name, result, i, total)
            except Exception as e:
                failed += 1
                errors.append(f"Failed to sync {doc.path.name}: {e}")
                if on_progress:
                    on_progress(doc.path.name, "failed", i, total)

        return SyncResult(
            created=created,
            updated=updated,
            skipped=skipped,
            failed=failed,
            errors=errors,
        )

    def _sync_document(
        self,
        doc: Document,
        parent_page_id: str,
        force: bool,
        dry_run: bool,
    ) -> str:
        """Sync a single document.

        Args:
            doc: Document to sync.
            parent_page_id: Notion page ID of the parent (Project row).
            force: Force sync regardless of changes.
            dry_run: Don't make actual changes.

        Returns:
            Action taken: "created", "updated", or "skipped".
        """
        # Get local path relative to planning_artifacts
        local_path = doc.path.name

        # Check existing state
        state = self.store.get_page_state(local_path)

        # Determine if sync is needed
        needs_sync = force or state is None or state.content_hash != doc.content_hash

        if not needs_sync:
            return "skipped"

        # Convert markdown to Notion blocks
        blocks = markdown_to_blocks(doc.content)

        if dry_run:
            # Report what would be done
            return "created" if state is None else "updated"

        if state is None:
            # Create new page as child of Project
            page = self.client.create_child_page(
                parent_page_id=parent_page_id,
                title=doc.title,
                children=blocks[:100] if blocks else None,
            )
            page_id = page["id"]

            # Save state immediately so a failure appending remaining blocks
            # won't cause a duplicate page on the next sync attempt.
            self.store.save_page_state(PageSyncState(
                local_path=local_path,
                notion_page_id=page_id,
                last_synced_mtime=doc.mtime,
                content_hash=doc.content_hash,
            ))

            # Add remaining blocks if any
            if len(blocks) > 100:
                self.client.append_blocks_in_batches(page_id, blocks[100:])

            return "created"
        else:
            # Update existing page
            page_id = state.notion_page_id

            # Clear existing content and add new blocks
            self.client.clear_page_content(page_id)
            if blocks:
                self.client.append_blocks_in_batches(page_id, blocks)

            # Update state
            self.store.save_page_state(PageSyncState(
                local_path=local_path,
                notion_page_id=page_id,
                last_synced_mtime=doc.mtime,
                content_hash=doc.content_hash,
            ))

            return "updated"
