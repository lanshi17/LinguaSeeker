import os
import pytest

if not os.getenv("RUN_QDRANT_TESTS"):
    pytest.skip("Set RUN_QDRANT_TESTS to enable Qdrant tests", allow_module_level=True)

from src.infrastructure.qdrant import QdrantManager
from pathlib import Path
import os
from icecream import ic
from loguru import logger
from datetime import datetime
from src.config import settings as cfg
from src.utils.timer import Timer
from typing import Optional
from pathlib import Path
from uuid import uuid4
import asyncio
from datetime import datetime

# 禁用代理 unset http_proxy https_proxy all_proxy
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ.pop("all_proxy", None)


async def ingest_knowledge_to_qdrant(
    folder_path: str, collect_name: str = cfg.qdrant_collection_name
) -> None:
    client = QdrantManager()
    # 测试连接
    health = await client.ping()
    if health.status != "ok":
        logger.error("无法连接到 Qdrant 服务，终止嵌入过程。")
        return
    # 获取客户端
    logger.info("连接到 Qdrant 服务成功。{}", client.get_client)
    # 获取集合信息
    collections = await client.client.get_collections()
    logger.info(
        f"当前 Qdrant 服务中的集合: {[col.name for col in collections.collections]}"
    )
    # 列出集合
    await client.list_collections()
    logger.debug("测试列出集合完成")
    client.collection_name = collect_name
    logger.info(f"使用的集合名称: {client.collection_name}")
    await client.create_collection_if_not_exists(collect_name)

    # 嵌入知识库
    logger.info(f"开始将知识库嵌入 Qdrant，文件夹路径: {folder_path}")
    await client.ingest_files(folder_path)
    logger.success("知识库嵌入 Qdrant 完成。")


@pytest.mark.anyio
async def test_ingest_knowledge_to_qdrant():
    # 创建一个临时文件夹并添加一些测试文件
    test_folder = Path("tests/unit/test_data")
    test_folder.mkdir(parents=True, exist_ok=True)
    test_file_1 = test_folder / "test1.txt"
    test_file_2 = test_folder / "test2.txt"
    test_file_1.write_text("This is a test file for Qdrant ingestion.")
    test_file_2.write_text("Another test file with different content.")

    try:
        # 调用函数进行知识库嵌入
        await ingest_knowledge_to_qdrant(str(test_folder), "test_collection")
    finally:
        # 清理测试文件夹
        for file in test_folder.iterdir():
            file.unlink()
        test_folder.rmdir()


@pytest.mark.anyio
async def test_ingest_knowledge_to_qdrant_invalid_path():
    # 提供一个不存在的文件夹路径
    invalid_folder = "non_existent_folder"

    # 调用函数进行知识库嵌入，预期不会抛出异常
    await ingest_knowledge_to_qdrant(invalid_folder, "test_collection")


@pytest.mark.unit
def test_delete_collection():
    qdrant_manager = QdrantManager()
    qdrant_manager.collection_name = "test_collection_to_delete"

    async def delete_and_check():
        # 先创建集合以确保它存在
        await qdrant_manager.create_collection_if_not_exists(
            qdrant_manager.collection_name
        )
        # 删除集合
        await qdrant_manager.delete_collection()
        # 检查集合是否已删除
        exists = await qdrant_manager.client.collection_exists(
            qdrant_manager.collection_name
        )
        assert not exists, "Collection should be deleted"

    import asyncio

    asyncio.run(delete_and_check())


@pytest.mark.unit
def test_create_collection_if_not_exists():
    qdrant_manager = QdrantManager()
    test_collection_name = "test_collection_creation"

    async def create_and_check():
        # 确保集合不存在
        await qdrant_manager.delete_collection()
        # 创建集合
        await qdrant_manager.create_collection_if_not_exists(test_collection_name)
        # 检查集合是否已创建
        exists = await qdrant_manager.client.collection_exists(test_collection_name)
        assert exists, "Collection should be created"

    import asyncio

    asyncio.run(create_and_check())


@pytest.mark.unit
def test_create_collection_if_already_exists():
    qdrant_manager = QdrantManager()
    test_collection_name = "test_collection_already_exists"

    async def create_existing_and_check():
        # 先创建集合
        await qdrant_manager.create_collection_if_not_exists(test_collection_name)
        # 再次调用创建函数，应该不会抛出异常
        await qdrant_manager.create_collection_if_not_exists(test_collection_name)
        # 检查集合是否仍然存在
        exists = await qdrant_manager.client.collection_exists(test_collection_name)
        assert exists, "Collection should still exist"

    import asyncio

    asyncio.run(create_existing_and_check())


@pytest.mark.unit
def test_reset_collection():
    qdrant_manager = QdrantManager()
    test_collection_name = "test_collection_reset"

    async def reset_and_check():
        # 创建集合
        await qdrant_manager.create_collection_if_not_exists(test_collection_name)
        # 重置集合
        await qdrant_manager.reset_collection()
        # 检查集合是否仍然存在
        exists = await qdrant_manager.client.collection_exists(test_collection_name)
        assert exists, "Collection should exist after reset"

    import asyncio

    asyncio.run(reset_and_check())


@pytest.mark.unit
def test_get_client():
    qdrant_manager = QdrantManager()
    client = qdrant_manager.get_client
    assert client is not None, "Qdrant client should not be None"


@pytest.mark.unit
def test_get_collection_name():
    qdrant_manager = QdrantManager()
    collection_name = qdrant_manager.collection_name
    assert collection_name == cfg.qdrant_collection_name, (
        "Collection name should match config"
    )


@pytest.mark.unit
def test_get_list_collections():
    qdrant_manager = QdrantManager()

    async def list_and_check():
        collections = await qdrant_manager.list_collections()
        assert isinstance(collections, list), "Collections should be a list"

    import asyncio

    asyncio.run(list_and_check())


# 测试获取集合中的内容
@pytest.mark.unit
def test_get_collection_info():
    qdrant_manager = QdrantManager()

    async def info_and_check():
        await qdrant_manager.create_collection_if_not_exists(
            qdrant_manager.collection_name
        )
        info = await qdrant_manager.get_collection_info()
        assert info is not None, "Collection info should not be None"

    import asyncio

    asyncio.run(info_and_check())


@pytest.mark.anyio
async def test_search_qdrant():
    qdrant_manager = QdrantManager()
    await qdrant_manager.create_collection_if_not_exists(qdrant_manager.collection_name)

    # 假设已经有一些数据被嵌入到集合中
    query_vector = [0.0] * cfg.embedding_dimension  # 使用一个零向量作为查询向量

    search_response = await qdrant_manager.search(
        query_vector=query_vector,
        top_k=3,
        score_threshold=0.5,
    )
    ic(search_response)
    logger.debug("Search response: {}", search_response)
    assert search_response is not None, "Search response should not be None"
    assert hasattr(search_response, "results"), (
        "Search response should have results attribute"
    )
    assert isinstance(search_response.results, list), "Search results should be a list"


if __name__ == "__main__":
    timer = Timer("All tests completed in {elapsed:.2f} seconds.")
    timer.start()
    t1 = test_ingest_knowledge_to_qdrant()
    t2 = test_ingest_knowledge_to_qdrant_invalid_path()
    test_delete_collection()
    test_create_collection_if_not_exists()
    test_create_collection_if_already_exists()
    test_reset_collection()
    test_get_client()
    test_get_collection_name()
    test_get_list_collections()
    test_get_collection_info()
    t3 = test_search_qdrant()
    logger.success("All tests completed.")
    timer.stop()
