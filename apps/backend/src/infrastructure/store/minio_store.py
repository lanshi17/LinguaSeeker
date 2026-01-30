from typing import Optional, List, Tuple
from .base_store import BaseStore
from src.config.database_config import DatabaseConfig
from src.utils.logger import Logger
from src.utils.exceptions import StoreException
import os
from minio import Minio
from minio.error import S3Error
import zipfile
import tempfile
import requests
from urllib.parse import urlparse
import ssl
from urllib3.exceptions import SSLError as Urllib3SSLError, MaxRetryError
from requests.exceptions import SSLError as RequestsSSLError

class MinIOStore(BaseStore):
    """MinIO对象存储实现类"""

    def __init__(self, db_config: DatabaseConfig):
        super().__init__()
        self.config = db_config.minio
        self.logger = Logger.get_logger("MinIOStore")

        # 初始化MinIO客户端
        endpoint, secure = self._sanitize_endpoint(self.config.endpoint, self.config.secure)
        try:
            self._initialize_client(endpoint, secure)
        except Exception as exc:
            if self._should_retry_insecure(exc, secure):
                self.logger.warning(
                    "SSL handshake failed for MinIO endpoint %s (%s); retrying with secure=False",
                    endpoint,
                    exc,
                )
                try:
                    self._initialize_client(endpoint, False)
                    return
                except Exception as retry_exc:
                    self.logger.error(
                        f"Failed to initialize MinIO client after SSL fallback: {retry_exc}"
                    )
                    raise StoreException(
                        f"MinIO initialization failed after SSL fallback: {retry_exc}"
                    ) from retry_exc

            self.logger.error(f"Failed to initialize MinIO client: {exc}")
            raise StoreException(f"MinIO initialization failed: {exc}") from exc

    def _sanitize_endpoint(self, raw_endpoint: str, secure_flag: bool) -> Tuple[str, bool]:
        """Normalize endpoint to host:port and derive secure flag if scheme is provided."""
        endpoint = (raw_endpoint or "").strip()
        if not endpoint:
            raise StoreException("MinIO endpoint cannot be empty")

        parts = urlparse(endpoint) if "://" in endpoint else urlparse(f"//{endpoint}")
        host = parts.netloc or parts.path

        if not host:
            raise StoreException(f"Invalid MinIO endpoint: {endpoint}")

        final_secure = secure_flag
        if parts.scheme:
            if parts.scheme not in ("http", "https"):
                raise StoreException(f"Unsupported MinIO endpoint scheme: {parts.scheme}")
            final_secure = parts.scheme == "https"

        if parts.path and parts.path not in ("", "/"):
            self.logger.warning(
                "Ignoring path %s in MinIO endpoint %s; MinIO only accepts host:port",
                parts.path,
                raw_endpoint,
            )

        if parts.query:
            self.logger.warning(
                "Ignoring query %s in MinIO endpoint %s; MinIO only accepts host:port",
                parts.query,
                raw_endpoint,
            )

        return host, final_secure

    def _initialize_client(self, endpoint: str, secure: bool) -> None:
        """Create MinIO client and ensure bucket availability."""
        self.client = Minio(
            endpoint,
            access_key=self.config.access_key,
            secret_key=self.config.secret_key,
            secure=secure
        )
        self.logger.info(
            "MinIO client initialized: endpoint=%s (raw=%s), secure=%s",
            endpoint,
            self.config.endpoint,
            secure,
        )
        self._ensure_bucket_exists()

    def _should_retry_insecure(self, exc: Exception, secure: bool) -> bool:
        """Determine whether to retry initialization over HTTP when SSL errors occur."""
        if not secure:
            return False

        ssl_error_types = (ssl.SSLError, RequestsSSLError, Urllib3SSLError)
        if isinstance(exc, ssl_error_types):
            return True

        reason = getattr(exc, "reason", None)
        if isinstance(reason, ssl_error_types):
            return True

        if isinstance(exc, MaxRetryError):
            inner = getattr(exc, "reason", None)
            if isinstance(inner, ssl_error_types):
                return True

        return "SSL" in str(exc).upper()

    def _ensure_bucket_exists(self) -> None:
        """确保bucket存在，不存在则创建"""
        try:
            if not self.client.bucket_exists(self.config.bucket_name):
                self.client.make_bucket(self.config.bucket_name)
                self.logger.info(f"Created bucket: {self.config.bucket_name}")
            else:
                self.logger.info(f"Bucket already exists: {self.config.bucket_name}")
        except S3Error as e:
            self.logger.error(f"Failed to ensure bucket exists: {e}")
            raise StoreException(f"Bucket operation failed: {e}")

    def save(self, data: bytes, destination: str) -> None:
        """保存数据到MinIO

        Args:
            data: 要保存的字节数据
            destination: MinIO中的对象名称（路径）
        """
        try:
            # 创建临时文件保存数据
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_file.write(data)
                tmp_file_path = tmp_file.name

            # 上传到MinIO
            self.client.fput_object(
                self.config.bucket_name,
                destination,
                tmp_file_path
            )

            # 清理临时文件
            os.remove(tmp_file_path)

            self.logger.info(f"Successfully saved data to MinIO: {destination}")
        except S3Error as e:
            self.logger.error(f"Failed to save data to MinIO: {e}")
            raise StoreException(f"MinIO save failed: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error saving to MinIO: {e}")
            raise StoreException(f"Save operation failed: {e}")

    def retrieve(self, source: str) -> bytes:
        """从MinIO检索数据

        Args:
            source: MinIO中的对象名称（路径）

        Returns:
            对象的字节数据
        """
        try:
            # 创建临时文件保存下载的数据
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_file_path = tmp_file.name

            # 从MinIO下载
            self.client.fget_object(
                self.config.bucket_name,
                source,
                tmp_file_path
            )

            # 读取数据
            with open(tmp_file_path, 'rb') as f:
                data = f.read()

            # 清理临时文件
            os.remove(tmp_file_path)

            self.logger.info(f"Successfully retrieved data from MinIO: {source}")
            return data
        except S3Error as e:
            self.logger.error(f"Failed to retrieve data from MinIO: {e}")
            raise StoreException(f"MinIO retrieve failed: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error retrieving from MinIO: {e}")
            raise StoreException(f"Retrieve operation failed: {e}")

    def upload_file(self, file_path: str, object_name: str, content_type: Optional[str] = None) -> None:
        """上传文件到MinIO存储

        Args:
            file_path: 本地文件路径
            object_name: MinIO中的对象名称
            content_type: 文件的MIME类型（可选）
        """
        try:
            if not os.path.exists(file_path):
                raise StoreException(f"File not found: {file_path}")

            self.client.fput_object(
                self.config.bucket_name,
                object_name,
                file_path,
                content_type=content_type
            )
            self.logger.info(f"Successfully uploaded file to MinIO: {file_path} -> {object_name}")
        except S3Error as e:
            self.logger.error(f"Failed to upload file to MinIO: {e}")
            raise StoreException(f"MinIO upload failed: {e}")

    def download_file(self, object_name: str, destination_path: str) -> None:
        """从MinIO存储下载文件

        Args:
            object_name: MinIO中的对象名称
            destination_path: 本地保存路径
        """
        try:
            # 确保目标目录存在
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)

            self.client.fget_object(
                self.config.bucket_name,
                object_name,
                destination_path
            )
            self.logger.info(f"Successfully downloaded file from MinIO: {object_name} -> {destination_path}")
        except S3Error as e:
            self.logger.error(f"Failed to download file from MinIO: {e}")
            raise StoreException(f"MinIO download failed: {e}")

    def delete_file(self, object_name: str) -> None:
        """删除MinIO存储中的文件

        Args:
            object_name: MinIO中的对象名称
        """
        try:
            self.client.remove_object(self.config.bucket_name, object_name)
            self.logger.info(f"Successfully deleted file from MinIO: {object_name}")
        except S3Error as e:
            self.logger.error(f"Failed to delete file from MinIO: {e}")
            raise StoreException(f"MinIO delete failed: {e}")

    def list_files(self, prefix: str = "") -> List[str]:
        """列出MinIO中的文件

        Args:
            prefix: 对象名称前缀（用于过滤）

        Returns:
            对象名称列表
        """
        try:
            objects = self.client.list_objects(
                self.config.bucket_name,
                prefix=prefix,
                recursive=True
            )
            file_list = [obj.object_name for obj in objects]
            self.logger.info(f"Listed {len(file_list)} files with prefix: {prefix}")
            return file_list
        except S3Error as e:
            self.logger.error(f"Failed to list files in MinIO: {e}")
            raise StoreException(f"MinIO list failed: {e}")

    def extract_and_upload_zip(self, zip_file_path: str, base_object_name: str) -> List[str]:
        """解压ZIP文件并上传所有内容到MinIO

        Args:
            zip_file_path: 本地ZIP文件路径
            base_object_name: MinIO中的基础路径（前缀）

        Returns:
            上传的对象名称列表
        """
        uploaded_files = []
        temp_extract_dir = None

        try:
            if not os.path.exists(zip_file_path):
                raise StoreException(f"ZIP file not found: {zip_file_path}")

            # 创建临时目录用于解压
            temp_extract_dir = tempfile.mkdtemp(prefix="mineru_extract_")
            self.logger.info(f"Extracting ZIP to temporary directory: {temp_extract_dir}")

            # 解压ZIP文件
            with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract_dir)

            # 遍历解压后的文件并上传到MinIO
            for root, dirs, files in os.walk(temp_extract_dir):
                for file in files:
                    local_file_path = os.path.join(root, file)
                    # 计算相对路径
                    relative_path = os.path.relpath(local_file_path, temp_extract_dir)
                    # 构建MinIO对象名称
                    object_name = f"{base_object_name}/{relative_path}".replace("\\", "/")

                    # 上传文件
                    self.upload_file(local_file_path, object_name)
                    uploaded_files.append(object_name)

            self.logger.info(f"Successfully extracted and uploaded {len(uploaded_files)} files from ZIP")
            return uploaded_files

        except zipfile.BadZipFile as e:
            self.logger.error(f"Invalid ZIP file: {e}")
            raise StoreException(f"Invalid ZIP file: {e}")
        except Exception as e:
            self.logger.error(f"Failed to extract and upload ZIP: {e}")
            raise StoreException(f"ZIP extraction and upload failed: {e}")
        finally:
            # 清理临时目录
            if temp_extract_dir and os.path.exists(temp_extract_dir):
                import shutil
                shutil.rmtree(temp_extract_dir, ignore_errors=True)
                self.logger.info(f"Cleaned up temporary extraction directory")

    def download_and_extract_zip(self, zip_url: str, base_object_name: str) -> List[str]:
        """从URL下载ZIP文件，解压并上传到MinIO

        Args:
            zip_url: ZIP文件的下载URL
            base_object_name: MinIO中的基础路径（前缀）

        Returns:
            上传的对象名称列表
        """
        temp_zip_path = None

        try:
            # 下载ZIP文件到临时位置
            temp_zip_path = tempfile.mktemp(suffix=".zip")
            self.logger.info(f"Downloading ZIP from URL: {zip_url}")

            response = requests.get(zip_url, stream=True, timeout=300)
            response.raise_for_status()

            with open(temp_zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            self.logger.info(f"ZIP file downloaded successfully: {temp_zip_path}")

            # 解压并上传
            return self.extract_and_upload_zip(temp_zip_path, base_object_name)

        except requests.RequestException as e:
            self.logger.error(f"Failed to download ZIP from URL: {e}")
            raise StoreException(f"ZIP download failed: {e}")
        finally:
            # 清理临时ZIP文件
            if temp_zip_path and os.path.exists(temp_zip_path):
                os.remove(temp_zip_path)
                self.logger.info(f"Cleaned up temporary ZIP file")
