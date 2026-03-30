# 领域层存储协调器,封装MinIO操作
from __future__ import annotations

from typing import Any, Dict, Optional
from datetime import datetime, timezone
import os

from src.infrastructure.store.minio_store import MinIOStore
from src.configs import DatabaseConfig
from src.utils.exceptions import StoreException
from src.utils.logger import Logger


class DocumentStorage:
    """封装MinIO存储逻辑,供应用层编排调用"""

    def __init__(
        self,
        store: Optional[MinIOStore] = None,
        db_config: Optional[DatabaseConfig] = None,
    ):
        self.logger = Logger.get_logger("DocumentStorage")
        self._minio_store: Optional[MinIOStore] = store
        self._db_config = db_config or DatabaseConfig.from_env()
        self._store_init_error: Optional[Exception] = None
        if self._minio_store:
            self.logger.info("DocumentStorage initialized with injected MinIOStore")
        else:
            self.logger.info("DocumentStorage initialized with lazy MinIOStore")

    def store_mineru_document(
        self,
        zip_url: Optional[str],
        filename: str,
        document_id: str,
    ) -> Dict[str, Any]:
        """存储上传文档的MinerU ZIP结果"""
        minio_prefix = self._build_document_prefix(filename, document_id)
        uploaded_files = self._store_zip_result(zip_url, minio_prefix)
        self.logger.info(
            f"Stored {len(uploaded_files)} files for document {document_id} under {minio_prefix}"
        )
        return {
            "minio_prefix": minio_prefix,
            "minio_files": uploaded_files,
            "file_count": len(uploaded_files),
        }

    def store_mineru_result(
        self,
        zip_url: Optional[str],
        file_path: str,
    ) -> Dict[str, Any]:
        """存储MinerU解析结果ZIP"""
        object_prefix = self._build_mineru_result_prefix(file_path)
        uploaded_files = self._store_zip_result(zip_url, object_prefix)
        self.logger.info(
            f"Stored {len(uploaded_files)} files for MinerU result under {object_prefix}"
        )
        return {
            "minio_prefix": object_prefix,
            "minio_files": uploaded_files,
        }

    def _store_zip_result(self, zip_url: Optional[str], object_prefix: str):
        if not zip_url:
            raise ValueError("MinerU did not return a ZIP URL")
        store = self._get_minio_store()
        return store.download_and_extract_zip(zip_url, object_prefix)

    def _build_document_prefix(self, filename: str, document_id: str) -> str:
        file_basename = os.path.splitext(filename)[0]
        return f"documents/{file_basename}/{document_id}"

    def _build_mineru_result_prefix(self, file_path: str) -> str:
        file_basename = os.path.splitext(os.path.basename(file_path))[0]
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return f"mineru_results/{file_basename}/{timestamp}"

    def _get_minio_store(self) -> MinIOStore:
        if self._minio_store is None:
            try:
                self._minio_store = MinIOStore(self._db_config)
                self._store_init_error = None
                self.logger.info("Lazy-initialized MinIOStore instance")
            except StoreException as exc:
                self._store_init_error = exc
                self.logger.error(f"Failed to initialize MinIOStore: {exc}")
                raise
            except Exception as exc:  # pragma: no cover - defensive safeguard
                self._store_init_error = exc
                self.logger.error(f"Unexpected error initializing MinIOStore: {exc}")
                raise StoreException(str(exc)) from exc
        return self._minio_store
