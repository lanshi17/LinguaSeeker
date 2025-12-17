"""向量数据库实体 - 对应Milvus集合"""
from typing import List, Optional


class VectorDocument:
    """向量文档实体"""
    
    def __init__(
        self,
        vector_id: int,
        embedding: List[float],
        text_content: str,
        metadata: dict
    ):
        self.vector_id = vector_id
        self.embedding = embedding  # Float[1536] - nomic-embed-text或openai
        self.text_content = text_content  # 原始文本片段(Markdown格式，含表格)
        self.metadata = metadata  # {pmid, section_name, is_table: true/false}
    
    def get_pmid(self) -> Optional[str]:
        """获取PMID"""
        pass
    
    def is_table_content(self) -> bool:
        """判断是否为表格内容"""
        pass
