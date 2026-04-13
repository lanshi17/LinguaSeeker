# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportCallIssue=false, reportGeneralTypeIssues=false, reportMissingImports=false, reportRedeclaration=false, reportFunctionMemberAccess=false, reportPossiblyUnboundVariable=false, reportReturnType=false

# 编排文件处理流程
from src.domain.impl import PDFParser, DocumentStorage
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

            parse_documents = getattr(self.pdf_parser, "parse_documents", None)
            if callable(parse_documents):
                parse_result = parse_documents([document.temp_file_path])
                artifacts = parse_result.artifacts
                return DocumentProcessResultDTO(
                    document_id=document_id,
                    file_name=document.filename,
                    processed_at=datetime.now(timezone.utc),
                    parser_backend=parse_result.parser_backend,
                    parser_task_id=parse_result.parser_task_id,
                    mineru_folder=parse_result.mineru_folder,
                    markdown_object_key=artifacts.markdown_object_key,
                    markdown_url=artifacts.markdown_url,
                    image_object_keys=list(artifacts.image_object_keys),
                    image_urls=list(artifacts.image_urls),
                    image_count=parse_result.image_count,
                )

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
            return DocumentProcessResultDTO(
                document_id=document_id,
                file_name=document.filename,
                processed_at=datetime.now(timezone.utc),
                minio_prefix=storage_result.get("minio_prefix"),
                minio_files=storage_result.get("minio_files"),
                file_count=storage_result.get("file_count"),
                mineru_file_id=parse_result.get("file_id"),
                state=parse_result.get("state"),
                full_zip_url=parse_result.get("full_zip_url"),
            )

        except Exception as e:
            logger.error(f"Error processing PDF document: {e}")
            raise

    def process_pdf_with_mineru(self, file_path: str, store_results: bool = True) -> Dict[str, Any]:
        """使用MinerU处理PDF文件并存储结果到MinIO"""
        try:
            logger.info(f"Processing PDF with MinerU: {file_path}")
            parse_result = self.pdf_parser.parse(file_path, document_id=None)
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
