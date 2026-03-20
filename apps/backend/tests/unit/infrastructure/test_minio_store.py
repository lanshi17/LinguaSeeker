"""MinIO存储单元测试"""

import os
import ssl
import tempfile
from typing import cast
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.config import AppConfig, MinIOConfig
from src.infrastructure.store.minio_store import MinIOStore
from src.utils.exceptions import StoreException


@pytest.fixture
def app_config() -> AppConfig:
    """创建模拟的应用配置"""
    config = AppConfig()
    config.minio = MinIOConfig(
        endpoint="localhost:9000",
        access_key="test_access_key",
        secret_key="test_secret_key",
        bucket_name="test-bucket",
        secure=False,
    )
    return config


@pytest.fixture
def minio_store(app_config: AppConfig) -> MinIOStore:
    """创建MinIOStore实例"""
    with patch("src.infrastructure.store.minio_store.Minio") as mock_minio:
        mock_client = MagicMock()
        mock_minio.return_value = mock_client
        mock_client.bucket_exists.return_value = True

        store = MinIOStore(app_config)
        store.client = mock_client
        return store


class TestMinIOStore:
    """MinIO存储测试类"""

    def test_initialization(self, app_config: AppConfig) -> None:
        """测试MinIO存储初始化"""
        with patch("src.infrastructure.store.minio_store.Minio") as mock_minio:
            mock_client = MagicMock()
            mock_minio.return_value = mock_client
            mock_client.bucket_exists.return_value = False

            MinIOStore(app_config)

            mock_minio.assert_called_once_with(
                "localhost:9000",
                access_key="test_access_key",
                secret_key="test_secret_key",
                secure=False,
            )
            mock_client.make_bucket.assert_called_once_with("test-bucket")

    def test_initialization_with_url_and_path_endpoint(
        self, app_config: AppConfig
    ) -> None:
        """测试带协议和路径的endpoint被正确解析"""
        app_config.minio.endpoint = "https://storage.internal:9443/minio"
        with patch("src.infrastructure.store.minio_store.Minio") as mock_minio:
            mock_client = MagicMock()
            mock_minio.return_value = mock_client
            mock_client.bucket_exists.return_value = True

            MinIOStore(app_config)

            mock_minio.assert_called_once_with(
                "storage.internal:9443",
                access_key="test_access_key",
                secret_key="test_secret_key",
                secure=True,
            )

    def test_initialization_without_scheme_preserves_secure_flag(
        self, app_config: AppConfig
    ) -> None:
        """测试无协议endpoint沿用配置secure标志"""
        app_config.minio.endpoint = "minio:9000/path/to/service"
        app_config.minio.secure = True
        with patch("src.infrastructure.store.minio_store.Minio") as mock_minio:
            mock_client = MagicMock()
            mock_minio.return_value = mock_client
            mock_client.bucket_exists.return_value = True

            MinIOStore(app_config)

            mock_minio.assert_called_once_with(
                "minio:9000",
                access_key="test_access_key",
                secret_key="test_secret_key",
                secure=True,
            )

    def test_initialization_ssl_error_falls_back_to_insecure(
        self, app_config: AppConfig
    ) -> None:
        """测试SSL错误时自动降级为HTTP"""
        app_config.minio.endpoint = "https://localhost:9000"
        app_config.minio.secure = True

        def _minio_ctor(endpoint, access_key=None, secret_key=None, secure=None):
            if secure:
                raise ssl.SSLError("wrong version")
            client = MagicMock()
            client.bucket_exists.return_value = True
            return client

        with patch(
            "src.infrastructure.store.minio_store.Minio", side_effect=_minio_ctor
        ) as mock_minio:
            store = MinIOStore(app_config)

            assert mock_minio.call_count == 2
            first_call = mock_minio.call_args_list[0]
            second_call = mock_minio.call_args_list[1]
            assert first_call.kwargs["secure"] is True
            assert second_call.kwargs["secure"] is False
            assert store.client is not None

    def test_upload_file(self, minio_store: MinIOStore) -> None:
        """测试文件上传"""
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".txt"
        ) as file_handle:
            file_handle.write("test content")
            temp_file = file_handle.name

        try:
            minio_store.upload_file(temp_file, "test/object.txt")

            mock_client = cast(MagicMock, minio_store.client)
            mock_client.fput_object.assert_called_once()
            kwargs = mock_client.fput_object.call_args.kwargs
            assert kwargs["bucket_name"] == "test-bucket"
            assert kwargs["object_name"] == "test/object.txt"
            assert kwargs["file_path"] == temp_file
        finally:
            os.remove(temp_file)

    def test_upload_file_not_found(self, minio_store: MinIOStore) -> None:
        """测试上传不存在的文件"""
        with pytest.raises(StoreException) as exc_info:
            minio_store.upload_file("/nonexistent/file.txt", "test/object.txt")

        assert "File not found" in str(exc_info.value)

    def test_download_file(self, minio_store: MinIOStore) -> None:
        """测试文件下载"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest_path = os.path.join(tmpdir, "downloaded.txt")

            minio_store.download_file("test/object.txt", dest_path)

            mock_client = cast(MagicMock, minio_store.client)
            mock_client.fget_object.assert_called_once_with(
                "test-bucket", "test/object.txt", dest_path
            )

    def test_delete_file(self, minio_store: MinIOStore) -> None:
        """测试文件删除"""
        minio_store.delete_file("test/object.txt")

        mock_client = cast(MagicMock, minio_store.client)
        mock_client.remove_object.assert_called_once_with(
            "test-bucket", "test/object.txt"
        )

    def test_list_files(self, minio_store: MinIOStore) -> None:
        """测试列出文件"""
        mock_obj1 = Mock()
        mock_obj1.object_name = "test/file1.txt"
        mock_obj2 = Mock()
        mock_obj2.object_name = "test/file2.txt"

        mock_client = cast(MagicMock, minio_store.client)
        mock_client.list_objects.return_value = [mock_obj1, mock_obj2]

        files = minio_store.list_files(prefix="test/")

        assert len(files) == 2
        assert "test/file1.txt" in files
        assert "test/file2.txt" in files
        mock_client.list_objects.assert_called_once_with(
            "test-bucket", prefix="test/", recursive=True
        )

    def test_save_and_retrieve(self, minio_store: MinIOStore) -> None:
        """测试保存和检索数据"""
        test_data = b"test binary data"
        object_name = "test/data.bin"

        with patch("tempfile.NamedTemporaryFile") as mock_temp:
            mock_file = MagicMock()
            mock_file.name = "/tmp/test123"
            mock_temp.return_value.__enter__.return_value = mock_file

            with patch("os.remove"):
                minio_store.save(test_data, object_name)

            mock_file.write.assert_called_once_with(test_data)
            mock_client = cast(MagicMock, minio_store.client)
            mock_client.fput_object.assert_called_once()

    def test_extract_and_upload_zip(self, minio_store: MinIOStore) -> None:
        """测试ZIP文件解压和上传"""
        import zipfile

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "test.zip")

            with zipfile.ZipFile(zip_path, "w") as zip_file:
                zip_file.writestr("file1.txt", "content1")
                zip_file.writestr("folder/file2.txt", "content2")

            with patch.object(minio_store, "upload_file") as mock_upload:
                uploaded_files = minio_store.extract_and_upload_zip(
                    zip_path, "test_prefix"
                )

                assert mock_upload.call_count == 2
                assert len(uploaded_files) == 2

    @patch("src.infrastructure.store.minio_store.requests.get")
    def test_download_and_extract_zip(
        self, mock_get: MagicMock, minio_store: MinIOStore
    ) -> None:
        """测试从URL下载并解压ZIP"""
        import zipfile

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "test.zip")
            with zipfile.ZipFile(zip_path, "w") as zip_file:
                zip_file.writestr("test.txt", "content")

            with open(zip_path, "rb") as file_handle:
                zip_content = file_handle.read()

        mock_response = MagicMock()
        mock_response.iter_content.return_value = [zip_content]
        mock_get.return_value = mock_response

        with patch.object(minio_store, "extract_and_upload_zip") as mock_extract:
            mock_extract.return_value = ["test_prefix/test.txt"]

            result = minio_store.download_and_extract_zip(
                "http://example.com/test.zip", "test_prefix"
            )

            mock_get.assert_called_once()
            mock_extract.assert_called_once()
            assert len(result) == 1


class TestMinIOStoreIntegration:
    """MinIO存储集成测试（需要实际的MinIO服务）"""

    @pytest.mark.integration
    @pytest.mark.skipif(
        os.getenv("MINIO_ENDPOINT") is None, reason="MinIO not configured"
    )
    def test_real_minio_connection(self) -> None:
        """测试实际的MinIO连接（集成测试）"""
        app_config = AppConfig.from_env()
        store = MinIOStore(app_config)

        files = store.list_files()
        assert isinstance(files, list)
