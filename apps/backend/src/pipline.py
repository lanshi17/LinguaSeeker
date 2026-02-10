from pathlib import Path
import sys
import os
from loguru import logger
# Ensure the project root (which contains the `src` package) is importable when this file
# is invoked directly with `python src/pipline.py`.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger
import requests
from domain.mineru.component import MinerUComponent
from domain.agent.workflow import EvidenceAgent
from domain.models import MinerURequest, MinerUResponse, EvidenceOutput
from src.database.qdrant_client import QdrantManager,initialize_knowledge_base
from src.utils.timer import Timer, timer
import src.utils.exceptions as exc
import src.utils.file_utils as file_utils
from typing import Any, List
from uuid import uuid4
from datetime import datetime
from src.config import settings
timer=Timer("整体流程运行时间")
timer.start()
cfg = settings
#禁用任何代理 unset http_proxy https_proxy all_proxy  
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ.pop("all_proxy", None)
logger.add(
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
logger.add(
    sink=sys.stderr,
    level="DEBUG", # 记录 DEBUG 及以上级别的日志到控制台
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    colorize=True, # 启用颜色，使终端日志更易读
    backtrace=True, # 记录完整的回溯信息
    diagnose=False, # 提供更详细的错误上下文 (在生产环境中可能需要关闭以保护敏感信息)
)


mineru=MinerUComponent()
agents=EvidenceAgent()
qdrant_manager=QdrantManager()

#先检查qdrant 是否包含知识库内容,没有则初始化
import asyncio
@Timer("初始化知识库")
async def init_knowledge_base_if_needed() -> bool:
    try:
        exists = await qdrant_manager.check_collection_exists(cfg.qdrant_collection_name)
    except Exception as e:
        logger.warning(f"无法连接向量数据库，跳过知识库初始化: {e}")
        return False

    if not exists:
        logger.info(f"向量数据库中未找到集合 {cfg.qdrant_collection_name}，尝试初始化知识库...")
        try:
            await initialize_knowledge_base(cfg.knowledge_docs_dir)
        except Exception as e:
            logger.warning(f"初始化知识库失败，继续离线流程: {e}")
            return False
    else:
        logger.info(f"向量数据库中已存在集合 {cfg.qdrant_collection_name}，跳过初始化。")
    return True

try:
    asyncio.run(init_knowledge_base_if_needed())
except Exception as e:
    logger.exception(f"知识库初始化过程中捕获异常，继续执行: {e}")

#使用./demo_pdf/test_en01.pdf 进行集成调试
mineru_request=MinerURequest(
    file_paths=[str(Path.cwd() / "demo_pdf" / "test_en01.pdf")],
)
try:
    mineru_response=mineru.minerU_pipeline(mineru_request)
except Exception as e:
    logger.exception(f"调用 MinerU 解析失败，将启用离线mock: {e}")

if not mineru_response or not getattr(mineru_response, "folder_path", None):
    logger.error("未能生成md文件，使用本地mock数据继续流程")

logger.debug("解析测试完成，结果目录: {}", mineru_response.folder_path)
origin_folder=file_utils.get_all_files_in_directory(mineru_response.folder_path)
origin_md_content=origin_folder.get(str(Path(mineru_response.folder_path) / "full.md"), "")
logger.debug("解析的Markdown内容预览:{}", origin_md_content[:100])
origin_image_paths=[str(p) for p in Path(mineru_response.folder_path).rglob("*.jpg") if p.is_file()]
logger.debug("解析的图片路径列表:{}", origin_image_paths)
agent_request={
    "markdown_content":origin_md_content,
    "image_paths":origin_image_paths,
}
try:
    agent_response=agents.process_medical_evidence(**agent_request)
except Exception as e:
    logger.exception(f"医学证据处理失败: {e}")


if getattr(agent_response, "status", None) == "failed":
    logger.error("医学证据处理失败，停止后续保存流程")
    raise SystemExit(1)

logger.debug("医学证据处理测试完成:{}", agent_response)
#保存结果
""" 
    ps3_evidence: Dict[str, Any] = Field(..., description="PS3 证据评估结果")
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
en_md_path=output_dir / "en_format.md"
with open(en_md_path, 'w', encoding='utf-8') as f:
    f.write(agent_response.en_format_md or "")
logger.debug("已保存翻译后Markdown到:{}", en_md_path)
#保存图片描述
image_desc_path=output_dir / "image_descriptions.txt"
with open(image_desc_path, 'w', encoding='utf-8') as f:
    for desc in agent_response.image_descriptions:
        f.write(desc + "\n")
logger.debug("已保存图片描述到:{}", image_desc_path)
#复制图片文件夹到输出目录
output_image_dir=output_dir / "images"
file_utils.ensure_directory_exists(str(output_image_dir))
for img_path in origin_image_paths:
    file_utils.copy_file_to_directory(img_path, str(output_image_dir))
logger.debug("已复制图片文件到:{}", output_image_dir)
#保存PS3证据评估结果
ps3_evidence_path=output_dir / "ps3_evidence.json"
import json
with open(ps3_evidence_path, 'w', encoding='utf-8') as f:
    json.dump(agent_response.ps3_evidence, f, ensure_ascii=False, indent=4)
logger.debug("已保存PS3证据评估结果到:{}", ps3_evidence_path)
logger.success("集成测试全部完成，结果保存在目录:{}", output_dir)
timer.stop()
# 清理tmp文件夹 只保留最近3次运行的文件夹
tmp_dir=Path.cwd() / "tmp"
file_utils.cleanup_old_temp_folders(str(tmp_dir), keep_latest=3)

