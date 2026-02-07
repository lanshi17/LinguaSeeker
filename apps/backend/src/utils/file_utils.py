"""File utility functions for downloading and extracting files."""

import os
import zipfile
import tempfile
from pathlib import Path
from typing import Dict, Any
import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import SSLError
from urllib3.util.retry import Retry
from loguru import logger
from .exceptions import FileProcessingException, SuppressAndLog


# Default timeout for file downloads (in seconds)
DEFAULT_DOWNLOAD_TIMEOUT = 300


def download_file(
    url: str, 
    destination: str, 
    timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
    retries: int = 3,
    backoff_factor: float = 0.5,
    allow_insecure_fallback: bool = False,
) -> str:
    """Download a file from a URL to a destination path.
    
    Args:
        url: URL to download from
        destination: Path to save the downloaded file
        timeout: Timeout for the download request in seconds (default: 300)
        
    Returns:
        Path to the downloaded file
        
    Raises:
        FileProcessingException: If download fails
    """
    try:
        logger.info(f"Downloading file from {url}")
        session = requests.Session()
        retry = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=backoff_factor,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        try:
            response = session.get(url, stream=True, timeout=timeout)
            response.raise_for_status()
        except SSLError as e:
            if allow_insecure_fallback:
                logger.warning(f"SSL error detected, retrying without verification: {e}")
                response = session.get(url, stream=True, timeout=timeout, verify=False)
                response.raise_for_status()
            else:
                raise
        
        with open(destination, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        logger.info(f"File downloaded successfully to {destination}")
        return destination
    except requests.RequestException as e:
        logger.error(f"Failed to download file from {url}: {e}")
        raise FileProcessingException(f"Failed to download file: {e}")
    except IOError as e:
        logger.error(f"Failed to save downloaded file to {destination}: {e}")
        raise FileProcessingException(f"Failed to save file: {e}")


def safe_remove_file(file_path: str) -> bool:
    """安全删除文件，使用SuppressAndLog处理可能的异常"""
    with SuppressAndLog(OSError):
        os.remove(file_path)
        logger.info(f"Successfully removed file: {file_path}")
        return True
    
    logger.warning(f"Failed to remove file (may not exist): {file_path}")
    return False


def extract_zip(zip_path: str, extract_to: str) -> str:
    """Extract a zip file to a directory.
    
    Args:
        zip_path: Path to the zip file
        extract_to: Directory to extract files to
        
    Returns:
        Path to the extraction directory
        
    Raises:
        FileProcessingException: If extraction fails
    """
    try:
        logger.info(f"Extracting zip file {zip_path} to {extract_to}")
        os.makedirs(extract_to, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        
        logger.info(f"Zip file extracted successfully to {extract_to}")
        return extract_to
    except zipfile.BadZipFile as e:
        logger.error(f"Invalid zip file {zip_path}: {e}")
        raise FileProcessingException(f"Invalid zip file: {e}")
    except Exception as e:
        logger.error(f"Failed to extract zip file {zip_path}: {e}")
        raise FileProcessingException(f"Failed to extract zip: {e}")


def find_file_in_directory(directory: str, extension: str) -> str:
    """Find the first file with a given extension in a directory.
    
    Args:
        directory: Directory to search in
        extension: File extension to look for (e.g., '.html', '.json')
        
    Returns:
        Path to the found file
        
    Raises:
        FileProcessingException: If no file is found
    """
    try:
        path = Path(directory)
        for file_path in path.rglob(f"*{extension}"):
            logger.info(f"Found file: {file_path}")
            return str(file_path)
        
        raise FileProcessingException(f"No {extension} file found in {directory}")
    except Exception as e:
        logger.error(f"Error searching for file in {directory}: {e}")
        raise FileProcessingException(f"Error searching for file: {e}")


def get_all_files_in_directory(directory: str) -> Dict[str, str]:
    """获取目录下所有文件的完整路径Dict。
    
    Args:
        directory: 目标目录路径。
        
    Returns:
        包含所有文件完整路径的字典，键为文件路径，值为文件内容。
    """
    files_dict = {}
    try:
        path = Path(directory)
        for file_path in path.rglob("*"):
            if file_path.is_file():
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    files_dict[str(file_path)] = content
                    logger.debug(f"Loaded file: {file_path}")
        return files_dict
    except Exception as e:
        logger.error(f"Error reading files in directory {directory}: {e}")
        raise FileProcessingException(f"Error reading files: {e}")
    

def ensure_directory_exists(directory: str) -> str:
    """确保目录存在，如果不存在则创建它。
    
    Args:
        directory: 目标目录路径。
        
    Returns:
        目标目录路径。
    """
    os.makedirs(directory, exist_ok=True)
    logger.info(f"Directory ensured: {directory}")
    return directory

def copy_file_to_directory(file_path: str, destination_directory: str) -> str:
    """将文件复制到指定目录。
    
    Args:
        file_path: 源文件路径。
        destination_directory: 目标目录路径。   
    """
    try:
        from shutil import copy2
        ensure_directory_exists(destination_directory)
        destination_path = Path(destination_directory) / Path(file_path).name
        copy2(file_path, destination_path)
        logger.info(f"Copied file {file_path} to {destination_path}")
        return str(destination_path)
    except Exception as e:
        logger.error(f"Error copying file {file_path} to {destination_directory}: {e}")
        raise FileProcessingException(f"Error copying file: {e}")

def cleanup_old_temp_folders(temp_root: str, keep_latest: int = 3) -> None:
    """清理临时文件夹，只保留最近的几个运行文件夹。
    
    Args:
        temp_root: 临时文件夹根目录路径。
        keep_latest: 保留的最新运行文件夹数量。
    """
    try:
        temp_path = Path(temp_root)
        if not temp_path.exists() or not temp_path.is_dir():
            logger.warning(f"Temporary root directory does not exist: {temp_root}")
            return
        
        run_dirs = [d for d in temp_path.iterdir() if d.is_dir() and d.name.startswith("run_")]
        run_dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
        
        for old_dir in run_dirs[keep_latest:]:
            from shutil import rmtree
            rmtree(old_dir)
            logger.info(f"Removed old temporary folder: {old_dir}")
    except Exception as e:
        logger.error(f"Error cleaning up temporary folders in {temp_root}: {e}")
        raise FileProcessingException(f"Error cleaning up temp folders: {e}")