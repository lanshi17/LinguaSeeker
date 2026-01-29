# minerU impl.py--minerU适配器实现
# implements the MinerU interface for file processing
from src.infrastructure.adapters.mineru.mineru_adapter_interface import MinerUAdapterInterface
from src.infrastructure.adapters.mineru.mineru_mapping import ERROR_CODE_MAPPING
from src.utils.logger import Logger
from src.utils.exceptions import MinerUException
from typing import Any, Dict, List, Optional
import os
import requests

class MinerUAdapterImpl(MinerUAdapterInterface):
    """MinerU适配器实现类"""
    def __init__(self):
        super().__init__()
        self._session = requests.Session()
        
    def pipline_process(self, files: list) -> Dict[str, Any]:
        """文件流水线处理"""
        upload_response = self.apply_upload_urls(files)
        upload_urls = [file_info["upload_url"] for file_info in upload_response.get("files", [])]
        
        upload_results = self.upload_to_urls(files, upload_urls)
        self.logger.info(f"Upload results: {upload_results}")
        
        file_ids = [file_info["file_id"] for file_info in upload_response.get("files", [])]
        processing_results = {}
        
        for file_id in file_ids:
            status = self.get_processing_status(file_id)
            processing_results[file_id] = status
            
            if status.get("extract_result", {}).get("state") == "completed":
                result = self.retrieve_results(file_id)
                processing_results[file_id]["result"] = result
                
        return processing_results

    def _request(
        self,
        method: str,
        url: str,
        *,
        action: str,
        include_auth_header: bool = True,
        timeout: int | None = None,
        **kwargs,
    ) -> requests.Response:
        """统一的请求发送与异常处理入口"""
        headers = kwargs.pop("headers", None)
        # 合并请求头
        if include_auth_header:
            merged_headers = dict(self.header)
            if headers:
                merged_headers.update(headers)
        else:
            merged_headers = headers

        try:
            response = self._session.request(
                method=method,
                url=url,
                headers=merged_headers,
                timeout=timeout or getattr(self.config, "timeout", None),
                **kwargs,
            )
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            self.logger.error(f"{action} request failed: {exc}")
            raise MinerUException(str(exc)) from exc

    def _handle_api_response(self, payload: Dict[str, Any], action: str) -> Dict[str, Any]:
        """处理API响应，检查错误码并抛出异常"""
        if payload.get("code") == 0:
            return payload

        error_code = str(payload.get("code"))
        mapping = ERROR_CODE_MAPPING.get(error_code)
        message = payload.get("msg") or (mapping["description"] if mapping else "Unknown error")
        suggestion = mapping["suggestion"] if mapping else ""
        detail = f"{action} failed ({error_code}): {message}"
        if suggestion:
            detail = f"{detail}. Suggestion: {suggestion}"
        self.logger.error(detail)
        raise MinerUException(detail)

    def _build_upload_payload(self, files: list[str], file_configs: Dict[str, Any] | None) -> Dict[str, Any]:
        """ 构建申请上传URL的请求负载 """
        payload_files = []
        configs = file_configs or {}

        for file in files:
            file_entry: Dict[str, Any] = {
                "url": file,
                "name": os.path.basename(file),
            }
            # Merge per-file config if provided
            file_entry.update(configs.get(file, {}))
            payload_files.append(file_entry)

        return {
            "files": payload_files,
            "model_version": self.model_version
        }

    def _log_extract_progress(self, extract_result: Dict[str, Any]) -> None:
        """ 日志记录提取进度 """
        state = extract_result.get("state")
        if state == "running":
            progress = extract_result.get("extract_progress", {})
            self.logger.info(
                "Processing in progress - %s/%s pages extracted",
                progress.get("extracted_pages"),
                progress.get("total_pages"),
            )
        elif state == "failed":
            self.logger.error(f"Processing failed: {extract_result.get('err_msg')}")

    def apply_upload_urls(self, files: list[str], file_configs: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """申请文件上传URL"""
        payload = self._build_upload_payload(files, file_configs)
        response = self._request(
            "POST",
            self.batch_url,
            json=payload,
            action="Apply upload URLs",
        )
        result = self._handle_api_response(response.json(), "Apply upload URLs")
        data = result.get("data", result)

        normalized_files = self._normalize_file_entries(data, files)
        if not normalized_files:
            self.logger.error("Apply upload URLs response missing file data: %s", data)
            raise MinerUException("Apply upload URLs succeeded but no file upload info was returned")

        data["files"] = normalized_files
        self.logger.info("Applied upload URLs successfully")
        return data

    def upload_to_urls(self, file_paths: list[str], upload_urls: list[str]) -> Dict[str, str]:
        """上传文件到申请的URL"""
        try:
            if len(file_paths) != len(upload_urls):
                self.logger.warning(
                    "Number of upload URLs (%s) does not match file count (%s)",
                    len(upload_urls),
                    len(file_paths),
                )
            results: Dict[str, str] = {}
            for file_path, url in zip(file_paths, upload_urls):
                with open(file_path, 'rb') as f:
                    self._request(
                        "PUT",
                        url,
                        data=f,
                        action=f"Upload file {file_path}",
                        include_auth_header=False,
                    )
                    self.logger.info(f"File {file_path} uploaded successfully")
                    results[file_path] = "success"
            return results
        except MinerUException:
            raise
        except IOError as e:
            self.logger.error(f"Error uploading files: {str(e)}")
            raise MinerUException(str(e)) from e

    def get_processing_status(self, file_id: str) -> Dict[str, Any]:
        """获取文件处理状态"""
        batch_id = self._extract_batch_id(file_id)
        if batch_id:
            data = self._get_batch_status(batch_id, action="Get batch processing status")
            self._log_extract_progress(data.get("extract_result", {}))
            return data

        response = self._request(
            "GET",
            f"{self.status_url}/{file_id}",
            action="Get processing status",
        )
        payload = self._handle_api_response(response.json(), "Get processing status")
        data = payload.get("data", payload)
        self.logger.info(f"Retrieved processing status successfully. Trace ID: {payload.get('trace_id')}")
        self._log_extract_progress(data.get("extract_result", {}))
        return data

    def retrieve_results(self, file_id: str) -> Dict[str, Any]:
        """检索处理结果"""
        batch_id = self._extract_batch_id(file_id)
        if batch_id:
            data = self._get_batch_status(batch_id, action="Retrieve batch results")
            extract_result = data.get("extract_result", {})
            if extract_result:
                self.logger.info(
                    f"File: {extract_result.get('file_name')}, Download URL: {extract_result.get('full_zip_url')}"
                )
            return data

        response = self._request(
            "GET",
            f"{self.status_url}/{file_id}",
            action="Retrieve results",
        )
        payload = self._handle_api_response(response.json(), "Retrieve results")
        data = payload.get("data", payload)
        extract_result = data.get("extract_result", {})
        self.logger.info(f"Retrieved results successfully. Trace ID: {payload.get('trace_id')}")
        if extract_result:
            self.logger.info(
                f"File: {extract_result.get('file_name')}, Download URL: {extract_result.get('full_zip_url')}"
            )
        return data
    
    def download_result_file(self, file_url: str) -> bytes:
        """下载结果文件"""
        response = self._request(
            "GET",
            file_url,
            action="Download result file",
            include_auth_header=False,
        )
        self.logger.info("Result file downloaded successfully")
        return response.content
    
    def close(self) -> None:
        """关闭会话"""
        self._session.close()
        self.logger.info("MinerUImpl session closed")

    def _normalize_file_entries(self, payload: Dict[str, Any], requested_files: List[str]) -> List[Dict[str, Any]]:
        """Normalize API responses so downstream logic always sees files list."""
        if payload is None:
            return []

        candidate_keys = [
            "files",
            "file_url_infos",
            "file_urls",
            "fileInfos",
            "file_infos",
        ]

        entries: List[Any] = self._search_for_list(payload, candidate_keys)
        if not entries:
            return []

        batch_id = self._search_payload_for_key(payload, "batch_id")
        normalized_entries: List[Dict[str, Any]] = []

        if entries and isinstance(entries[0], dict):
            for idx, entry in enumerate(entries):
                normalized = dict(entry)
                normalized.setdefault("batch_id", batch_id or entry.get("batch_id"))

                file_id = (
                    entry.get("file_id")
                    or entry.get("fileId")
                    or entry.get("fileID")
                    or entry.get("id")
                )
                upload_url = (
                    entry.get("upload_url")
                    or entry.get("uploadUrl")
                    or entry.get("url")
                )

                if not file_id and normalized.get("batch_id"):
                    file_id = self._build_batch_identifier(normalized["batch_id"], idx)

                if file_id:
                    normalized["file_id"] = file_id
                if upload_url:
                    normalized["upload_url"] = upload_url

                normalized_entries.append(normalized)
            return normalized_entries

        # entries list may be strings (upload URLs)
        for idx, entry in enumerate(entries):
            if not isinstance(entry, str):
                continue
            identifier = self._build_batch_identifier(batch_id, idx)
            if not identifier:
                self.logger.warning("Unable to build batch identifier for upload URL response: %s", entry)
                continue
            normalized_entries.append(
                {
                    "file_id": identifier,
                    "batch_id": batch_id,
                    "upload_url": entry,
                    "source_file": requested_files[idx] if idx < len(requested_files) else None,
                }
            )

        return normalized_entries
    
    def _search_for_list(self, payload: Dict[str, Any], candidate_keys: List[str]) -> List[Any]:
        stack: List[Dict[str, Any]] = [payload]
        while stack:
            current = stack.pop()
            for key in candidate_keys:
                entries = current.get(key)
                if isinstance(entries, list) and entries:
                    return entries
            for value in current.values():
                if isinstance(value, dict):
                    stack.append(value)
        return []

    def _search_payload_for_key(self, payload: Dict[str, Any], target_key: str) -> Optional[Any]:
        stack: List[Dict[str, Any]] = [payload]
        while stack:
            current = stack.pop()
            if target_key in current and current[target_key]:
                return current[target_key]
            for value in current.values():
                if isinstance(value, dict):
                    stack.append(value)
        return None

    def _build_batch_identifier(self, batch_id: Optional[str], index: int) -> Optional[str]:
        if not batch_id:
            return None
        return f"batch::{batch_id}::{index}"

    def _extract_batch_id(self, file_id: str) -> Optional[str]:
        if not isinstance(file_id, str):
            return None
        if not file_id.startswith("batch::"):
            return None
        parts = file_id.split("::")
        if len(parts) >= 2 and parts[1]:
            return parts[1]
        return None

    def _select_first_extract_result(self, extract_result: Any) -> Dict[str, Any]:
        if isinstance(extract_result, list):
            return extract_result[0] if extract_result else {}
        if isinstance(extract_result, dict):
            return extract_result
        return {}

    def _get_batch_status(self, batch_id: str, action: str) -> Dict[str, Any]:
        if not self.batch_status_url:
            raise MinerUException("Batch status URL is not configured for MinerU client")

        response = self._request(
            "GET",
            f"{self.batch_status_url}{batch_id}",
            action=action,
        )
        payload = self._handle_api_response(response.json(), action)
        data = payload.get("data", payload)
        normalized = {
            "batch_id": data.get("batch_id") or batch_id,
            "extract_result": self._select_first_extract_result(data.get("extract_result")),
        }
        return normalized
