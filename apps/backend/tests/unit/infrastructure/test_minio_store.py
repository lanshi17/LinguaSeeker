"""MinIO存储单元测试"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from config.database_config import DatabaseConfig, MinIOConfig
from infrastructure.store.minio_store import MinIOStore
from utils.exceptions import StoreException
from unittest import mock
from unittest.mock import MagicMock, Mock, patch
from io import BytesIO
from config.database_config import DatabaseConfig, MinIOConfig



@pytest.fixture
def mock_db_config():
    """创建模拟的数据库配置"""
    config = Mock(spec=DatabaseConfig)
    config.minio = MinIOConfig(
        endpoint="localhost:9000",
        access_key="test_access_key",
        secret_key="test_secret_key",
        bucket_name="test-bucket",
        secure=False
    )
    return config


@pytest.fixture
def minio_store(mock_db_config):
    """创建MinIOStore实例"""
    with patch('infrastructure.store.minio_store.Minio') as mock_minio:
        mock_client = MagicMock()
        mock_minio.return_value = mock_client
        mock_client.bucket_exists.return_value = True

        store = MinIOStore(mock_db_config)
        store.client = mock_client
        return store


class TestMinIOStore:
    """MinIO存储测试类"""

    def test_initialization(self, mock_db_config):
        """测试MinIO存储初始化"""
        with patch('infrastructure.store.minio_store.Minio') as mock_minio:
            mock_client = MagicMock()
            mock_minio.return_value = mock_client
            mock_client.bucket_exists.return_value = False

            store = MinIOStore(mock_db_config)

            # 验证Minio客户端被正确初始化
            mock_minio.assert_called_once_with(
                "localhost:9000",
                access_key="test_access_key",
                secret_key="test_secret_key",
                secure=False
            )

            # 验证bucket创建被调用
            mock_client.make_bucket.assert_called_once_with("test-bucket")

    def test_upload_file(self, minio_store):
        """测试文件上传"""
        # 创建临时测试文件
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("test content")
            temp_file = f.name

        try:
            minio_store.upload_file(temp_file, "test/object.txt")

            # 验证fput_object被调用
            minio_store.client.fput_object.assert_called_once()
            args = minio_store.client.fput_object.call_args[0]
            assert args[0] == "test-bucket"
            assert args[1] == "test/object.txt"
            assert args[2] == temp_file
        finally:
            os.remove(temp_file)

    def test_upload_file_not_found(self, minio_store):
        """测试上传不存在的文件"""
        with pytest.raises(StoreException) as exc_info:
            minio_store.upload_file("/nonexistent/file.txt", "test/object.txt")

        assert "File not found" in str(exc_info.value)

    def test_download_file(self, minio_store):
        """测试文件下载"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest_path = os.path.join(tmpdir, "downloaded.txt")

            minio_store.download_file("test/object.txt", dest_path)

            # 验证fget_object被调用
            minio_store.client.fget_object.assert_called_once_with(
                "test-bucket",
                "test/object.txt",
                dest_path
            )

    def test_delete_file(self, minio_store):
        """测试文件删除"""
        minio_store.delete_file("test/object.txt")

        # 验证remove_object被调用
        minio_store.client.remove_object.assert_called_once_with(
            "test-bucket",
            "test/object.txt"
        )

    def test_list_files(self, minio_store):
        """测试列出文件"""
        # 模拟返回的对象列表
        mock_obj1 = Mock()
        mock_obj1.object_name = "test/file1.txt"
        mock_obj2 = Mock()
        mock_obj2.object_name = "test/file2.txt"

        minio_store.client.list_objects.return_value = [mock_obj1, mock_obj2]

        files = minio_store.list_files(prefix="test/")

        assert len(files) == 2
        assert "test/file1.txt" in files
        assert "test/file2.txt" in files

        # 验证list_objects被正确调用
        minio_store.client.list_objects.assert_called_once_with(
            "test-bucket",
            prefix="test/",
            recursive=True
        )

    def test_save_and_retrieve(self, minio_store):
        """测试保存和检索数据"""
        test_data = b"test binary data"
        object_name = "test/data.bin"

        # 测试保存
        with patch('tempfile.NamedTemporaryFile') as mock_temp:
            mock_file = MagicMock()
            mock_file.name = "/tmp/test123"
            mock_temp.return_value.__enter__.return_value = mock_file

            with patch('os.remove'):
                minio_store.save(test_data, object_name)

            mock_file.write.assert_called_once_with(test_data)
            minio_store.client.fput_object.assert_called_once()

    def test_extract_and_upload_zip(self, minio_store):
        """测试ZIP文件解压和上传"""
        import zipfile

        # 创建临时ZIP文件
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "test.zip")

            # 创建一个简单的ZIP文件
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr("file1.txt", "content1")
                zf.writestr("folder/file2.txt", "content2")

            # 执行解压和上传
            with patch.object(minio_store, 'upload_file') as mock_upload:
                uploaded_files = minio_store.extract_and_upload_zip(
                    zip_path,
                    "test_prefix"
                )

                # 验证上传被调用了2次（2个文件）
                assert mock_upload.call_count == 2
                assert len(uploaded_files) == 2

    @patch('infrastructure.store.minio_store.requests.get')
    def test_download_and_extract_zip(self, mock_get, minio_store):
        """测试从URL下载并解压ZIP"""
        import zipfile

        # 创建模拟的ZIP内容
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "test.zip")
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr("test.txt", "content")

            with open(zip_path, 'rb') as f:
                zip_content = f.read()

        # 模拟HTTP响应
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [zip_content]
        mock_get.return_value = mock_response

        # 执行下载和解压
        with patch.object(minio_store, 'extract_and_upload_zip') as mock_extract:
            mock_extract.return_value = ["test_prefix/test.txt"]

            result = minio_store.download_and_extract_zip(
                "http://example.com/test.zip",
                "test_prefix"
            )

            # 验证下载被调用
            mock_get.assert_called_once()
            # 验证解压被调用
            mock_extract.assert_called_once()
            assert len(result) == 1


class TestMinIOStoreIntegration:
    """MinIO存储集成测试（需要实际的MinIO服务）"""

    @pytest.mark.integration
    @pytest.mark.skipif(
        os.getenv("MINIO_ENDPOINT") is None,
        reason="MinIO not configured"
    )
    def test_real_minio_connection(self):
        """测试实际的MinIO连接（集成测试）"""
        db_config = DatabaseConfig.from_env()
        store = MinIOStore(db_config)

        # 测试列出文件
        files = store.list_files()
        assert isinstance(files, list)
