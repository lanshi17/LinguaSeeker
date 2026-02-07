from pathlib import Path
import sys
import os

# Ensure the project root (which contains the `src` package) is importable when this file
# is invoked directly with `python src/pipline.py`.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger
import requests
from component.mineru import MinerUComponent
from component.agents import EvidenceAgent
from component.models import MinerURequest
from database.qdrant import QdrantManager,initialize_knowledge_base
from utils.timer import Timer, timer
import utils.exceptions as exc
import utils.file_utils as file_utils
from typing import Any
from uuid import uuid4
from datetime import datetime
from config import settings


def add_logger_sink(**kwargs):
    """Prefer async logging but gracefully fall back if the runtime forbids semaphores."""
    try:
        return logger.add(enqueue=True, **kwargs)
    except PermissionError:
        logger.warning("Unable to enable async logging for sink %s; falling back to synchronous mode", kwargs.get("sink"))
        return logger.add(enqueue=False, **kwargs)
cfg=settings
#禁用任何代理 unset http_proxy https_proxy all_proxy  
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ.pop("all_proxy", None)
add_logger_sink(
    sink=f"logs/app_{datetime.now().strftime('%Y%m%d')}.log", # 文件名包含日期
    level="INFO", # 记录 INFO 及以上级别的日志到文件
    rotation="00:00", # 每天午夜滚动
    retention="7 days", # 保留最近7天的日志文件
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} - {message}",
    compression="zip", # 可选：对旧日志进行压缩
    serialize=False # 默认为 False，如果为 True，整个日志记录会被序列化成 JSON
)

# 添加一个 sink 到标准错误输出 (stderr)，通常是你的终端
# 你可以根据需要设置不同的 level，例如 DEBUG
add_logger_sink(
    sink=sys.stderr,
    level="DEBUG", # 记录 DEBUG 及以上级别的日志到控制台
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    colorize=True, # 启用颜色，使终端日志更易读
    backtrace=True, # 记录完整的回溯信息
    diagnose=True, # 提供更详细的错误上下文 (在生产环境中可能需要关闭以保护敏感信息)
)

mineru=MinerUComponent()
agents=EvidenceAgent()
qdrant_manager=QdrantManager()

#先检查qdrant 是否包含知识库内容,没有则初始化
import asyncio
@Timer("初始化知识库")
async def init():
    try:
        if not qdrant_manager.check_collection_exists(cfg.qdrant_collection_name):
            logger.info(f"向量数据库中未找到集合 {cfg.qdrant_collection_name}，正在初始化知识库...")
            await initialize_knowledge_base(cfg.knowledge_docs_dir)
        else:
            logger.info(f"向量数据库中已存在集合 {cfg.qdrant_collection_name}，跳过初始化。")
    except exc.VectorDBConnectionError as e:
        logger.error(f"连接向量数据库失败: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"初始化知识库时发生错误: {e}")
        sys.exit(1)
    
    asyncio.run(init())

#使用./demo_pdf/test_fr01.pdf 进行集成调试
mineru_request=MinerURequest(
    file_paths=[str(Path.cwd() / "demo_pdf" / "test_fr01.pdf")],
)
mineru_response=mineru.minerU_pipeline(mineru_request)
if not isinstance(mineru_response, str):
    logger.error("未能生成md文件")
    sys.exit(1)
logger.debug("解析测试完成:{}", mineru_response)
origin_folder=file_utils.get_all_files_in_directory(mineru_response.folder_path)
origin_md_content=origin_folder.get(str(Path(mineru_response.folder_path) / "full.md"), "")
logger.debug("解析的Markdown内容预览:{}", origin_md_content[:500])
origin_image_paths=[str(p) for p in Path(mineru_response.folder_path).rglob("*.jpg") if p.is_file()]
logger.debug("解析的图片路径列表:{}", origin_image_paths)
agent_request={
    "markdown_content":origin_md_content,
    "image_paths":origin_image_paths,
}
agent_response=agents.process_medical_evidence(**agent_request)
if not hasattr(agent_response, "ps3_evidence"):
    logger.error("未能生成医学证据处理结果")
    sys.exit(1)
logger.debug("医学证据处理测试完成:{}", agent_response)
#保存结果
""" 
    ps3_evidence: Dict[str, Any] = Field(..., description="PS3 证据评估结果")
    arbitration_score: float = Field(..., description="仲裁评分 (0-100)")
    middleware_md: str = Field(..., description="处理后的中间 英文 Markdown 文档")
    image_descriptions: List[str] = Field(default_factory=list, description="图片描述列表")
    final_evidence_strength: Optional[str] = Field(None, description="最终证据强度等级")
    status: Optional[str] = Field("pending", description="处理状态")
    origin_format_md: Optional[str] = Field(None, description="原始格式的 排版后的Markdown 内容")
    en_format_md: Optional[str] = Field(None, description="翻译成英文的排版后的Markdown 内容")
"""
output_dir=Path.cwd() / "demo_output" / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
file_utils.ensure_directory_exists(str(output_dir))
#保存原始Markdown
origin_md_path=output_dir / "original_format.md"
with open(origin_md_path, 'w', encoding='utf-8') as f:
    f.write(agent_response.origin_format_md or "")
logger.debug("已保存原始格式Markdown到:{}", origin_md_path)
#保存翻译后Markdown
en_md_path=output_dir / "translated_format.md"
with open(en_md_path, 'w', encoding='utf-8') as f:
    f.write(agent_response.en_format_md or "")
logger.debug("已保存翻译后Markdown到:{}", en_md_path)
#保存中间处理Markdown
middleware_md_path=output_dir / "middleware_english.md"
with open(middleware_md_path, 'w', encoding='utf-8') as f:
    f.write(agent_response.middleware_md or "")
logger.debug("已保存中间处理Markdown到:{}", middleware_md_path)
#保存图片描述
image_desc_path=output_dir / "image_descriptions.txt"
with open(image_desc_path, 'w', encoding='utf-8') as f:
    for desc in agent_response.image_descriptions:
        f.write(desc + "\n")
logger.debug("已保存图片描述到:{}", image_desc_path)
#保存PS3证据评估结果
ps3_evidence_path=output_dir / "ps3_evidence.json"
import json
with open(ps3_evidence_path, 'w', encoding='utf-8') as f:
    json.dump(agent_response.ps3_evidence, f, ensure_ascii=False, indent=4)
logger.debug("已保存PS3证据评估结果到:{}", ps3_evidence_path)
logger.success("集成测试全部完成，结果保存在目录:{}", output_dir)
# if __name__ == "__main__":
#     import os
#     #禁用代理 unset http_proxy https_proxy all_proxy  
#     os.environ.pop("http_proxy", None)
#     os.environ.pop("https_proxy", None)
#     os.environ.pop("all_proxy", None)    
#     # #batch test
#     # #文件夹
#     # folder_path = os.getcwd() + "/demo_pdf/"
#     # #获取文件列表
#     # files = file_utils.get_all_files_in_directory(folder_path)
#     # minerU(files)
#     #测试单个文件
#     file_path=Path(os.getcwd() + "/demo_pdf/test_de01.pdf")
#     md_file_path=minerU([str(file_path)])
#     if not isinstance(md_file_path, str):
#         logger.error("未能生成md文件")
#         sys.exit(1)
#     logger.debug("上传测试完成")
#     logger.success("解析文件完成")
