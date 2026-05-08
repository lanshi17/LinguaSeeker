"""Document acquisition service — unified facade for local upload and online acquisition."""

from __future__ import annotations

import hashlib
import time
from typing import Optional

from loguru import logger

from .contracts import (
    AcquisitionSource,
    DocumentAcquisitionRequest,
    DocumentAcquisitionResult,
)

try:
    import files_io
except ImportError:
    files_io = None  # type: ignore[assignment]
    logger.warning("files_io not available, file deduplication disabled")


class DocumentAcquisitionService:
    """Unified facade for document acquisition.

    Provides a single entry point for acquiring documents from different sources:
    - LOCAL: Upload files from local filesystem
    - ONLINE: Search/download literature from online providers
    """

    def __init__(self) -> None:
        self.logger = logger.bind(component="DocumentAcquisitionService")

    def acquire(self, request: DocumentAcquisitionRequest) -> DocumentAcquisitionResult:
        """Acquire a document from the specified source.

        Args:
            request: The acquisition request.

        Returns:
            DocumentAcquisitionResult with acquisition result.
        """
        start_time = time.time()
        self.logger.debug(
            f"Acquisition started: source={request.source.value}"
        )

        try:
            if request.source == AcquisitionSource.LOCAL:
                result = self._handle_upload(request)
            elif request.source == AcquisitionSource.ONLINE:
                result = self._handle_literature(request)
            else:
                raise ValueError(f"Invalid source: {request.source}")

            result.elapsed_time = time.time() - start_time
            self.logger.debug(
                f"Acquisition completed: source={request.source.value}, "
                f"success={result.success}, elapsed_time={result.elapsed_time:.2f}s"
            )
            return result
        except ValueError as e:
            self.logger.warning(
                f"Acquisition failed: source={request.source.value}, error={e}"
            )
            return DocumentAcquisitionResult(
                success=False,
                source=request.source,
                error=str(e),
                elapsed_time=time.time() - start_time,
            )
        except Exception as e:
            self.logger.error(
                f"Unexpected error: source={request.source.value}, error={e}"
            )
            raise

    def _handle_upload(self, request: DocumentAcquisitionRequest) -> DocumentAcquisitionResult:
        """Handle local file upload."""
        if not request.filename:
            raise ValueError("filename is required for local upload")
        if not request.content:
            raise ValueError("content is required for local upload")

        self.logger.debug(f"Uploading file: {request.filename}")

        # File deduplication logic
        if request.deduplicate and files_io is not None:
            content_hash = hashlib.sha256(request.content).hexdigest()
            existing = self._find_by_hash(content_hash)
            if existing:
                self.logger.debug(f"File already exists: {existing.file_path}")
                return DocumentAcquisitionResult(
                    success=True,
                    source=AcquisitionSource.LOCAL,
                    stored_file=existing,
                    deduplicated=True,
                    warnings=["File already exists"],
                )

        # Call local_upload module
        from .local_upload import upload_document

        result = upload_document(
            filename=request.filename,
            content=request.content,
            content_type=request.content_type,
            upload_dir=request.upload_dir,
        )

        return DocumentAcquisitionResult(
            success=result.success,
            source=AcquisitionSource.LOCAL,
            warnings=result.warnings,
            error=result.error,
            stored_file=result.stored_file,
        )

    def _handle_literature(self, request: DocumentAcquisitionRequest) -> DocumentAcquisitionResult:
        """Handle online literature acquisition."""
        if not request.action:
            raise ValueError("action is required for online acquisition")
        if request.action == "search" and not request.query:
            raise ValueError("query is required for search action")

        self.logger.debug(f"Searching literature: {request.query}")

        # Call online_acquisition module
        from .online_acquisition import online_acquisition_workflow

        payload = {
            "action": request.action,
            "query": request.query,
            "identifiers": request.identifiers,
            "limit": request.limit,
            "download_path": request.download_path,
            "language": request.language,
            "prefer": request.prefer,
            "web_provider": request.web_provider,
            "api_provider": request.api_provider,
        }

        result = online_acquisition_workflow(payload)

        return DocumentAcquisitionResult(
            success=result.get("success", False),
            source=AcquisitionSource.ONLINE,
            warnings=result.get("warnings", []),
            error=result.get("error"),
            items=result.get("items", []),
            downloads=result.get("downloads", []),
            route=result.get("route"),
        )

    def _find_by_hash(self, content_hash: str) -> Optional[object]:
        """Find file by hash with file lock for thread safety."""
        if files_io is None:
            return None

        import fcntl

        lock_path = f"/tmp/files_io_{content_hash}.lock"
        try:
            with open(lock_path, "w") as lock_file:
                fcntl.flock(lock_file, fcntl.LOCK_EX)
                try:
                    return files_io.find_by_hash(content_hash)
                finally:
                    fcntl.flock(lock_file, fcntl.LOCK_UN)
        except Exception as e:
            self.logger.warning(f"File lock failed: {e}")
            return None
