from loguru import logger
import requests
from component.mineru import MinerUComponent
from component.rag import RAGComponent
from database.qdrant import QdrantManager
from utils.timer import Timer, timer
import utils.exceptions as exc
import utils.file_utils as file_utils
from typing import Any
from pathlib import Path
from uuid import uuid4
import sys
from datetime import datetime
from config import settings
cfg=settings
logger.add(
    sink=f"logs/app_{datetime.now().strftime('%Y%m%d')}.log", # 文件名包含日期
    level="INFO", # 记录 INFO 及以上级别的日志到文件
    rotation="00:00", # 每天午夜滚动
    retention="7 days", # 保留最近7天的日志文件
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} - {message}",
    compression="zip", # 可选：对旧日志进行压缩
    enqueue=True, # 线程安全
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
    diagnose=True, # 提供更详细的错误上下文 (在生产环境中可能需要关闭以保护敏感信息)
    enqueue=True, # 线程安全
)

mineru=MinerUComponent()
rag=RAGComponent()



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