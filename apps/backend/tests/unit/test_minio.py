from __future__ import annotations

from io import BytesIO
import json

import pytest

from datetime import datetime, timezone

from minio.error import S3Error

from src.infrastructure.minio import MinIOClient
from src.infrastructure.enum import MinioBucketNameEnum
from src.infrastructure.models import MinioObjectRefModel
from src.utils.exceptions import StoreException


class DummyResponse:
	def __init__(self, payload: bytes) -> None:
		self._payload = payload
		self.closed = False
		self.released = False

	def read(self) -> bytes:
		return self._payload

	def close(self) -> None:
		self.closed = True

	def release_conn(self) -> None:
		self.released = True


class DummyErrorResponse:
	def __init__(self, code: str) -> None:
		self.status = 404
		self.reason = code
		self.headers = {"x-minio-error": code}
		self.data = b""


class DummyStat:
	def __init__(self, size: int, etag: str, content_type: str | None, metadata: dict | None) -> None:
		self.size = size
		self.etag = etag
		self.content_type = content_type
		self.last_modified = datetime(2026, 2, 9, 12, 0, 0, tzinfo=timezone.utc)
		self.metadata = metadata


class DummyObject:
	def __init__(self, object_name: str) -> None:
		self.object_name = object_name


def make_s3_error(code: str) -> S3Error:
	return S3Error(
		code=code,
		message="error",
		resource="/",
		request_id="req",
		host_id="host",
		response=DummyErrorResponse(code),
	)


@pytest.fixture()
def fake_minio_client(monkeypatch):
	class FakeMinio:
		def __init__(self) -> None:
			self.put_calls = []
			self.removed_objects = []
			self.created_buckets = []
			self.removed_buckets = []
			self.copy_calls = []
			self.existing_buckets = set()
			self.object_store = {}
			self.object_meta = {}

		def put_object(self, bucket_name, object_name, data, length, content_type=None, metadata=None):
			payload = data.read(length)
			self.object_store[(bucket_name, object_name)] = payload
			self.object_meta[(bucket_name, object_name)] = {
				"content_type": content_type,
				"metadata": metadata or {},
			}
			self.put_calls.append((bucket_name, object_name, length, content_type, metadata))

		def get_object(self, bucket_name, object_name):
			key = (bucket_name, object_name)
			if key not in self.object_store:
				raise make_s3_error("NoSuchKey")
			return DummyResponse(self.object_store[key])

		def remove_object(self, bucket_name, object_name):
			key = (bucket_name, object_name)
			if key not in self.object_store:
				raise make_s3_error("NoSuchKey")
			self.removed_objects.append(key)
			del self.object_store[key]

		def stat_object(self, bucket_name, object_name):
			key = (bucket_name, object_name)
			if key not in self.object_store:
				raise make_s3_error("NoSuchKey")
			meta = self.object_meta.get(key, {})
			return DummyStat(
				size=len(self.object_store[key]),
				etag="etag",
				content_type=meta.get("content_type"),
				metadata=meta.get("metadata", {}),
			)

		def list_objects(self, bucket_name, prefix=None, recursive=True):
			names = [name for (bkt, name) in self.object_store if bkt == bucket_name]
			for name in names:
				if prefix is None or name.startswith(prefix):
					yield DummyObject(name)

		def make_bucket(self, bucket_name):
			self.created_buckets.append(bucket_name)
			self.existing_buckets.add(bucket_name)

		def bucket_exists(self, bucket_name):
			return bucket_name in self.existing_buckets

		def remove_bucket(self, bucket_name):
			if bucket_name not in self.existing_buckets:
				raise make_s3_error("NoSuchBucket")
			if any(bkt == bucket_name for (bkt, _) in self.object_store):
				raise make_s3_error("BucketNotEmpty")
			self.existing_buckets.remove(bucket_name)
			self.removed_buckets.append(bucket_name)

		def presigned_get_object(self, bucket_name, object_name, expires):
			return f"https://example.com/{bucket_name}/{object_name}?exp={expires}"

		def presigned_put_object(self, bucket_name, object_name, expires):
			return f"https://example.com/{bucket_name}/{object_name}?put={expires}"

		def copy_object(self, bucket_name, object_name, source):
			self.copy_calls.append((bucket_name, object_name, source))

	fake = FakeMinio()

	def fake_minio_factory(*args, **kwargs):
		return fake

	monkeypatch.setattr("src.infrastructure.minio.Minio", fake_minio_factory)
	return fake


def build_client(fake_minio_client) -> MinIOClient:
	return MinIOClient(
		endpoint="localhost:9000",
		access_key="key",
		secret_key="secret",
		secure=False,
		bucket_name="bucket",
	)


