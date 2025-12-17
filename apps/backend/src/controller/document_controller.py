"""文档上传和解析相关API"""
from typing import Dict, Any


class DocumentController:
    """文档管理控制器
    
    处理PDF上传、文献导入等操作
    """
    
    def __init__(self, parser_service):
        self.parser_service = parser_service
    
    async def upload_pdf(self, file_data: bytes, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """POST /api/documents/upload - 上传PDF文档
        
        Request:
        - Content-Type: multipart/form-data
        - file: PDF文件
        - user_id: UUID
        - filename: string
        
        Response:
        {
            "task_id": "uuid",
            "status": "Parsing",
            "message": "PDF uploaded and parsing started"
        }
        """
        # TODO: 验证文件格式
        # TODO: 调用parser_service上传和解析
        # TODO: 返回任务ID
        pass
    
    async def import_from_pubmed(self, pmid: str, user_id: str) -> Dict[str, Any]:
        """POST /api/documents/import/pubmed - 从PubMed导入文献
        
        Request Body:
        {
            "pmid": "12345678",
            "user_id": "uuid"
        }
        
        Response:
        {
            "task_id": "uuid",
            "pmid": "12345678",
            "status": "Parsing"
        }
        """
        # TODO: 从PubMed获取文献
        # TODO: 创建解析任务
        pass
    
    async def get_parsing_status(self, task_id: str) -> Dict[str, Any]:
        """GET /api/documents/parsing/{task_id} - 获取解析状态
        
        Response:
        {
            "task_id": "uuid",
            "status": "Parsing | Graph_Building | Completed",
            "progress": 50,
            "chunks_created": 120
        }
        """
        # TODO: 查询解析进度
        pass
