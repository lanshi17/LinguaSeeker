# 编排文件处理流程
from src.domain.__init__ import PDFParser, DocumentStorage
from loguru import logger
from src.application.dtos.document_dto import DocumentUploadDTO, DocumentProcessResultDTO
from typing import Any, Dict, Optional
from datetime import datetime, timezone
import os
import uuid

class DocumentService:
    """文档服务类，负责处理文档相关的业务逻辑"""

    def __init__(
        self,
        parser: Optional[PDFParser] = None,
        storage: Optional[DocumentStorage] = None,
        **storage_kwargs: Any,
    ):
        self.pdf_parser: PDFParser = parser or PDFParser()
        self.document_storage = storage or DocumentStorage(**storage_kwargs)
        logger.info("DocumentService initialized with parser and storage")

    def process_pdf_document(self, document: DocumentUploadDTO) -> DocumentProcessResultDTO:
        """处理PDF文档(使用MinerU)并将结果存储到MinIO

        Args:
            document: DocumentUploadDTO对象,包含文档内容和临时文件路径
        Returns:
            DocumentProcessResultDTO对象，包含处理结果和存储信息
        """
        try:
            if not document.temp_file_path or not os.path.exists(document.temp_file_path):
                raise ValueError("Temporary file path is required and must exist")

            logger.info(f"Processing PDF document: {document.filename}")

            # 生成唯一的document ID
            document_id = str(uuid.uuid4())

            parse_result = self.pdf_parser.parse_with_mineru(
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
            result_dto = DocumentProcessResultDTO(
                document_id=document_id,
                file_name=document.filename,
                minio_prefix=storage_result.get("minio_prefix"),
                minio_files=storage_result.get("minio_files"),
                file_count=storage_result.get("file_count"),
                processed_at=datetime.now(timezone.utc),
                mineru_file_id=parse_result.get("file_id"),
                state=parse_result.get("state"),
                full_zip_url=parse_result.get("full_zip_url"),
            )
            return result_dto

        except Exception as e:
            logger.error(f"Error processing PDF document: {e}")
            raise


    def process_pdf(self, file_path: str, store_in_minio: bool = False, object_prefix: Optional[str] = None) -> Dict[str, Any]:
        """处理PDF文件并返回解析后的HTML内容

        Args:
            file_path: PDF文件路径
            store_in_minio: 是否将结果存储到MinIO
            object_prefix: MinIO对象名称前缀（可选）

        Returns:
            包含HTML内容和MinIO路径（如果存储）的字典
        """
        try:
            logger.info(f"Processing PDF file: {file_path}")
            content = self.pdf_parser.parse(file_path)
           

            result = {
                "content": content,
                "file_name": os.path.basename(file_path),
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }

            if store_in_minio:
                prefix = object_prefix or os.path.splitext(os.path.basename(file_path))[0]
                object_name = self.document_storage.store_html_content(content, prefix)
                result["minio_path"] = object_name

            logger.info("PDF file processed successfully")
            return result

        except Exception as e:
            logger.error(f"Error processing PDF file: {e}")
            raise

    def process_pdf_with_mineru(self, file_path: str, store_results: bool = True) -> Dict[str, Any]:
        """使用MinerU处理PDF文件并存储结果到MinIO"""
        try:
            logger.info(f"Processing PDF with MinerU: {file_path}")
            parse_result = self.pdf_parser.parse_with_mineru(file_path, document_id=None)
            result_data = {
                "file_id": parse_result.get("file_id"),
                "file_name": parse_result.get("file_name") or os.path.basename(file_path),
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