@pytest.mark.asyncio
async def test_ensure_bucket_creates_when_missing(fake_minio_client):
	client = build_client(fake_minio_client)

	await client.ensure_bucket("bucket")

	assert fake_minio_client.created_buckets == ["bucket"]


@pytest.mark.asyncio
async def test_ensure_bucket_no_create_when_exists(fake_minio_client):
	client = build_client(fake_minio_client)
	fake_minio_client.existing_buckets.add("bucket")

	await client.ensure_bucket("bucket")

	assert fake_minio_client.created_buckets == []


@pytest.mark.asyncio
async def test_ensure_bucket_wraps_errors(fake_minio_client, monkeypatch):
	class ErrorClient:
		async def bucket_exists(self, bucket_name: str) -> bool:
			raise RuntimeError("boom")

		async def create_bucket(self, bucket_name: str) -> None:
			raise AssertionError("not reached")

	client = build_client(fake_minio_client)
	monkeypatch.setattr(client, "bucket_exists", ErrorClient().bucket_exists)
	monkeypatch.setattr(client, "create_bucket", ErrorClient().create_bucket)

	with pytest.raises(StoreException):
		await client.ensure_bucket("bucket")


@pytest.mark.asyncio
async def test_ensure_buckets_calls_both(fake_minio_client, monkeypatch):
	client = build_client(fake_minio_client)
	calls: list[str] = []

	async def fake_ensure_bucket(bucket_name: str) -> None:
		calls.append(bucket_name)

	monkeypatch.setattr(client, "ensure_bucket", fake_ensure_bucket)

	await client.ensure_buckets()

	assert calls == [
		MinioBucketNameEnum.LITERATURE_UPLOADS.value,
		MinioBucketNameEnum.PROCESSED_RESULTS.value,
	]


def test_build_processed_object_key():
	assert MinIOClient.build_processed_object_key("doc", "a.txt") == "doc/a.txt"


def test_build_processed_image_key():
	assert MinIOClient.build_processed_image_key("doc", "image.png") == "doc/images/image.png"


@pytest.mark.asyncio
async def test_upload_bytes_uploads_and_returns_ref(fake_minio_client, monkeypatch):
	client = build_client(fake_minio_client)
	ensure_calls: list[str] = []

	async def fake_ensure_bucket(bucket_name: str) -> None:
		ensure_calls.append(bucket_name)

	monkeypatch.setattr(client, "ensure_bucket", fake_ensure_bucket)

	ref = await client.upload_bytes(
		bucket=MinioBucketNameEnum.PROCESSED_RESULTS,
		object_key="doc/a.txt",
		payload=b"data",
		content_type="text/plain",
		metadata={"x-meta": "1"},
	)

	assert ensure_calls == [MinioBucketNameEnum.PROCESSED_RESULTS.value]
	assert fake_minio_client.put_calls == [
		(
			MinioBucketNameEnum.PROCESSED_RESULTS.value,
			"doc/a.txt",
			4,
			"text/plain",
			{"x-meta": "1"},
		)
	]
	assert ref == MinioObjectRefModel(
		bucket=MinioBucketNameEnum.PROCESSED_RESULTS,
		object_key="doc/a.txt",
		content_type="text/plain",
	)


@pytest.mark.asyncio
async def test_download_bytes_returns_payload(fake_minio_client):
	client = build_client(fake_minio_client)
	fake_minio_client.object_store[(MinioBucketNameEnum.PROCESSED_RESULTS.value, "doc/a.txt")] = b"content"

	payload = await client.download_bytes(MinioBucketNameEnum.PROCESSED_RESULTS, "doc/a.txt")

	assert payload == b"content"


@pytest.mark.asyncio
async def test_upload_literature_upload_builds_key(fake_minio_client, monkeypatch):
	client = build_client(fake_minio_client)
	called = {}

	async def fake_upload_bytes(
		bucket: MinioBucketNameEnum,
		object_key: str,
		payload: bytes,
		content_type: str,
		metadata: dict | None = None,
	) -> MinioObjectRefModel:
		called.update(
			{
				"bucket": bucket,
				"object_key": object_key,
				"payload": payload,
				"content_type": content_type,
				"metadata": metadata,
			}
		)
		return MinioObjectRefModel(bucket=bucket, object_key=object_key, content_type=content_type)

	monkeypatch.setattr(client, "upload_bytes", fake_upload_bytes)

	ref = await client.upload_literature_upload(
		filename="file.pdf",
		payload=b"pdf",
		content_type="application/pdf",
		object_prefix="prefix",
		metadata={"x-meta": "1"},
	)

	assert called["bucket"] == MinioBucketNameEnum.LITERATURE_UPLOADS
	assert called["object_key"] == "prefix/file.pdf"
	assert ref.object_key == "prefix/file.pdf"


