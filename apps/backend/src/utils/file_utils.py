"""File utility functions for downloading and extracting files."""

import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict

import requests
from loguru import logger

from .exceptions import FileProcessingException, SuppressAndLog

# Default timeout for file downloads (in seconds)
DEFAULT_DOWNLOAD_TIMEOUT = 300


def ensure_directory_exists(path: str) -> str:
    try:
        os.makedirs(path, exist_ok=True)
        return path
    except OSError as e:
        logger.error(f"Failed to create directory {path}: {e}")
        raise FileProcessingException(f"Failed to create directory: {e}")


def cleanup_old_temp_folders(base_dir: str, keep_latest: int = 3) -> None:
    path = Path(base_dir)
    if not path.exists() or not path.is_dir():
        return

    directories = [entry for entry in path.iterdir() if entry.is_dir()]
    directories.sort(key=lambda entry: entry.stat().st_mtime, reverse=True)

    for old_dir in directories[max(keep_latest, 0) :]:
        try:
            shutil.rmtree(old_dir)
            logger.info(f"Removed old temp directory: {old_dir}")
        except OSError as e:
            logger.warning(f"Failed to remove temp directory {old_dir}: {e}")


def download_file(
    url: str,
    destination: str,
    timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
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
        response = requests.get(url, stream=True, timeout=timeout)
        response.raise_for_status()

        with open(destination, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        logger.info(f"File downloaded successfully to {destination}")
        return destination
    except requests.RequestException as e:
        if not allow_insecure_fallback:
            logger.error(f"Failed to download file from {url}: {e}")
            raise FileProcessingException(f"Failed to download file: {e}")

        logger.warning(
            f"Download failed with TLS verification enabled for {url}, retrying insecurely: {e}"
        )

        try:
            insecure_response = requests.get(
                url,
                stream=True,
                timeout=timeout,
                verify=False,
            )
            insecure_response.raise_for_status()

            with open(destination, "wb") as f:
                for chunk in insecure_response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            logger.info(
                f"File downloaded successfully to {destination} with insecure fallback"
            )
            return destination
        except requests.RequestException as insecure_error:
            logger.error(f"Failed to download file from {url}: {insecure_error}")
            raise FileProcessingException(f"Failed to download file: {insecure_error}")

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

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
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


def get_all_files_in_directory(
    directory: str, recursive: bool = True
) -> Dict[str, str]:
    """Read all files in a directory into a dict of {path: content}.

    Args:
        directory: Directory to scan
        recursive: Whether to include files in subdirectories

    Returns:
        Mapping of file paths to file contents (UTF-8, errors ignored)

    Raises:
        FileProcessingException: If directory does not exist or is not readable
    """
    path = Path(directory)
    if not path.exists() or not path.is_dir():
        raise FileProcessingException(f"Directory not found: {directory}")

    files: Dict[str, str] = {}
    iterator = path.rglob("*") if recursive else path.glob("*")
    for file_path in iterator:
        if not file_path.is_file():
            continue
        try:
            files[str(file_path)] = file_path.read_text(
                encoding="utf-8", errors="ignore"
            )
        except Exception as exc:
            logger.warning(f"Failed to read file {file_path}: {exc}")
            continue

    return files


def create_temp_directory(prefix: str = "mineru_") -> str:
    """Create a temporary directory.

    Args:
        prefix: Prefix for the temporary directory name

    Returns:
        Path to the created directory
    """
    temp_dir = tempfile.mkdtemp(prefix=prefix)
    logger.info(f"Created temporary directory: {temp_dir}")
    return temp_dir
