from __future__ import annotations

from io import BytesIO
from typing import Any

import pytest

from src.infrastructure.enum import MinioBucketNameEnum
from src.infrastructure.minio import MinIOClient
from src.infrastructure.models import MinioObjectRefModel


class FakeMinio:
    def __init__(self) -> None:
        self.existing_buckets: set[str] = set()
        self.put_calls: list[dict[str, Any]] = []

    def bucket_exists(self, bucket_name: str) -> bool:
        return bucket_name in self.existing_buckets

    def make_bucket(self, bucket_name: str) -> None:
        self.existing_buckets.add(bucket_name)

    def put_object(
        self,
        bucket_name: str,
        object_name: str,
        data: BytesIO,
        length: int,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        data.read(length)
        self.put_calls.append(
            {
                "bucket_name": bucket_name,
                "object_name": object_name,
                "content_type": content_type,
                "metadata": metadata,
            }
        )


@pytest.fixture()
def fake_minio(monkeypatch: pytest.MonkeyPatch) -> FakeMinio:
    fake = FakeMinio()
    monkeypatch.setattr("src.infrastructure.minio.Minio", lambda *args, **kwargs: fake)
    return fake


def _build_client() -> MinIOClient:
    return MinIOClient(
        endpoint="localhost:9000",
        access_key="key",
        secret_key="secret",
        secure=False,
        bucket_name="bucket",
    )


def test_build_literature_object_key_uses_hash_and_extension() -> None:
    object_key = MinIOClient.build_literature_object_key("ABC-123", "测试文件.PDF")
    hash_prefix, object_name = object_key.split("/", 1)

    assert hash_prefix == "abc123"
    assert object_name.endswith(".pdf")


@pytest.mark.asyncio
async def test_upload_file_filters_non_ascii_metadata(fake_minio: FakeMinio) -> None:
    client = _build_client()

    await client.upload_file(
        bucket=MinioBucketNameEnum.LITERATURE_UPLOADS.value,
        object_key="abc123/object.pdf",
        file_data=BytesIO(b"payload"),
        content_type="application/pdf",
        metadata={
            "hash": "abc123",
            "filename": "贵州省Waardenburg综合征.pdf",
            "uploaded_at": "2026-03-05T10:00:00+00:00",
            "unsafe-key": "line1\r\nline2",
            "bad key": "valid",
        },
    )

    assert fake_minio.put_calls[0]["metadata"] == {
        "hash": "abc123",
        "uploaded_at": "2026-03-05T10:00:00+00:00",
    }


@pytest.mark.asyncio
async def test_upload_literature_upload_prefers_storage_key(
    fake_minio: FakeMinio, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _build_client()
    captured: dict[str, Any] = {}

    async def fake_upload_bytes(
        bucket: MinioBucketNameEnum,
        object_key: str,
        payload: bytes,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> MinioObjectRefModel:
        captured["bucket"] = bucket
        captured["object_key"] = object_key
        captured["content_type"] = content_type
        captured["metadata"] = metadata
        return MinioObjectRefModel(bucket=bucket, object_key=object_key, content_type=content_type)

    monkeypatch.setattr(client, "upload_bytes", fake_upload_bytes)

    ref = await client.upload_literature_upload(
        storage_key="hash/custom.pdf",
        filename="legacy.pdf",
        object_prefix="legacy",
        payload=b"pdf",
        content_type="application/pdf",
        metadata={"hash": "abc"},
    )

    assert captured["bucket"] == MinioBucketNameEnum.LITERATURE_UPLOADS
    assert captured["object_key"] == "hash/custom.pdf"
    assert ref.object_key == "hash/custom.pdf"
