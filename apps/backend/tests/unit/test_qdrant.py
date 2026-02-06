import pytest
from src.pipline import ingest_knowledge_to_qdrant
from pathlib import Path
from loguru import logger
from src.utils import file_utils
from typing import List, Dict, Any, Optional
import sys

def test_ingest_knowledge_to_qdrant():
    # 创建一个临时文件夹并添加一些测试文件
    test_folder = Path("tests/unit/test_data")
    test_folder.mkdir(parents=True, exist_ok=True)
    test_file_1 = test_folder / "test1.txt"
    test_file_2 = test_folder / "test2.txt"
    test_file_1.write_text("This is a test file for Qdrant ingestion.")
    test_file_2.write_text("Another test file with different content.")

    try:
        # 调用函数进行知识库嵌入
        ingest_knowledge_to_qdrant(str(test_folder))

        # 这里可以添加更多断言来验证数据是否正确插入到 Qdrant 中
        # 例如，查询 Qdrant 并检查向量是否存在
        # 由于这是一个集成测试，具体实现取决于 Qdrant 的查询接口

    finally:
        # 清理测试文件夹
        for file in test_folder.iterdir():
            file.unlink()
        test_folder.rmdir()