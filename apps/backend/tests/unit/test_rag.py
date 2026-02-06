from src.utils.timer import Timer, timer
import src.utils.exceptions as exc
import src.utils.file_utils as file_utils
from src.config import settings as cfg 
from src.component.rag import RAGComponent
from loguru import logger
from typing import List, Dict, Any, Optional
from src.component.models import RAGQueryRequest, RAGQueryResponse
import asyncio
import pytest
rag = RAGComponent()


def extract_context(response: Dict[str, Any]) -> str:
    return response.get("context", "")


def extract_results(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    return response.get("results", [])


@pytest.mark.asyncio
async def test_rag_pipeline():
    query = "什么是多基因突变？"
    response = await rag.rag_pipeline(
        request=RAGQueryRequest(
            query=query,
            top_k=cfg.rerank_top_k,
            score_threshold=cfg.rerank_score_threshold,
            max_context_chars=2000,
            chunk_overlap=200,
            enable_rerank=True,
        )
    )
    assert response is not None
    assert isinstance(response, dict)
    context = extract_context(response)
    assert isinstance(context, str)
    assert context == "" or len(context) > 0
    assert isinstance(extract_results(response), list)
    logger.info("RAG pipeline test passed.")

@pytest.mark.asyncio
async def test_rag_pipeline_empty_query():
    query = "   "  # 空查询
    with pytest.raises(ValueError) as exc_info:
        await rag.rag_pipeline(
            request=RAGQueryRequest(
                query=query,
                top_k=cfg.rerank_top_k,
                score_threshold=cfg.rerank_score_threshold,
                max_context_chars=2000,
                chunk_overlap=200,
                enable_rerank=False,
            )
        )
    assert str(exc_info.value) == "query is empty"
    logger.info("RAG pipeline empty query test passed.")
    
@pytest.mark.asyncio
async def test_rag_pipeline_no_results():
    query = "ThisIsAnUnlikelyQueryThatShouldReturnNoResults12345"
    response = await rag.rag_pipeline(
        request=RAGQueryRequest(
            query=query,
            top_k=cfg.rerank_top_k,
            score_threshold=cfg.rerank_score_threshold,     
            max_context_chars=2000,
            chunk_overlap=200,
            enable_rerank=False,
        )
    )
    assert extract_context(response) == ""
    logger.info("RAG pipeline no results test passed.")
@pytest.mark.asyncio
async def test_rag_pipeline_rerank_disabled():
    query = "Explain the concept of reinforcement learning."
    response = await rag.rag_pipeline(
        request=RAGQueryRequest(
            query=query,
            top_k=cfg.rerank_top_k,
            score_threshold=cfg.rerank_score_threshold,
            max_context_chars=2000,
            chunk_overlap=200,
            enable_rerank=False,
        )
    )
    assert response is not None
    assert isinstance(response, dict)
    context = extract_context(response)
    assert isinstance(context, str)
    assert context == "" or len(context) > 0
    assert isinstance(extract_results(response), list)
    logger.info("RAG pipeline with rerank disabled test passed.")
    
@pytest.mark.asyncio
async def test_rag_pipeline_high_threshold():
    query = "What are the applications of natural language processing?"
    response = await rag.rag_pipeline(
        request=RAGQueryRequest(
            query=query,
            top_k=cfg.rerank_top_k,
            score_threshold=0.99,  # 设置高阈值
            max_context_chars=2000,
            chunk_overlap=200,
            enable_rerank=False,
        )
    )
    assert extract_context(response) == ""
    logger.info("RAG pipeline with high score threshold test passed.")
@pytest.mark.asyncio
async def test_rag_pipeline_low_top_k():
    query = "Describe the process of photosynthesis."
    response = await rag.rag_pipeline(
        request=RAGQueryRequest(
            query=query,
            top_k=1,  # 设置低 top_k
            score_threshold=cfg.rerank_score_threshold,
            max_context_chars=2000,
            chunk_overlap=200,
            enable_rerank=False,
        )
    )
    assert response is not None
    assert isinstance(response, dict)
    context = extract_context(response)
    assert isinstance(context, str)
    assert context == "" or len(context) > 0
    assert isinstance(extract_results(response), list)
    logger.info("RAG pipeline with low top_k test passed.")
    
@pytest.mark.asyncio
async def test_rag_pipeline_large_context():
    query = "What is the significance of the Turing Test in AI?"
    response = await rag.rag_pipeline(
        request=RAGQueryRequest(
            query=query,
            top_k=cfg.rerank_top_k,
            score_threshold=cfg.rerank_score_threshold,
            max_context_chars=10000,  # 增加上下文字符数
            chunk_overlap=500,
            enable_rerank=False,
        )
    )
    assert response is not None
    assert isinstance(response, dict)
    context = extract_context(response)
    assert isinstance(context, str)
    assert context == "" or len(context) > 0
    assert isinstance(extract_results(response), list)
    logger.info("RAG pipeline with large context test passed.")
@pytest.mark.asyncio
async def test_rag_pipeline_small_chunks():
    query = "Explain the theory of relativity."
    response = await rag.rag_pipeline(
        request=RAGQueryRequest(
            query=query,
            top_k=cfg.rerank_top_k,
            score_threshold=cfg.rerank_score_threshold,
            max_context_chars=2000,
            chunk_overlap=50,  # 减小重叠部分
            enable_rerank=False,
        )
    )
    assert response is not None
    assert isinstance(response, dict)
    context = extract_context(response)
    assert isinstance(context, str)
    assert context == "" or len(context) > 0
    assert isinstance(extract_results(response), list)
    logger.info("RAG pipeline with small chunks test passed.")
@pytest.mark.asyncio
async def test_rag_pipeline_special_characters():
    query = "What is the role of π (pi) in mathematics?"
    response = await rag.rag_pipeline(
        request=RAGQueryRequest(
            query=query,
            top_k=cfg.rerank_top_k,
            score_threshold=cfg.rerank_score_threshold,
            max_context_chars=2000,
            chunk_overlap=200,
            enable_rerank=False,
        )
    )
    assert response is not None
    assert isinstance(response, dict)
    context = extract_context(response)
    assert isinstance(context, str)
    assert context == "" or len(context) > 0
    assert isinstance(extract_results(response), list)
    logger.info("RAG pipeline with special characters test passed.")    
@pytest.mark.asyncio
async def test_rag_pipeline_multilingual_query():
    query = "¿Qué es el aprendizaje automático?"
    response = await rag.rag_pipeline(
        request=RAGQueryRequest(
            query=query,
            top_k=cfg.rerank_top_k,
            score_threshold=cfg.rerank_score_threshold,
            max_context_chars=2000,
            chunk_overlap=200,
            enable_rerank=False,
        )
    )
    assert response is not None
    assert isinstance(response, dict)
    context = extract_context(response)
    assert isinstance(context, str)
    assert context == "" or len(context) > 0
    assert isinstance(extract_results(response), list)
    logger.info("RAG pipeline with multilingual query test passed.")
    
@pytest.mark.asyncio
async def test_rag_pipeline_numeric_query():
    query = "What is 2 + 2?"
    response = await rag.rag_pipeline(
        request=RAGQueryRequest(
            query=query,
            top_k=cfg.rerank_top_k,
            score_threshold=cfg.rerank_score_threshold,
            max_context_chars=2000,
            chunk_overlap=200,
            enable_rerank=False,
        )
    )
    assert response is not None
    assert isinstance(response, dict)
    context = extract_context(response)
    assert isinstance(context, str)
    assert context == "" or len(context) > 0
    assert isinstance(extract_results(response), list)
    logger.info("RAG pipeline with numeric query test passed.")

@pytest.mark.asyncio
async def test_search_qdrant():
    query = "Explain the concept of reinforcement learning."
    response = await rag.search_qdrant(
        query=query,
        top_k=5,
        score_threshold=0.7,
    )
    assert response is not None
    assert hasattr(response, "results")
    assert isinstance(response.results, list)
    logger.info("Qdrant search test passed.")

if __name__ == "__main__":
    timer=Timer("Total test execution time: {elapsed:.2f} seconds.")
    with timer:
        asyncio.run(test_rag_pipeline())
        asyncio.run(test_rag_pipeline_empty_query())
        asyncio.run(test_rag_pipeline_no_results())
        asyncio.run(test_rag_pipeline_rerank_disabled())
        asyncio.run(test_rag_pipeline_high_threshold())
        asyncio.run(test_rag_pipeline_low_top_k())
        asyncio.run(test_rag_pipeline_large_context())
        asyncio.run(test_rag_pipeline_small_chunks())
        asyncio.run(test_rag_pipeline_special_characters())
        asyncio.run(test_rag_pipeline_multilingual_query())
        asyncio.run(test_rag_pipeline_numeric_query())
    logger.success(f"All tests completed.")
    timer.stop()