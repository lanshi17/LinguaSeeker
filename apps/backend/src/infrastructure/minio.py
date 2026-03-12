from __future__ import annotations

from datetime import timedelta
from io import BytesIO
import json
import os
from typing import Dict, List, Optional
from urllib.parse import urlparse

from loguru import logger
from minio import Minio
from minio.error import S3Error

from src.config import settings as cfg
from src.infrastructure.enum import MinioBucketNameEnum
from src.infrastructure.models import MinioObjectRefModel
from src.utils.sanitizers import build_storage_key, filter_ascii_metadata
from src.utils.exceptions import StoreException


class MinIOClient:
    """MinIO storage wrapper with higher-level helpers."""

    @staticmethod
    def _normalize_endpoint(endpoint: str) -> str:
        if not endpoint:
            return endpoint

        endpoint = endpoint.strip()
        if "://" not in endpoint:
            if "/" in endpoint:
                logger.warning("MinIO endpoint contains a path, ignoring it: {}", endpoint)
                return endpoint.split("/", 1)[0]
            return endpoint

        parsed = urlparse(endpoint)
        if parsed.scheme:
            if parsed.path and parsed.path != "/":
                logger.warning("MinIO endpoint contains a path, ignoring it: {}", parsed.path)
            return parsed.netloc or parsed.path

        return parsed.netloc or parsed.path

    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        secure: Optional[bool] = None,
        bucket_name: Optional[str] = None,
    ) -> None:
        raw_endpoint = endpoint or cfg.minio_endpoint
        self.endpoint = self._normalize_endpoint(raw_endpoint)
        self.access_key = access_key or cfg.minio_access_key
        self.secret_key = secret_key or cfg.minio_secret_key
        self.secure = cfg.minio_secure if secure is None else secure
        self.bucket_name = bucket_name or cfg.minio_results_bucket
        self.logger = logger

        try:
            self.client = Minio(
                endpoint=self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
            )
        except Exception as exc:
            raise ConnectionError(f"Failed to connect to MinIO: {exc}")

    @staticmethod
    def build_processed_object_key(document_id: str, name: str) -> str:
        return f"{document_id}/{name}"

    @staticmethod
    def build_processed_image_key(document_id: str, filename: str) -> str:
        return f"{document_id}/images/{filename}"

    @staticmethod
    def build_literature_object_key(file_hash: str, original_filename: Optional[str]) -> str:
        return build_storage_key(file_hash=file_hash, filename=original_filename)

    async def upload_file(
        self,
        bucket: str,
        object_key: str,
        file_data: BytesIO,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        try:
            if not await self.bucket_exists(bucket):
                await self.create_bucket(bucket)

            file_data.seek(0, os.SEEK_END)
            file_size = file_data.tell()
            file_data.seek(0)
            safe_metadata = filter_ascii_metadata(metadata)

            self.client.put_object(
                bucket_name=bucket,
                object_name=object_key,
                data=file_data,
                length=file_size,
                content_type=content_type or "application/octet-stream",
                metadata=safe_metadata or None,
            )

            protocol = "https" if self.secure else "http"
            return f"{protocol}://{self.endpoint}/{bucket}/{object_key}"
        except S3Error as exc:
            raise IOError(f"Failed to upload file: {exc}")

    async def download_file(self, bucket: str, object_key: str) -> BytesIO:
        try:
            response = self.client.get_object(bucket_name=bucket, object_name=object_key)
            data = BytesIO(response.read())
            response.close()
            response.release_conn()
            return data
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                raise FileNotFoundError(f"Object not found: {bucket}/{object_key}")
            raise IOError(f"Failed to download file: {exc}")

    async def delete_file(self, bucket: str, object_key: str) -> bool:
        try:
            self.client.remove_object(bucket_name=bucket, object_name=object_key)
            return True
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return False
            raise IOError(f"Failed to delete file: {exc}")

    async def file_exists(self, bucket: str, object_key: str) -> bool:
        try:
            self.client.stat_object(bucket_name=bucket, object_name=object_key)
            return True
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return False
            raise IOError(f"Failed to check file existence: {exc}")

    async def get_file_metadata(self, bucket: str, object_key: str) -> Dict[str, str]:
        try:
            stat = self.client.stat_object(bucket_name=bucket, object_name=object_key)
            last_modified = stat.last_modified.isoformat() if stat.last_modified else ""
            metadata = {
                "size": str(stat.size),
                "etag": stat.etag or "",
                "content_type": stat.content_type or "application/octet-stream",
                "last_modified": last_modified,
            }
            if stat.metadata:
                metadata.update(stat.metadata)
            return metadata
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                raise FileNotFoundError(f"Object not found: {bucket}/{object_key}")
            raise IOError(f"Failed to get metadata: {exc}")

    async def list_objects(
        self, bucket: str, prefix: Optional[str] = None, limit: int = 1000
    ) -> List[str]:
        try:
            objects = self.client.list_objects(bucket_name=bucket, prefix=prefix, recursive=True)
            names = []
            for obj in objects:
                names.append(obj.object_name)
                if len(names) >= limit:
                    break
            return names
        except S3Error as exc:
            raise IOError(f"Failed to list objects: {exc}")

    async def create_bucket(self, bucket: str) -> bool:
        try:
            if await self.bucket_exists(bucket):
                return False
            self.client.make_bucket(bucket)
            return True
        except S3Error as exc:
            raise IOError(f"Failed to create bucket: {exc}")

    async def bucket_exists(self, bucket: str) -> bool:
        try:
            return self.client.bucket_exists(bucket)
        except S3Error as exc:
            raise IOError(f"Failed to check bucket existence: {exc}")

    async def delete_bucket(self, bucket: str, force: bool = False) -> bool:
        try:
            if force:
                objects = self.client.list_objects(bucket, recursive=True)
                for obj in objects:
                    if obj.object_name:
                        self.client.remove_object(bucket, obj.object_name)
            self.client.remove_bucket(bucket)
            return True
        except S3Error as exc:
            if exc.code == "NoSuchBucket":
                return False
            if exc.code == "BucketNotEmpty" and not force:
                raise ValueError(f"Bucket {bucket} is not empty. Use force=True to delete.")
            raise IOError(f"Failed to delete bucket: {exc}")

    async def get_presigned_url(
        self,
        bucket: str,
        object_key: str,
        expires_in: int = 3600,
        method: str = "GET",
    ) -> str:
        try:
            expires = timedelta(seconds=expires_in)
            if method == "GET":
                url = self.client.presigned_get_object(
                    bucket_name=bucket, object_name=object_key, expires=expires
                )
            elif method == "PUT":
                url = self.client.presigned_put_object(
                    bucket_name=bucket, object_name=object_key, expires=expires
                )
            else:
                raise ValueError(f"Unsupported method: {method}")
            return url
        except S3Error as exc:
            raise IOError(f"Failed to generate presigned URL: {exc}")

    async def copy_object(
        self,
        source_bucket: str,
        source_key: str,
        dest_bucket: str,
        dest_key: str,
    ) -> bool:
        try:
            from minio.commonconfig import CopySource

            copy_source = CopySource(source_bucket, source_key)
            self.client.copy_object(
                bucket_name=dest_bucket, object_name=dest_key, source=copy_source
            )
            return True
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                raise FileNotFoundError(f"Source object not found: {source_bucket}/{source_key}")
            raise IOError(f"Failed to copy object: {exc}")

    async def get_object_size(self, bucket: str, object_key: str) -> int:
        try:
            stat = self.client.stat_object(bucket_name=bucket, object_name=object_key)
            if stat.size is None:
                raise IOError(f"Failed to get object size: {bucket}/{object_key} has unknown size")
            return stat.size
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                raise FileNotFoundError(f"Object not found: {bucket}/{object_key}")
            raise IOError(f"Failed to get object size: {exc}")

    async def store_file(
        self, key: str, content: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        self.logger.info("Storing file with key: {}", key)
        if not await self.bucket_exists(self.bucket_name):
            await self.create_bucket(self.bucket_name)

        file_data = BytesIO(content)
        file_size = len(content)
        try:
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=key,
                data=file_data,
                length=file_size,
                content_type=content_type,
            )
            protocol = "https" if self.secure else "http"
            url = f"{protocol}://{self.endpoint}/{self.bucket_name}/{key}"
            self.logger.info("File stored successfully: {}", url)
            return url
        except S3Error as exc:
            self.logger.error("Failed to store file {}: {}", key, exc)
            raise IOError(f"Failed to store file: {exc}")

    async def get_file(self, key: str) -> bytes:
        self.logger.info("Retrieving file with key: {}", key)
        try:
            response = self.client.get_object(bucket_name=self.bucket_name, object_name=key)
            content = response.read()
            response.close()
            response.release_conn()
            self.logger.info("File retrieved successfully: {} ({} bytes)", key, len(content))
            return content
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                self.logger.error("File not found: {}", key)
                raise FileNotFoundError(f"Object not found: {self.bucket_name}/{key}")
            self.logger.error("Failed to retrieve file {}: {}", key, exc)
            raise IOError(f"Failed to retrieve file: {exc}")

    async def ensure_bucket(self, bucket_name: str) -> None:
        try:
            exists = await self.bucket_exists(bucket_name)
            if not exists:
                await self.create_bucket(bucket_name)
                logger.info("Created MinIO bucket: {}", bucket_name)
        except Exception as exc:
            logger.exception("Failed to ensure bucket {}: {}", bucket_name, exc)
            raise StoreException(f"Failed to ensure bucket {bucket_name}: {exc}")

    async def ensure_buckets(self) -> None:
        await self.ensure_bucket(MinioBucketNameEnum.LITERATURE_UPLOADS.value)
        await self.ensure_bucket(MinioBucketNameEnum.PROCESSED_RESULTS.value)

    async def upload_bytes(
        self,
        bucket: MinioBucketNameEnum,
        object_key: str,
        payload: bytes,
        content_type: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> MinioObjectRefModel:
        await self.ensure_bucket(bucket.value)
        data = BytesIO(payload)
        await self.upload_file(
            bucket=bucket.value,
            object_key=object_key,
            file_data=data,
            content_type=content_type,
            metadata=metadata,
        )
        return MinioObjectRefModel(
            bucket=bucket,
            object_key=object_key,
            content_type=content_type,
        )

    async def download_bytes(self, bucket: MinioBucketNameEnum, object_key: str) -> bytes:
        buffer = await self.download_file(bucket.value, object_key)
        return buffer.getvalue()

    async def upload_literature_upload(
        self,
        payload: bytes,
        content_type: str,
        storage_key: Optional[str] = None,
        filename: Optional[str] = None,
        object_prefix: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> MinioObjectRefModel:
        if storage_key:
            object_key = storage_key
        elif filename:
            object_key = f"{object_prefix}/{filename}" if object_prefix else filename
        else:
            raise ValueError("storage_key or filename is required for literature upload")

        return await self.upload_bytes(
            bucket=MinioBucketNameEnum.LITERATURE_UPLOADS,
            object_key=object_key,
            payload=payload,
            content_type=content_type,
            metadata=metadata,
        )

    async def download_literature_upload(self, object_key: str) -> bytes:
        return await self.download_bytes(MinioBucketNameEnum.LITERATURE_UPLOADS, object_key)

    async def upload_processed_result_json(
        self, document_id: str, payload: Dict[str, object]
    ) -> MinioObjectRefModel:
        object_key = self.build_processed_object_key(document_id, "ps3_evidence.json")
        content = json.dumps(payload, ensure_ascii=False, indent=4).encode("utf-8")
        return await self.upload_bytes(
            bucket=MinioBucketNameEnum.PROCESSED_RESULTS,
            object_key=object_key,
            payload=content,
            content_type="application/json",
        )

    async def download_processed_result_json(self, document_id: str) -> bytes:
        object_key = self.build_processed_object_key(document_id, "ps3_evidence.json")
        return await self.download_bytes(MinioBucketNameEnum.PROCESSED_RESULTS, object_key)

    async def download_processed_result(self, object_key: str) -> bytes:
        return await self.download_bytes(MinioBucketNameEnum.PROCESSED_RESULTS, object_key)

    async def upload_processed_result_bytes(
        self,
        document_id: str,
        object_name: str,
        payload: bytes,
        content_type: str,
    ) -> MinioObjectRefModel:
        object_key = self.build_processed_object_key(document_id, object_name)
        return await self.upload_bytes(
            bucket=MinioBucketNameEnum.PROCESSED_RESULTS,
            object_key=object_key,
            payload=payload,
            content_type=content_type,
        )

    async def upload_processed_image(
        self,
        document_id: str,
        filename: str,
        payload: bytes,
        content_type: str,
    ) -> MinioObjectRefModel:
        object_key = self.build_processed_image_key(document_id, filename)
        return await self.upload_bytes(
            bucket=MinioBucketNameEnum.PROCESSED_RESULTS,
            object_key=object_key,
            payload=payload,
            content_type=content_type,
        )


def get_minio_client() -> MinIOClient:
    return MinIOClient(
        endpoint=cfg.minio_endpoint,
        access_key=cfg.minio_access_key,
        secret_key=cfg.minio_secret_key,
        secure=cfg.minio_secure,
        bucket_name=cfg.minio_results_bucket,
    )
