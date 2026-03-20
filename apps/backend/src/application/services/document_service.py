# 编排文件处理流程
from datetime import datetime, timezone
import os
from typing import Any, Dict, Optional
import uuid

from loguru import logger

from src.application.dtos.document_dto import (
    DocumentProcessResultDTO,
    DocumentUploadDTO,
)
from src.domain.__init__ import DocumentStorage, PDFParser
from src.infrastructure.adapters.mineru import MinerUAdapterImpl
from src.infrastructure.store.minio_store import MinIOStore


class DocumentService:
    """文档服务类，负责处理文档相关的业务逻辑"""

    def __init__(
        self,
        parser: Optional[PDFParser] = None,
        storage: Optional[DocumentStorage] = None,
        **storage_kwargs: Any,
    ):
        db_config = storage_kwargs.get("db_config")
        self.mineru_adapter = MinerUAdapterImpl()
        self.minio_store: MinIOStore | None = None
        self.pdf_parser: PDFParser = parser or PDFParser(
            mineru_adapter=self.mineru_adapter
        )

        if storage is not None:
            self.document_storage = storage
        elif db_config is not None:
            self.minio_store = MinIOStore(db_config)
            self.document_storage = DocumentStorage(
                store=self.minio_store,
                db_config=db_config,
            )
        else:
            self.document_storage = DocumentStorage(db_config=db_config)

        logger.info("DocumentService initialized with parser and storage")

    def process_pdf_document(self, document: DocumentUploadDTO) -> Dict[str, Any]:
        """处理PDF文档(使用MinerU)并将结果存储到MinIO

        Args:
            document: DocumentUploadDTO对象,包含文档内容和临时文件路径
        Returns:
            DocumentProcessResultDTO对象，包含处理结果和存储信息
        """
        try:
            if not document.temp_file_path or not os.path.exists(
                document.temp_file_path
            ):
                raise ValueError("Temporary file path is required and must exist")

            logger.info(f"Processing PDF document: {document.filename}")

            # 生成唯一的document ID
            document_id = str(uuid.uuid4())

            parse_result = self.pdf_parser.parse(
                document.temp_file_path,
                document_id=document_id,
            )
            storage_result = self.document_storage.store_mineru_document(
                parse_result.get("full_zip_url"),
                document.filename,
                document_id,
            )

            logger.info(
                f"Stored {storage_result.get('file_count')} files in MinIO under "
                f"{storage_result.get('minio_prefix')}"
            )
            # 构建处理结果DTO
            minio_prefix = str(storage_result.get("minio_prefix") or "")
            raw_minio_files = storage_result.get("minio_files")
            minio_files = raw_minio_files if isinstance(raw_minio_files, list) else []
            raw_file_count = storage_result.get("file_count")
            file_count = (
                raw_file_count if isinstance(raw_file_count, int) else len(minio_files)
            )

            result_dto = DocumentProcessResultDTO(
                document_id=document_id,
                file_name=document.filename,
                minio_prefix=minio_prefix,
                minio_files=minio_files,
                file_count=file_count,
                processed_at=datetime.now(timezone.utc),
                mineru_file_id=parse_result.get("file_id"),
                state=parse_result.get("state"),
                full_zip_url=parse_result.get("full_zip_url"),
            )
            return result_dto.model_dump()

        except Exception as e:
            logger.error(f"Error processing PDF document: {e}")
            raise

    def process_pdf_with_mineru(
        self, file_path: str, store_results: bool = True
    ) -> Dict[str, Any]:
        """使用MinerU处理PDF文件并存储结果到MinIO"""
        try:
            logger.info(f"Processing PDF with MinerU: {file_path}")
            parse_result = self.pdf_parser.parse(file_path, document_id=None)
            result_data = {
                "file_id": parse_result.get("file_id"),
                "file_name": parse_result.get("file_name")
                or os.path.basename(file_path),
                "status": parse_result.get("state"),
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "full_zip_url": parse_result.get("full_zip_url"),
            }

            if parse_result.get("state") == "completed" and store_results:
                storage_result = self.document_storage.store_mineru_result(
                    parse_result.get("full_zip_url"),
                    file_path,
                )
                result_data.update(storage_result)
                logger.info(
                    f"Stored {len(storage_result.get('minio_files', []))} files in MinIO under "
                    f"{storage_result.get('minio_prefix')}"
                )

            return result_data

        except Exception as e:
            logger.error(f"Error processing PDF with MinerU: {e}")
            raise
