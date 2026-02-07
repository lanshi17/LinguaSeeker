#!/usr/bin/env python3
"""
初始化 Qdrant 知识库脚本

用法:
    python scripts/init_knowledge_base.py [--reset]
    
参数:
    --reset: 重置现有集合（删除并重新创建）
"""

import sys
import os
import asyncio
from pathlib import Path
# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from src.database.qdrant_client import QdrantManager
from src.config import settings as cfg

async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="初始化 Qdrant 知识库")
    parser.add_argument("--reset", action="store_true", help="重置现有集合")
    parser.add_argument("--docs-dir", type=str, default="knowledge_docs", 
                        help="知识文档目录路径")
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("开始初始化 Qdrant 知识库")
    logger.info("=" * 60)
    
    # 1. 检查配置
    logger.info(f"Qdrant 服务: {cfg.qdrant_host}:{cfg.qdrant_port}")
    logger.info(f"集合名称: {cfg.qdrant_collection_name}")
    logger.info(f"向量维度: {cfg.qdrant_dimension}")
    logger.info(f"Embedding 模型: {cfg.embedding_model}")
    
    # 2. 创建管理器
    try:
        manager = QdrantManager()
        logger.info("✓ Qdrant 管理器创建成功")
    except Exception as e:
        logger.error(f"✗ 创建 Qdrant 管理器失败: {e}")
        return 1
    
    # 3. 健康检查
    health = await manager.ping()
    if health.status != "ok":
        logger.error("✗ Qdrant 服务连接失败，请检查服务是否启动")
        logger.info("提示: 使用 Docker 启动 Qdrant:")
        logger.info("  docker run -p 6333:6333 -p 6334:6334 -v $(pwd)/qdrant_storage:/qdrant/storage qdrant/qdrant")
        return 1
    logger.info("✓ Qdrant 服务连接成功")
    
    # QdrantManager does not expose a health_check method; ping is sufficient.
    
    # 4. 创建或重置集合
    try:
        if args.reset:
            logger.warning("正在重置集合...")
            await manager.reset_collection()
            logger.info("✓ 集合重置成功")
        else:
            await manager.create_collection_if_not_exists()
            logger.info("✓ 集合创建/检查成功")
    except Exception as e:
        logger.error(f"✗ 集合操作失败: {e}")
        return 1
    
    # 5. 检查知识文档目录
    docs_dir = Path(args.docs_dir)
    if not docs_dir.exists():
        logger.error(f"✗ 知识文档目录不存在: {docs_dir}")
        logger.info(f"请创建目录并添加知识文档: mkdir -p {docs_dir}")
        return 1
    
    # 检查文档数量
    doc_files = list(docs_dir.glob("**/*.md")) + list(docs_dir.glob("**/*.txt"))
    if not doc_files:
        logger.warning(f"⚠ 知识文档目录为空: {docs_dir}")
        logger.info("请添加知识文档到该目录")
        return 0
    
    logger.info(f"发现 {len(doc_files)} 个文档文件")
    for doc_file in doc_files[:5]:  # 显示前 5 个
        logger.info(f"  - {doc_file.name}")
    if len(doc_files) > 5:
        logger.info(f"  ... 共 {len(doc_files)} 个文件")
    
    # 6. 导入文档
    try:
        logger.info("开始导入文档到 Qdrant...")
        await manager.ingest_files(str(docs_dir))
        logger.info("✓ 文档导入成功")
    except Exception as e:
        logger.error(f"✗ 文档导入失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1
    
    # 7. 验证导入结果
    try:
        collection_info = await manager.get_collection_info()
        logger.info(f"✓ 集合中的向量数量: {collection_info.vectors_count}")
    except Exception as e:
        logger.warning(f"⚠ 无法获取集合信息: {e}")
    
    logger.info("=" * 60)
    logger.info("✓ 知识库初始化完成!")
    logger.info("=" * 60)
    logger.info("")

    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
