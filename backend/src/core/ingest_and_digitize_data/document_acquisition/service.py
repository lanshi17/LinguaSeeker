"""Document acquisition service — unified facade for local upload and online acquisition."""

from __future__ import annotations

import hashlib
import os
import time

from loguru import logger

from .contracts import (
    AcquisitionSource,
    DocumentAcquisitionRequest,
    DocumentAcquisitionResult,
    DocumentDownloadEntry,
)
from .local_upload.contracts import LocalStoredFile


class DocumentAcquisitionService:
    """Unified facade for document acquisition.

    Provides a single entry point for acquiring documents from different sources:
    - LOCAL: Upload files from local filesystem
    - ONLINE: Search/download literature from online providers
    """

    def __init__(self) -> None:
        self.logger = logger.bind(component="DocumentAcquisitionService")

    async def acquire(self, request: DocumentAcquisitionRequest) -> DocumentAcquisitionResult:
        """Acquire a document from the specified source.

        Args:
            request: The acquisition request.

        Returns:
            DocumentAcquisitionResult with acquisition result.
        """
        start_time = time.time()
        self.logger.debug(f"Acquisition started: source={request.source.value}")

        try:
            if request.source == AcquisitionSource.LOCAL:
                result = self._handle_upload(request)
            elif request.source == AcquisitionSource.ONLINE:
                result = await self._handle_literature(request)
            else:
                raise ValueError(f"Invalid source: {request.source}")

            result.elapsed_time = time.time() - start_time
            self.logger.debug(
                f"Acquisition completed: source={request.source.value}, "
                f"success={result.success}, elapsed_time={result.elapsed_time:.2f}s"
            )
            return result
        except ValueError as e:
            self.logger.warning(f"Acquisition failed: source={request.source.value}, error={e}")
            return DocumentAcquisitionResult(
                success=False,
                source=request.source,
                error=str(e),
                elapsed_time=time.time() - start_time,
            )
        except Exception as e:
            self.logger.error(f"Unexpected error: source={request.source.value}, error={e}")
            raise

    def _handle_upload(self, request: DocumentAcquisitionRequest) -> DocumentAcquisitionResult:
        """Handle local file upload."""
        if not request.filename:
            raise ValueError("filename is required for local upload")
        if not request.content:
            raise ValueError("content is required for local upload")

        self.logger.debug(f"Uploading file: {request.filename}")

        # File deduplication: check if a file with the same SHA256 already exists
        # in the target upload_dir (same content → same filename from store_local_file).
        if request.deduplicate and request.upload_dir:
            content_hash = hashlib.sha256(request.content).hexdigest()
            ext = os.path.splitext(request.filename)[1].lower()
            expected_path = os.path.join(request.upload_dir, f"{content_hash}{ext}")
            if os.path.exists(expected_path):
                size = os.path.getsize(expected_path)
                self.logger.debug(f"File already exists: {expected_path}")
                return DocumentAcquisitionResult(
                    success=True,
                    source=AcquisitionSource.LOCAL,
                    stored_file=LocalStoredFile(
                        file_path=expected_path,
                        sha256=content_hash,
                        original_filename=request.filename,
                        size=size,
                        content_type=request.content_type,
                    ),
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

    async def _handle_literature(self, request: DocumentAcquisitionRequest) -> DocumentAcquisitionResult:
        """Handle online literature acquisition.

        Routes to ``multilingual_acquisition_workflow`` when the request
        has a free-text query and no specific language hint (``auto``);
        single-language and identifier-driven requests stay on
        ``online_acquisition_workflow``.
        """
        if not request.action:
            raise ValueError("action is required for online acquisition")
        if request.action == "search" and not request.query:
            raise ValueError("query is required for search action")

        from lit_acquisition import (
            multilingual_acquisition_workflow,
            online_acquisition_workflow,
        )

        payload: dict[str, object] = {
            "action": request.action,
            "query": request.query,
            "identifiers": request.identifiers,
            "limit": request.limit,
            "download_path": request.download_path,
            "language": request.language,
            "prefer": request.prefer,
            "api_provider": request.api_provider,
            "relevance_gate": request.relevance_gate,
        }
        if request.literature_types:
            payload["literature_types"] = list(request.literature_types)

        # Multilingual fanout requires a free-text query and "auto" routing.
        # An explicit language or an identifier-only request stays on the
        # single-language path so we don't translate identifiers like DOIs.
        use_multilingual = bool(
            request.query
            and (request.language in (None, "", "auto"))
            and not (request.identifiers and not request.query)
        )

        if use_multilingual:
            self.logger.debug(f"Searching literature (multilingual): {request.query}")
            result = await multilingual_acquisition_workflow(payload)
        else:
            self.logger.debug(f"Searching literature (single-language): {request.query}")
            result = await online_acquisition_workflow(payload)

        # Convert raw download dicts to typed entries
        downloads = [
            DocumentDownloadEntry(
                file_path=d.get("file_path"),
                pdf_url=d.get("pdf_url"),
                resolved_url=d.get("resolved_url"),
                pre_parsed_markdown=d.get("parsed_markdown") or None,
            )
            for d in result.get("downloads", [])
        ]

        warnings_list = result.get("warnings", [])
        success = result.get("success", False)
        # OnlineAcquisitionResponse carries failure reasons in ``warnings``
        # and has no ``error`` field, so ``result.get("error")`` is always
        # None. Surface the warnings as a concrete error so upstream layers
        # (Phase 1 adapter) don't report "Acquisition failed: None".
        error = result.get("error")
        if not success and not error:
            error = "; ".join(warnings_list) if warnings_list else "No candidates or downloads returned by any provider"

        return DocumentAcquisitionResult(
            success=success,
            source=AcquisitionSource.ONLINE,
            warnings=warnings_list,
            error=error,
            items=result.get("items", []),
            downloads=downloads,
            route=result.get("route"),
        )
