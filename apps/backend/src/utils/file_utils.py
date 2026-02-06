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

