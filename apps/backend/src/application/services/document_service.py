# 编排文件处理流程
from domain.__init__ import DocumentParser, PDFParser
from infrastructure.adapters.mineru import MinerUImpl
from infrastructure.store.minio_store import MinIOStore
from config.database_config import DatabaseConfig
from utils.logger import Logger
from application.dtos.document_dto import DocumentDTO
from typing import Any, Dict, Optional
import os
from datetime import datetime, timezone
import uuid

class DocumentService:
    """文档服务类，负责处理文档相关的业务逻辑"""

    def __init__(self, db_config: Optional[DatabaseConfig] = None):
        self.logger = Logger.get_logger("DocumentService")
        self.mineru_adapter = MinerUImpl()
        self.pdf_parser: DocumentParser = PDFParser(self.mineru_adapter)

        # 初始化MinIO存储
        if db_config is None:
            db_config = DatabaseConfig.from_env()
        self.minio_store = MinIOStore(db_config)

        self.logger.info("DocumentService initialized with MinIO storage")

    def process_pdf_document(self, document: DocumentDTO) -> Dict[str, Any]:
        """处理PDF文档(使用MinerU)并将结果存储到MinIO

        Args:
            document: DocumentDTO对象,包含文档内容和临时文件路径

        Returns:
            包含document_id、minio_prefix和文件列表的字典
        """
        try:
            if not document.temp_file_path or not os.path.exists(document.temp_file_path):
                raise ValueError("Temporary file path is required and must exist")

            self.logger.info(f"Processing PDF document: {document.filename}")

            # 生成唯一的document ID
            document_id = str(uuid.uuid4())

            # 提取文件名(不带扩展名)用于MinIO路径
            file_basename = os.path.splitext(document.filename)[0]

            # 调用领域层的PDF解析器(使用MinerU)
            parse_result = self.pdf_parser.parse_with_mineru(
                document.temp_file_path,
                document_id=document_id
            )

            # 构建MinIO对象前缀: documents/{filename}/{uuid}
            minio_prefix = f"documents/{file_basename}/{document_id}"

            # 下载MinerU返回的ZIP并解压上传到MinIO
            full_zip_url = parse_result.get("full_zip_url")
            if not full_zip_url:
                raise ValueError("MinerU did not return a ZIP URL")

            uploaded_files = self.minio_store.download_and_extract_zip(
                full_zip_url,
                minio_prefix
            )

            result = {
                "document_id": document_id,
                "file_name": document.filename,
                "minio_prefix": minio_prefix,
                "minio_files": uploaded_files,
                "file_count": len(uploaded_files),
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "mineru_file_id": parse_result.get("file_id")
            }

            self.logger.info(f"PDF document processed successfully. {len(uploaded_files)} files stored in MinIO")
            return result

        except Exception as e:
            self.logger.error(f"Error processing PDF document: {e}")
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
            self.logger.info(f"Processing PDF file: {file_path}")
            html_content = self.pdf_parser.parse(file_path)
            if not self.pdf_parser.validate(html_content):
                raise ValueError("Parsed content is not valid HTML")

            result = {
                "html_content": html_content,
                "file_name": os.path.basename(file_path),
                "processed_at": datetime.now(timezone.utc).isoformat()
            }

            # 如果需要，存储到MinIO
            if store_in_minio:
                if object_prefix is None:
                    # 使用文件名（不带扩展名）作为默认前缀
                    object_prefix = os.path.splitext(os.path.basename(file_path))[0]

                # 生成MinIO对象名称
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                object_name = f"documents/{object_prefix}/{timestamp}/result.html"

                # 保存HTML内容到MinIO
                self.minio_store.save(html_content.encode('utf-8'), object_name)
                result["minio_path"] = object_name
                self.logger.info(f"Stored HTML content in MinIO: {object_name}")

            self.logger.info("PDF file processed successfully")
            return result

        except Exception as e:
            self.logger.error(f"Error processing PDF file: {e}")
            raise

    def process_pdf_with_mineru(self, file_path: str, store_results: bool = True) -> Dict[str, Any]:
        """使用MinerU处理PDF文件并存储结果到MinIO

        Args:
            file_path: PDF文件路径
            store_results: 是否将MinerU返回的ZIP结果存储到MinIO

        Returns:
            处理结果字典，包含MinIO中的文件列表
        """
        try:
            self.logger.info(f"Processing PDF with MinerU: {file_path}")

            # 1. 申请上传URL
            upload_response = self.mineru_adapter.apply_upload_urls([file_path])
            file_id = upload_response.get("files", [])[0].get("file_id")

            # 2. 上传文件
            upload_url = upload_response.get("files", [])[0].get("upload_url")
            self.mineru_adapter.upload_to_urls([file_path], [upload_url])

            # 3. 等待处理完成并获取结果
            self.logger.info("Waiting for MinerU processing to complete...")
            status = self.mineru_adapter.get_processing_status(file_id)

            # 4. 检索结果
            result = self.mineru_adapter.retrieve_results(file_id)
            extract_result = result.get("extract_result", {})

            result_data = {
                "file_id": file_id,
                "file_name": os.path.basename(file_path),
                "status": extract_result.get("state"),
                "processed_at": datetime.now(timezone.utc).isoformat()
            }

            # 5. 如果处理完成且需要存储，下载ZIP并上传到MinIO
            if extract_result.get("state") == "completed" and store_results:
                full_zip_url = extract_result.get("full_zip_url")
                if full_zip_url:
                    # 生成MinIO对象名称前缀
                    file_basename = os.path.splitext(os.path.basename(file_path))[0]
                    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                    object_prefix = f"mineru_results/{file_basename}/{timestamp}"

                    # 下载并解压到MinIO
                    uploaded_files = self.minio_store.download_and_extract_zip(
                        full_zip_url,
                        object_prefix
                    )

                    result_data["minio_files"] = uploaded_files
                    result_data["minio_prefix"] = object_prefix
                    self.logger.info(f"Stored {len(uploaded_files)} files in MinIO under {object_prefix}")

            return result_data

        except Exception as e:
            self.logger.error(f"Error processing PDF with MinerU: {e}")
            raise