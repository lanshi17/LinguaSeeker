"""文档控制器 - 占位符实现"""

import logging

logger = logging.getLogger(__name__)


class DocumentController:
    """文档控制器 - 占位符实现"""

    def __init__(self, service=None):
        self.service = service
        self.logger = logging.getLogger(self.__class__.__name__)

    async def upload_pdf(self, file_data: bytes, metadata: dict) -> dict:
        """上传PDF文档 - 占位符实现"""
        self.logger.info("文档上传功能被调用（占位符）")
        return {
            "success": True,
            "data": {
                "message": "文档上传功能暂未完全实现",
                "action": "upload_pdf",
                "file_size": len(file_data) if file_data else 0,
            },
        }

    async def import_from_pubmed(self, pmid: str, user_id: str) -> dict:
        """从PubMed导入文献 - 占位符实现"""
        self.logger.info(f"PubMed导入功能被调用（占位符）: {pmid}")
        return {
            "success": True,
            "data": {
                "message": "PubMed导入功能暂未实现",
                "pmid": pmid,
                "user_id": user_id,
            },
        }

    async def get_parsing_status(self, task_id: str) -> dict:
        """获取解析状态 - 占位符实现"""
        self.logger.info(f"解析状态查询功能被调用（占位符）: {task_id}")
        return {
            "success": True,
            "data": {
                "message": "解析状态查询功能暂未实现",
                "task_id": task_id,
                "status": "unknown",
            },
        }
