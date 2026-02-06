#!/usr/bin/env python3
"""
测试 Qdrant RAG 检索功能

用法:
    python scripts/test_rag_retrieval.py
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from component.agents import search_knowledge_base, get_qdrant_manager

def test_basic_search():
    """测试基础检索功能"""
    logger.info("=" * 60)
    logger.info("测试 1: 基础检索功能")
    logger.info("=" * 60)
    
    # 测试查询
    query = "What is PS3 evidence in ACMG guidelines?"
    logger.info(f"查询: {query}")
    
    try:
        results = search_knowledge_base(query, top_k=3)
        
        if not results:
            logger.warning("⚠ 没有检索到任何结果")
            return False
        
        logger.info(f"✓ 检索到 {len(results)} 个相关文档")
        
        for i, doc in enumerate(results):
            logger.info(f"\n--- 文档 {i+1} ---")
            logger.info(f"相似度: {doc['score']:.4f}")
            logger.info(f"文件路径: {doc.get('file_path', 'N/A')}")
            logger.info(f"内容预览: {doc['content'][:200]}...")
        
        return True
    except Exception as e:
        logger.error(f"✗ 检索失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_multiple_queries():
    """测试多个查询"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 2: 多查询检索")
    logger.info("=" * 60)
    
    queries = [
        "How to calculate OddsPath for PS3 evidence?",
        "What are the control requirements for functional assays?",
        "BS3 evidence strength criteria",
    ]
    
    all_success = True
    for query in queries:
        logger.info(f"\n查询: {query}")
        try:
            results = search_knowledge_base(query, top_k=2)
            if results:
                logger.info(f"✓ 检索到 {len(results)} 个结果")
                logger.info(f"  最高相似度: {results[0]['score']:.4f}")
            else:
                logger.warning("⚠ 没有检索到结果")
                all_success = False
        except Exception as e:
            logger.error(f"✗ 查询失败: {e}")
            all_success = False
    
    return all_success


def test_collection_status():
    """测试集合状态"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 3: 检查集合状态")
    logger.info("=" * 60)
    
    try:
        manager = get_qdrant_manager()
        
        # 健康检查
        if manager.health_check():
            logger.info("✓ Qdrant 服务健康")
        else:
            logger.warning("⚠ Qdrant 服务状态异常")
            return False
        
        # 集合信息
        collection_info = manager.get_collection_info()
        logger.info(f"集合名称: {manager.collection_name}")
        
        if hasattr(collection_info, 'vectors_count'):
            logger.info(f"向量数量: {collection_info.vectors_count}")
        
        if hasattr(collection_info, 'config'):
            logger.info(f"向量维度: {collection_info.config.params.vectors.size}")
            logger.info(f"距离度量: {collection_info.config.params.vectors.distance}")
        
        return True
    except Exception as e:
        logger.error(f"✗ 获取集合状态失败: {e}")
        return False


def test_similarity_threshold():
    """测试相似度阈值"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 4: 相似度阈值测试")
    logger.info("=" * 60)
    
    # 测试不相关查询
    irrelevant_query = "How to cook pasta?"
    logger.info(f"查询（不相关）: {irrelevant_query}")
    
    try:
        results = search_knowledge_base(irrelevant_query, top_k=5)
        
        if not results:
            logger.info("✓ 正确过滤了不相关查询（低于阈值）")
            return True
        else:
            logger.warning(f"⚠ 检索到 {len(results)} 个结果")
            logger.info(f"最高相似度: {results[0]['score']:.4f}")
            if results[0]['score'] < 0.5:
                logger.info("✓ 相似度较低，阈值工作正常")
                return True
            else:
                logger.warning("⚠ 可能需要调整相似度阈值")
                return False
    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        return False


def main():
    """主函数"""
    logger.info("\n" + "=" * 60)
    logger.info("Qdrant RAG 检索功能测试")
    logger.info("=" * 60)
    
    # 运行所有测试
    tests = [
        ("基础检索", test_basic_search),
        ("多查询检索", test_multiple_queries),
        ("集合状态", test_collection_status),
        ("相似度阈值", test_similarity_threshold),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            logger.error(f"测试异常: {test_name} - {e}")
            results.append((test_name, False))
    
    # 汇总结果
    logger.info("\n" + "=" * 60)
    logger.info("测试结果汇总")
    logger.info("=" * 60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        logger.info(f"{status}: {test_name}")
    
    logger.info("=" * 60)
    logger.info(f"通过: {passed}/{total}")
    
    if passed == total:
        logger.info("✓ 所有测试通过!")
        return 0
    else:
        logger.warning(f"⚠ {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
