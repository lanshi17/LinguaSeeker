# Global fixture configuration (e.g., pytest-asyncio, database sessions)
import sys
from pathlib import Path
import dotenv
from loguru import logger
from datetime import datetime
# Load environment variables from .env.test file
dotenv.load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env.local")

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
# Disable proxies for tests
import os
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ.pop("all_proxy", None)  
import pytest
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
@pytest.fixture(scope="session")
def any_global_fixture():
    # Setup code here

    yield
    # Teardown code here
    pass
# Add more fixtures as needed for tests

# This file is used to define global fixtures and configurations for tests.
# It can include setup and teardown logic for test sessions.
# For example, you can define database fixtures, mock services, etc.