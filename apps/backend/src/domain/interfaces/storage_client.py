"""Storage Client interface.

Defines the contract for object storage operations (MinIO/S3).
"""

from abc import ABC, abstractmethod
from io import BytesIO
from typing import BinaryIO, Dict, List, Optional


class StorageClient(ABC):
    """Abstract client for object storage operations.

    Provides S3-compatible storage interface for PDFs,
    parsed documents, and extracted data.
    """

    @abstractmethod
    async def upload_file(
        self,
        bucket: str,
        object_key: str,
        file_data: BinaryIO,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """Upload a file to object storage.

        Args:
            bucket: Bucket name
            object_key: Object key/path in bucket
            file_data: Binary file data
            content_type: MIME type (e.g., 'application/pdf')
            metadata: Custom metadata dictionary

        Returns:
            Object URL or path

        Raises:
            StorageError: If upload fails
        """
        pass

    @abstractmethod
    async def download_file(
        self, bucket: str, object_key: str
    ) -> BytesIO:
        """Download a file from object storage.

        Args:
            bucket: Bucket name
            object_key: Object key/path in bucket

        Returns:
            File data as BytesIO

        Raises:
            ObjectNotFoundError: If object doesn't exist
            StorageError: If download fails
        """
        pass

    @abstractmethod
    async def delete_file(self, bucket: str, object_key: str) -> bool:
        """Delete a file from object storage.

        Args:
            bucket: Bucket name
            object_key: Object key/path in bucket

        Returns:
            True if deleted, False if not found

        Raises:
            StorageError: If deletion fails
        """
        pass

    @abstractmethod
    async def file_exists(self, bucket: str, object_key: str) -> bool:
        """Check if a file exists in storage.

        Args:
            bucket: Bucket name
            object_key: Object key/path in bucket

        Returns:
            True if exists, False otherwise
        """
        pass

    @abstractmethod
    async def get_file_metadata(
        self, bucket: str, object_key: str
    ) -> Dict[str, str]:
        """Get file metadata.

        Args:
            bucket: Bucket name
            object_key: Object key/path in bucket

        Returns:
            Metadata dictionary

        Raises:
            ObjectNotFoundError: If object doesn't exist
        """
        pass

    @abstractmethod
    async def list_objects(
        self, bucket: str, prefix: Optional[str] = None, limit: int = 1000
    ) -> List[str]:
        """List objects in a bucket.

        Args:
            bucket: Bucket name
            prefix: Object key prefix filter
            limit: Maximum number of objects to return

        Returns:
            List of object keys
        """
        pass

    @abstractmethod
    async def create_bucket(self, bucket: str) -> bool:
        """Create a storage bucket.

        Args:
            bucket: Bucket name

        Returns:
            True if created, False if already exists

        Raises:
            StorageError: If creation fails
        """
        pass

    @abstractmethod
    async def bucket_exists(self, bucket: str) -> bool:
        """Check if a bucket exists.

        Args:
            bucket: Bucket name

        Returns:
            True if exists, False otherwise
        """
        pass

    @abstractmethod
    async def delete_bucket(self, bucket: str, force: bool = False) -> bool:
        """Delete a storage bucket.

        Args:
            bucket: Bucket name
            force: If True, delete even if bucket contains objects

        Returns:
            True if deleted

        Raises:
            BucketNotEmptyError: If bucket has objects and force=False
            StorageError: If deletion fails
        """
        pass

    @abstractmethod
    async def get_presigned_url(
        self,
        bucket: str,
        object_key: str,
        expires_in: int = 3600,
        method: str = "GET",
    ) -> str:
        """Generate a presigned URL for temporary access.

        Args:
            bucket: Bucket name
            object_key: Object key/path in bucket
            expires_in: URL expiration time in seconds
            method: HTTP method (GET, PUT, DELETE)

        Returns:
            Presigned URL string

        Raises:
            ObjectNotFoundError: If object doesn't exist (for GET)
            StorageError: If URL generation fails
        """
        pass

    @abstractmethod
    async def copy_object(
        self,
        source_bucket: str,
        source_key: str,
        dest_bucket: str,
        dest_key: str,
    ) -> bool:
        """Copy an object within or between buckets.

        Args:
            source_bucket: Source bucket name
            source_key: Source object key
            dest_bucket: Destination bucket name
            dest_key: Destination object key

        Returns:
            True if copied successfully

        Raises:
            ObjectNotFoundError: If source doesn't exist
            StorageError: If copy fails
        """
        pass

    @abstractmethod
    async def get_object_size(self, bucket: str, object_key: str) -> int:
        """Get object size in bytes.

        Args:
            bucket: Bucket name
            object_key: Object key/path in bucket

        Returns:
            Size in bytes

        Raises:
            ObjectNotFoundError: If object doesn't exist
        """
        pass
