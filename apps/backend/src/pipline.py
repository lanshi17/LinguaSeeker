from loguru import logger
import requests
import component.mineru as mineru
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

@Timer("mineru上传文件")
def minerU(files_path: list[str]) -> Any:
    token=settings.mineru_api_token
    batch_id=mineru.upload_local_files_batch(token,files_path,common_params={"model_version":cfg.mineru_version})[1]
    if not batch_id:
        logger.error("批量上传申请失败，无法继续。")
        return
    logger.debug(f"批量上传申请结果 batch_id: {batch_id}")
    status_info=mineru.query_batch_status(token=token,batch_id=batch_id)
    logger.debug(f"初始状态: {status_info}")
    #轮询等待解析完成
    try:
        final_status = mineru.poll_batch_status_until_done(token=token, batch_id=batch_id)
        logger.debug(f"最终状态: {final_status}")
    except Exception as e:
        logger.exception(f"轮询过程中出现错误: {e}")
        final_status = None
        
    #download results
    try:
        if not final_status:
            logger.error("最终状态为空，无法下载结果。")
            return None
            
        download_folder = file_utils.ensure_directory_exists(settings.mineru_download_dir)
        logger.debug(f"下载目录: {download_folder}")
        download_zip_path =uuid4().hex
        # 从状态数据中提取下载URL（优先 full_zip_url）
        download_url = final_status.download_url
        if not download_url and final_status.extract_result:
            download_url = final_status.extract_result[0].full_zip_url
        if not download_url:
            logger.error("最终状态中没有可用的下载URL（download_url/full_zip_url）")
            return None
        file_utils.download_file(
            download_url,
            f"{download_folder}/{download_zip_path}.zip",
            allow_insecure_fallback=True,
        )
        logger.debug(f"结果已下载到: {download_folder}")
    except exc.FileProcessingException as e:
        logger.exception(f"下载结果时出现错误: {e}")
        return None
    finally:
        pass
    #extract the download'folder
    try:
        extracted_folder = file_utils.ensure_directory_exists(f"{download_folder}/extracted/{download_zip_path}")
        logger.debug(f"解压目录: {extracted_folder}")
        #uuid as extract folder name
        file_utils.extract_zip(f"{download_folder}/{download_zip_path}.zip", extracted_folder)
        logger.debug(f"结果已解压到: {extracted_folder}")
    except exc.FileProcessingException as e:
        logger.exception(f"解压结果时出现错误: {e}")
        return None
    finally:
        pass
    
    # 列出解压目录下的所有文件并找到.md文件并返回md文件路径
    try:
        #列出解压目录下的所有文件
        all_files = file_utils.get_all_files_in_directory(extracted_folder)
        logger.debug(f"解压目录下的所有文件: {all_files}")
        #找到.md文件
        md_file_path = file_utils.find_file_in_directory(extracted_folder, ".md")
        logger.debug(f"找到的.md文件路径: {md_file_path}")
        return md_file_path
    except exc.FileProcessingException as e:
        logger.exception(f"查找.md文件时出现错误: {e}")
        return None
    
    


if __name__ == "__main__":
    import os
    #禁用代理 unset http_proxy https_proxy all_proxy  
    os.environ.pop("http_proxy", None)
    os.environ.pop("https_proxy", None)
    os.environ.pop("all_proxy", None)    
    # #batch test
    # #文件夹
    # folder_path = os.getcwd() + "/demo_pdf/"
    # #获取文件列表
    # files = file_utils.get_all_files_in_directory(folder_path)
    # minerU(files)
    #测试单个文件
    file_path=Path(os.getcwd() + "/demo_pdf/test_de01.pdf")
    md_file_path=minerU([str(file_path)])
    if not isinstance(md_file_path, str):
        logger.error("未能生成md文件")
        sys.exit(1)
    logger.debug("上传测试完成")
    logger.success("解析文件完成")