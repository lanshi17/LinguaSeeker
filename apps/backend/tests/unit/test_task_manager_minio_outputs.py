from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.domain.models import EvidenceOutput, PipelineFiles
from src.services import task_manager as tasks_module


class FakeMinIOClient:
    def __init__(self) -> None:
        self.ensure_buckets_called = 0
        self.byte_uploads: List[Dict[str, Any]] = []
        self.json_uploads: List[Dict[str, Any]] = []
        self.image_uploads: List[Dict[str, Any]] = []

    async def ensure_buckets(self) -> None:
        self.ensure_buckets_called += 1

    def build_processed_object_key(self, document_id: str, object_name: str) -> str:
        return f"{document_id}/{object_name}"

    async def upload_processed_result_bytes(
        self,
        document_id: str,
        object_name: str,
        payload: bytes,
        content_type: str,
    ) -> None:
        self.byte_uploads.append(
            {
                "document_id": document_id,
                "object_name": object_name,
                "payload": payload,
                "content_type": content_type,
            }
        )

    async def upload_processed_result_json(
        self,
        document_id: str,
        payload: Dict[str, object],
    ) -> None:
        self.json_uploads.append(
            {
                "document_id": document_id,
                "payload": payload,
            }
        )

    async def upload_processed_image(
        self,
        document_id: str,
        filename: str,
        payload: bytes,
        content_type: str,
    ) -> None:
        self.image_uploads.append(
            {
                "document_id": document_id,
                "filename": filename,
                "payload": payload,
                "content_type": content_type,
            }
        )


@pytest.mark.asyncio
async def test_store_outputs_in_minio_persists_expected_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image_path = tmp_path / "figure1.jpg"
    image_path.write_bytes(b"image-bytes")

    fake_minio = FakeMinIOClient()
    monkeypatch.setattr(tasks_module, "MinIOClient", lambda: fake_minio)

    response = EvidenceOutput(
        ps3_evidence={"score": 0.95, "classification": "PS3"},
        arbitration_confidence=0.0,
        image_descriptions=["Figure 1: LDLR assay result"],
        final_evidence_strength="",
        status="success",
        origin_format_md="# 原始内容\n\n- point 1",
        en_format_md="# English content\n\n- point 1",
        extracted_fields={},
        field_confidence_scores={},
        overall_confidence=0.0,
        evidence_classification="",
        acmg_evidence_levels=[],
    )

    result = await tasks_module._store_outputs_in_minio(
        response,
        [str(image_path)],
        document_id="doc-123",
    )

    assert fake_minio.ensure_buckets_called == 1

    assert fake_minio.byte_uploads == [
        {
            "document_id": "doc-123",
            "object_name": "original_format.md",
            "payload": b"# \xe5\x8e\x9f\xe5\xa7\x8b\xe5\x86\x85\xe5\xae\xb9\n\n- point 1",
            "content_type": "text/markdown; charset=utf-8",
        },
        {
            "document_id": "doc-123",
            "object_name": "en_format.md",
            "payload": b"# English content\n\n- point 1",
            "content_type": "text/markdown; charset=utf-8",
        },
        {
            "document_id": "doc-123",
            "object_name": "image_descriptions.txt",
            "payload": b"Figure 1: LDLR assay result\n",
            "content_type": "text/plain; charset=utf-8",
        },
    ]

    assert fake_minio.json_uploads == [
        {
            "document_id": "doc-123",
            "payload": {"score": 0.95, "classification": "PS3"},
        }
    ]

    assert fake_minio.image_uploads == [
        {
            "document_id": "doc-123",
            "filename": "figure1.jpg",
            "payload": b"image-bytes",
            "content_type": "image/jpeg",
        }
    ]

    assert result == PipelineFiles(
        origin_md_path="doc-123/original_format.md",
        en_md_path="doc-123/en_format.md",
        image_desc_path="doc-123/image_descriptions.txt",
        ps3_evidence_path="doc-123/ps3_evidence.json",
        image_dir="doc-123/images",
        origin_md_url=f"{tasks_module.cfg.api_prefix}/results/doc-123/original_format.md",
        en_md_url=f"{tasks_module.cfg.api_prefix}/results/doc-123/en_format.md",
        image_desc_url=f"{tasks_module.cfg.api_prefix}/results/doc-123/image_descriptions.txt",
        ps3_evidence_url=f"{tasks_module.cfg.api_prefix}/results/doc-123/ps3_evidence.json",
        image_urls=[
            f"{tasks_module.cfg.api_prefix}/results/doc-123/images/figure1.jpg"
        ],
    )