@pytest.mark.asyncio
async def test_download_literature_upload_calls_download_bytes(fake_minio_client, monkeypatch):
	client = build_client(fake_minio_client)

	async def fake_download_bytes(bucket: MinioBucketNameEnum, object_key: str) -> bytes:
		assert bucket == MinioBucketNameEnum.LITERATURE_UPLOADS
		assert object_key == "file.pdf"
		return b"payload"

	monkeypatch.setattr(client, "download_bytes", fake_download_bytes)

	payload = await client.download_literature_upload("file.pdf")

	assert payload == b"payload"


@pytest.mark.asyncio
async def test_upload_processed_result_json_uses_expected_object_key(fake_minio_client, monkeypatch):
	client = build_client(fake_minio_client)
	captured = {}

	async def fake_upload_bytes(
		bucket: MinioBucketNameEnum,
		object_key: str,
		payload: bytes,
		content_type: str,
		metadata: dict | None = None,
	) -> MinioObjectRefModel:
		captured.update(
			{
				"bucket": bucket,
				"object_key": object_key,
				"payload": payload,
				"content_type": content_type,
			}
		)
		return MinioObjectRefModel(bucket=bucket, object_key=object_key, content_type=content_type)

	monkeypatch.setattr(client, "upload_bytes", fake_upload_bytes)

	ref = await client.upload_processed_result_json("doc", {"a": 1})

	assert captured["bucket"] == MinioBucketNameEnum.PROCESSED_RESULTS
	assert captured["object_key"] == "doc/ps3_evidence.json"
	assert captured["content_type"] == "application/json"
	assert json.loads(captured["payload"].decode("utf-8")) == {"a": 1}
	assert ref.object_key == "doc/ps3_evidence.json"


@pytest.mark.asyncio
async def test_download_processed_result_json(fake_minio_client, monkeypatch):
	client = build_client(fake_minio_client)

	async def fake_download_bytes(bucket: MinioBucketNameEnum, object_key: str) -> bytes:
		assert bucket == MinioBucketNameEnum.PROCESSED_RESULTS
		assert object_key == "doc/ps3_evidence.json"
		return b"payload"

	monkeypatch.setattr(client, "download_bytes", fake_download_bytes)

	payload = await client.download_processed_result_json("doc")

	assert payload == b"payload"


@pytest.mark.asyncio
async def test_download_processed_result(fake_minio_client, monkeypatch):
	client = build_client(fake_minio_client)

	async def fake_download_bytes(bucket: MinioBucketNameEnum, object_key: str) -> bytes:
		assert bucket == MinioBucketNameEnum.PROCESSED_RESULTS
		assert object_key == "doc/a.txt"
		return b"payload"

	monkeypatch.setattr(client, "download_bytes", fake_download_bytes)

	payload = await client.download_processed_result("doc/a.txt")

	assert payload == b"payload"


@pytest.mark.asyncio
async def test_upload_processed_result_bytes(fake_minio_client, monkeypatch):
	client = build_client(fake_minio_client)
	captured = {}

	async def fake_upload_bytes(
		bucket: MinioBucketNameEnum,
		object_key: str,
		payload: bytes,
		content_type: str,
		metadata: dict | None = None,
	) -> MinioObjectRefModel:
		captured.update(
			{
				"bucket": bucket,
				"object_key": object_key,
				"payload": payload,
				"content_type": content_type,
			}
		)
		return MinioObjectRefModel(bucket=bucket, object_key=object_key, content_type=content_type)

	monkeypatch.setattr(client, "upload_bytes", fake_upload_bytes)

	ref = await client.upload_processed_result_bytes(
		document_id="doc",
		object_name="report.md",
		payload=b"content",
		content_type="text/markdown",
	)

	assert captured["bucket"] == MinioBucketNameEnum.PROCESSED_RESULTS
	assert captured["object_key"] == "doc/report.md"
	assert ref.object_key == "doc/report.md"


@pytest.mark.asyncio
async def test_upload_processed_image(fake_minio_client, monkeypatch):
	client = build_client(fake_minio_client)
	captured = {}

	async def fake_upload_bytes(
		bucket: MinioBucketNameEnum,
		object_key: str,
		payload: bytes,
		content_type: str,
		metadata: dict | None = None,
	) -> MinioObjectRefModel:
		captured.update(
			{
				"bucket": bucket,
				"object_key": object_key,
				"payload": payload,
				"content_type": content_type,
			}
		)
		return MinioObjectRefModel(bucket=bucket, object_key=object_key, content_type=content_type)

	monkeypatch.setattr(client, "upload_bytes", fake_upload_bytes)

	ref = await client.upload_processed_image(
		document_id="doc",
		filename="image.png",
		payload=b"data",
		content_type="image/png",
	)

	assert captured["bucket"] == MinioBucketNameEnum.PROCESSED_RESULTS
	assert captured["object_key"] == "doc/images/image.png"
	assert ref.object_key == "doc/images/image.png"
