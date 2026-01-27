# minerU impl.py--minerU适配器实现
# implements the MinerU interface for file processing
from config.app_config import AppConfig
from infrastructure.adapters.mineru.mineru_interface import cfg
from src.infrastructure.adapters.mineru.mineru_interface import MinerUInterface
from infrastructure.adapters.mineru.mineru_mapping import ERROR_CODE_MAPPING
from utils.logger import Logger
from utils.exceptions import MinerUException
from typing import Any, Dict
import requests

class MinerUImpl(MinerUInterface):
    """MinerU适配器实现类"""
    def __init__(self, config: AppConfig = cfg):
        super().__init__(config)
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
        return {
            "files": [
                {
                    "url": file,
                    **(file_configs.get(file, {}) if file_configs else {})
                }
                for file in files
            ],
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
        self.logger.info("Applied upload URLs successfully")
        return result.get("data", result)

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
        
       