"""MinIO implementation of Storage Client.

S3-compatible object storage client using MinIO.
"""

import os
import asyncio
from io import BytesIO
from typing import BinaryIO, Dict, List, Optional
import base64

from minio import Minio
from minio.error import S3Error
from urllib3.exceptions import MaxRetryError

from src.domain.interfaces.storage_client import StorageClient
from src.utils.logger import Logger


class MinIOStorageClient(StorageClient):
    """MinIO implementation of storage client.

    Provides S3-compatible object storage for PDFs, parsed documents,
    and extracted data using MinIO.
    """

    def __init__(
        self,
        endpoint: str = None,
        access_key: str = None,
        secret_key: str = None,
        secure: bool = True,
        bucket_name: str = None,
    ):
        """Initialize MinIO client.

        Args:
            endpoint: MinIO endpoint (e.g., "localhost:9000")
            access_key: Access key ID
            secret_key: Secret access key
            secure: Use HTTPS if True, HTTP if False
            bucket_name: Default bucket name
        """
        from src.config.app_config import AppConfig
        config = AppConfig.from_env()

        self.endpoint = endpoint or config.minio_endpoint
        self.access_key = access_key or config.minio_access_key
        self.secret_key = secret_key or config.minio_secret_key
        self.secure = secure
        self.bucket_name = bucket_name or config.minio_bucket
        self.logger = Logger()

        try:
            self.client = Minio(
                endpoint=self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
            )
        except Exception as e:
            raise ConnectionError(f"Failed to connect to MinIO: {e}")

    async def upload_file(
        self,
        bucket: str,
        object_key: str,
        file_data: BinaryIO,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """Upload a file to MinIO."""
        try:
            # Ensure bucket exists
            if not await self.bucket_exists(bucket):
                await self.create_bucket(bucket)

            # Get file size
            file_data.seek(0, os.SEEK_END)
            file_size = file_data.tell()
            file_data.seek(0)

            # Upload
            self.client.put_object(
                bucket_name=bucket,
                object_name=object_key,
                data=file_data,
                length=file_size,
                content_type=content_type or "application/octet-stream",
                metadata=metadata,
            )

            # Return object path
            protocol = "https" if self.secure else "http"
            return f"{protocol}://{self.endpoint}/{bucket}/{object_key}"

        except S3Error as e:
            raise IOError(f"Failed to upload file: {e}")

    async def download_file(self, bucket: str, object_key: str) -> BytesIO:
        """Download a file from MinIO."""
        try:
            response = self.client.get_object(
                bucket_name=bucket,
                object_name=object_key,
            )

            # Read into BytesIO
            data = BytesIO(response.read())
            response.close()
            response.release_conn()

            return data

        except S3Error as e:
            if e.code == "NoSuchKey":
                raise FileNotFoundError(f"Object not found: {bucket}/{object_key}")
            raise IOError(f"Failed to download file: {e}")

    async def delete_file(self, bucket: str, object_key: str) -> bool:
        """Delete a file from MinIO."""
        try:
            self.client.remove_object(
                bucket_name=bucket,
                object_name=object_key,
            )
            return True

        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            raise IOError(f"Failed to delete file: {e}")

    async def file_exists(self, bucket: str, object_key: str) -> bool:
        """Check if a file exists in MinIO."""
        try:
            self.client.stat_object(
                bucket_name=bucket,
                object_name=object_key,
            )
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            raise IOError(f"Failed to check file existence: {e}")

    async def get_file_metadata(
        self, bucket: str, object_key: str
    ) -> Dict[str, str]:
        """Get file metadata."""
        try:
            stat = self.client.stat_object(
                bucket_name=bucket,
                object_name=object_key,
            )

            metadata = {
                "size": str(stat.size),
                "etag": stat.etag,
                "content_type": stat.content_type or "application/octet-stream",
                "last_modified": stat.last_modified.isoformat(),
            }

            # Add custom metadata
            if stat.metadata:
                metadata.update(stat.metadata)

            return metadata

        except S3Error as e:
            if e.code == "NoSuchKey":
                raise FileNotFoundError(f"Object not found: {bucket}/{object_key}")
            raise IOError(f"Failed to get metadata: {e}")

    async def list_objects(
        self, bucket: str, prefix: Optional[str] = None, limit: int = 1000
    ) -> List[str]:
        """List objects in a bucket."""
        try:
            objects = self.client.list_objects(
                bucket_name=bucket,
                prefix=prefix,
                recursive=True,
            )

            # Collect object names
            names = []
            for obj in objects:
                names.append(obj.object_name)
                if len(names) >= limit:
                    break

            return names

        except S3Error as e:
            raise IOError(f"Failed to list objects: {e}")

    async def create_bucket(self, bucket: str) -> bool:
        """Create a storage bucket."""
        try:
            if await self.bucket_exists(bucket):
                return False

            self.client.make_bucket(bucket)
            return True

        except S3Error as e:
            raise IOError(f"Failed to create bucket: {e}")

    async def bucket_exists(self, bucket: str) -> bool:
        """Check if a bucket exists."""
        try:
            return self.client.bucket_exists(bucket)
        except S3Error as e:
            raise IOError(f"Failed to check bucket existence: {e}")

    async def delete_bucket(self, bucket: str, force: bool = False) -> bool:
        """Delete a storage bucket."""
        try:
            if force:
                # Remove all objects first
                objects = self.client.list_objects(bucket, recursive=True)
                for obj in objects:
                    self.client.remove_object(bucket, obj.object_name)

            self.client.remove_bucket(bucket)
            return True

        except S3Error as e:
            if e.code == "NoSuchBucket":
                return False
            if e.code == "BucketNotEmpty" and not force:
                raise ValueError(f"Bucket {bucket} is not empty. Use force=True to delete.")
            raise IOError(f"Failed to delete bucket: {e}")

    async def get_presigned_url(
        self,
        bucket: str,
        object_key: str,
        expires_in: int = 3600,
        method: str = "GET",
    ) -> str:
        """Generate a presigned URL for temporary access."""
        try:
            if method == "GET":
                url = self.client.presigned_get_object(
                    bucket_name=bucket,
                    object_name=object_key,
                    expires=expires_in,
                )
            elif method == "PUT":
                url = self.client.presigned_put_object(
                    bucket_name=bucket,
                    object_name=object_key,
                    expires=expires_in,
                )
            else:
                raise ValueError(f"Unsupported method: {method}")

            return url

        except S3Error as e:
            raise IOError(f"Failed to generate presigned URL: {e}")

    async def copy_object(
        self,
        source_bucket: str,
        source_key: str,
        dest_bucket: str,
        dest_key: str,
    ) -> bool:
        """Copy an object within or between buckets."""
        try:
            from minio.commonconfig import CopySource

            copy_source = CopySource(source_bucket, source_key)

            self.client.copy_object(
                bucket_name=dest_bucket,
                object_name=dest_key,
                source=copy_source,
            )
            return True

        except S3Error as e:
            if e.code == "NoSuchKey":
                raise FileNotFoundError(f"Source object not found: {source_bucket}/{source_key}")
            raise IOError(f"Failed to copy object: {e}")

    async def get_object_size(self, bucket: str, object_key: str) -> int:
        """Get object size in bytes."""
        try:
            stat = self.client.stat_object(
                bucket_name=bucket,
                object_name=object_key,
            )
            return stat.size

        except S3Error as e:
            if e.code == "NoSuchKey":
                raise FileNotFoundError(f"Object not found: {bucket}/{object_key}")
            raise IOError(f"Failed to get object size: {e}")

    async def store_file(self, key: str, content: bytes, content_type: str = "application/octet-stream") -> str:
        """
        Store a file in MinIO storage.

        Args:
            key: Storage key (path/object name)
            content: File content as bytes
            content_type: MIME type of the content

        Returns:
            URL to the stored file
        """
        self.logger.info(f"Storing file with key: {key}")

        # Ensure bucket exists
        if not await self.bucket_exists(self.bucket_name):
            await self.create_bucket(self.bucket_name)

        # Upload file
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
            self.logger.info(f"File stored successfully: {url}")
            return url

        except S3Error as e:
            self.logger.error(f"Failed to store file {key}: {e}")
            raise IOError(f"Failed to store file: {e}")

    async def get_file(self, key: str) -> bytes:
        """
        Retrieve a file from MinIO storage.

        Args:
            key: Storage key (path/object name)

        Returns:
            File content as bytes
        """
        self.logger.info(f"Retrieving file with key: {key}")

        try:
            response = self.client.get_object(
                bucket_name=self.bucket_name,
                object_name=key,
            )

            content = response.read()
            response.close()
            response.release_conn()

            self.logger.info(f"File retrieved successfully: {key} ({len(content)} bytes)")
            return content

        except S3Error as e:
            if e.code == "NoSuchKey":
                self.logger.error(f"File not found: {key}")
                raise FileNotFoundError(f"Object not found: {self.bucket_name}/{key}")
            self.logger.error(f"Failed to retrieve file {key}: {e}")
            raise IOError(f"Failed to retrieve file: {e}")
