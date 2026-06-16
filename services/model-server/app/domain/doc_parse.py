"""Document parsing via MinerU's internal Python API."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from typing import Any

from app.utils.logger import get_logger

logger = get_logger()


@dataclass
class DocParseResult:
    """Result from MinerU document parsing."""

    md_content: str = ""
    content_list: list[dict[str, Any]] = field(default_factory=list)
    images: dict[str, bytes] = field(default_factory=dict)


class DocParseService:
    """Wraps MinerU's doc_analyze for PDF parsing.

    Uses MinerU's ModelSingleton for model lifecycle management.
    The VLM model is loaded on first request and cached.
    """

    def __init__(
        self,
        backend: str = "vlm",
        gpu_memory_utilization: float = 0.9,
        model_path: str = "",
    ) -> None:
        self._backend = backend
        self._gpu_memory_utilization = gpu_memory_utilization
        self._model_path = model_path or None
        self._available: bool | None = None

    @property
    def ready(self) -> bool:
        """Whether MinerU is importable and ready for parsing."""
        return self.is_available()

    def is_available(self) -> bool:
        """Check if MinerU is importable and ready."""
        if self._available is None:
            try:
                from mineru.backend.vlm.vlm_analyze import doc_analyze  # noqa: F401

                self._available = True
            except ImportError:
                self._available = False
        return self._available

    def parse(self, pdf_bytes: bytes, file_name: str = "document.pdf") -> DocParseResult:
        """Parse a PDF and return structured results.

        Args:
            pdf_bytes: Raw PDF file content.
            file_name: Original filename (for logging).

        Returns:
            DocParseResult with markdown, content_list, and images.

        Raises:
            RuntimeError: If MinerU is not available.
        """
        if not self.is_available():
            raise RuntimeError("MinerU is not installed. Install with: pip install 'mineru[vlm]'")

        from mineru.backend.vlm.vlm_analyze import doc_analyze
        from mineru.data.data_reader_writer import FileBasedDataWriter

        with tempfile.TemporaryDirectory() as tmp_dir:
            images_dir = os.path.join(tmp_dir, "images")
            os.makedirs(images_dir, exist_ok=True)
            image_writer = FileBasedDataWriter(images_dir)

            logger.info(
                "Running MinerU doc_analyze for {name} (backend={backend})",
                name=file_name,
                backend=self._backend,
            )

            middle_json, results = doc_analyze(
                pdf_bytes=pdf_bytes,
                image_writer=image_writer,
                backend=self._backend,
                model_path=self._model_path,
                gpu_memory_utilization=self._gpu_memory_utilization,
                image_analysis=True,
            )

            # Extract markdown from middle_json
            pdf_info = middle_json.get("pdf_info", [])
            md_parts: list[str] = []
            content_list: list[dict[str, Any]] = []

            for page_info in pdf_info:
                page_content = page_info.get("preproc_blocks", [])
                for block in page_content:
                    block_type = block.get("type", "")
                    if block_type == "discarded":
                        continue

                    text_lines = []
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text = span.get("content", "")
                            if text:
                                text_lines.append(text)

                    if text_lines:
                        md_parts.append(" ".join(text_lines))

                    # Build content_list entry
                    content_list.append({
                        "type": block_type,
                        "text": " ".join(text_lines),
                        "page_idx": page_info.get("page_no", 0),
                        "bbox": block.get("bbox", [0, 0, 0, 0]),
                    })

            # Collect images
            images: dict[str, bytes] = {}
            if os.path.isdir(images_dir):
                for img_file in os.listdir(images_dir):
                    img_path = os.path.join(images_dir, img_file)
                    if os.path.isfile(img_path):
                        with open(img_path, "rb") as f:
                            images[img_file] = f.read()

            full_markdown = "\n\n".join(md_parts)

            logger.info(
                "MinerU parsed {name}: {pages} pages, {blocks} blocks, {images} images",
                name=file_name,
                pages=len(pdf_info),
                blocks=len(content_list),
                images=len(images),
            )

            return DocParseResult(
                md_content=full_markdown,
                content_list=content_list,
                images=images,
            )
