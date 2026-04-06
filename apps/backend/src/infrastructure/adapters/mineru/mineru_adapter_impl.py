# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportCallIssue=false, reportGeneralTypeIssues=false, reportMissingImports=false, reportRedeclaration=false, reportFunctionMemberAccess=false, reportPossiblyUnboundVariable=false, reportReturnType=false

# MinerU适配器实现
# 实现MinerU接口,提供完整的文档处理流水线
from src.infrastructure.adapters.mineru.mineru_adapter_interface import MinerUAdapterInterface
from src.infrastructure.adapters.mineru.mineru_mapping import ERROR_CODE_MAPPING
from src.utils.logger import Logger
from src.utils.exceptions import MinerUException
from typing import Any, Dict, List, Optional, Tuple
import os
import requests
import time


class MinerUAdapterImpl(MinerUAdapterInterface):
    """MinerU适配器实现类

    封装了与MinerU服务交互的所有细节,对外只暴露mineru_parse方法。
    内部实现包括文件验证、上传、轮询状态、结果获取等完整流程。
    """

    def __init__(self):
        """初始化MinerU适配器实现"""
        super().__init__()
        self._session = requests.Session()
        self.logger = Logger.get_logger("MinerUAdapterImpl")

    # ==================== 公共接口 ====================

    def mineru_parse(
        self,
        files: List[str],
        *,
        poll_interval: float = 2.0,
        timeout_seconds: float = 300.0,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """MinerU文档解析流水线

        完整的处理流程:
        1. 验证输入文件
        2. 申请上传URL
        3. 上传文件到MinerU
        4. 轮询处理状态直到完成或超时
        5. 获取并返回处理结果

        Args:
            files: 待处理的文件路径列表
            poll_interval: 状态轮询间隔(秒)
            timeout_seconds: 处理超时时间(秒)
            **kwargs: 其他可选参数

        Returns:
            单个文件返回字典,多个文件返回包含files列表的字典

        Raises:
            MinerUException: 当处理失败时抛出
        """
        # 1. 验证输入文件
        validated_files = self._validate_input_files(files)

        # 2. 申请上传URL
        upload_response = self._apply_upload_urls(validated_files)
        normalized_files = upload_response.get("files") or []
        if not normalized_files:
            raise MinerUException("MinerU did not return any upload information for the requested files")

        # 3. 提取上传URL并上传文件
        upload_urls: List[str] = []
        for entry in normalized_files:
            upload_url = entry.get("upload_url")
            if not upload_url:
                raise MinerUException("MinerU upload response is missing an upload URL")
            upload_urls.append(upload_url)

        self._upload_to_urls(validated_files, upload_urls)
        self.logger.info(f"Uploaded {len(validated_files)} file(s) successfully")

        # 4. 处理每个文件,轮询状态并获取结果
        processed_entries: List[Dict[str, Any]] = []
        batch_extract_cache: Dict[str, List[Dict[str, Any]]] = {}

        for idx, file_entry in enumerate(normalized_files):
            file_path = validated_files[idx] if idx < len(validated_files) else file_entry.get("source_file")
            file_id = file_entry.get("file_id")
            if not file_id:
                raise MinerUException("MinerU upload response did not contain a file_id")

            # 等待处理完成
            self._wait_for_completion(file_id, poll_interval, timeout_seconds)

            # 获取最终结果
            batch_id, entry_index = self._parse_batch_identifier(file_id)
            if batch_id:
                final_extract = self._get_extract_result_from_batch(
                    batch_id=batch_id,
                    entry_index=entry_index,
                    cache=batch_extract_cache,
                )
            else:
                status = self._get_processing_status(file_id)
                extract_result = status.get("extract_result") or {}
                try:
                    result_payload = self._retrieve_results(file_id)
                except MinerUException:
                    result_payload = {}
                final_extract = result_payload.get("extract_result") or extract_result

            # 构建文件结果
            processed_entries.append(
                self._build_file_result(
                    file_id=file_id,
                    file_path=file_path,
                    extract_result=final_extract,
                    fallback_url=file_entry.get("upload_url"),
                )
            )

        # 5. 返回结果
        if len(processed_entries) == 1:
            return processed_entries[0]
        return {"files": processed_entries}
    def close(self) -> None:
        """关闭会话并释放资源"""
        self._session.close()
        self.logger.info("MinerUAdapterImpl session closed")

    # ==================== 文件验证相关私有方法 ====================

    def _validate_input_files(self, files: list) -> List[str]:
        """验证输入文件列表

        Args:
            files: 文件路径列表

        Returns:
            验证后的文件路径列表

        Raises:
            MinerUException: 当文件无效时抛出
        """
        if not isinstance(files, list):
            try:
                files = list(files)
            except TypeError as exc:
                raise MinerUException("Files must be provided as a list or list-like object") from exc

        if not files:
            raise MinerUException("At least one file must be provided to process with MinerU")

        validated: List[str] = []
        for file_path in files:
            # 规范化路径
            if isinstance(file_path, os.PathLike):
                normalized_path = os.fspath(file_path)
            elif isinstance(file_path, str):
                normalized_path = file_path
            else:
                raise MinerUException("File path must be a string or Path-like object")

            normalized_path = normalized_path.strip()
            if not normalized_path:
                raise MinerUException("File path cannot be empty")
            if not os.path.exists(normalized_path):
                raise MinerUException(f"File does not exist: {normalized_path}")

            # 如果是PDF文件,额外验证
            if normalized_path.lower().endswith(".pdf"):
                self._ensure_valid_pdf(normalized_path)

            validated.append(normalized_path)

        return validated

    def _ensure_valid_pdf(self, file_path: str) -> None:
        """验证PDF文件格式

        Args:
            file_path: PDF文件路径

        Raises:
            MinerUException: 当文件不是有效的PDF时抛出
        """
        try:
            with open(file_path, "rb") as file_handle:
                header = file_handle.read(4)
        except OSError as exc:
            raise MinerUException(f"Unable to read file {file_path}: {exc}") from exc

        if not header.startswith(b"%PDF"):
            raise MinerUException(f"Invalid PDF file: {file_path}")

    # ==================== 上传相关私有方法 ====================

    def _apply_upload_urls(
        self,
        files: List[str],
        file_configs: Optional[Dict[str, Any]] = None,
        request_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """申请文件上传URL

        Args:
            files: 文件路径列表
            file_configs: 每个文件的配置
            request_options: 请求选项

        Returns:
            包含上传URL信息的响应

        Raises:
            MinerUException: 当申请失败时抛出
        """
        payload = self._build_upload_payload(files, file_configs, request_options)
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

    def _upload_to_urls(self, file_paths: List[str], upload_urls: List[str]) -> Dict[str, str]:
        """上传文件到申请的URL

        Args:
            file_paths: 文件路径列表
            upload_urls: 上传URL列表

        Returns:
            上传结果字典

        Raises:
            MinerUException: 当上传失败时抛出
        """
        try:
            if len(file_paths) != len(upload_urls):
                self.logger.warning(
                    "Number of upload URLs (%s) does not match file count (%s)",
                    len(upload_urls),
                    len(file_paths),
                )

            results: Dict[str, str] = {}
            for file_path, url in zip(file_paths, upload_urls):
                with open(file_path, "rb") as f:
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

    # ==================== 状态轮询相关私有方法 ====================

    def _wait_for_completion(
        self,
        file_id: str,
        poll_interval: float,
        timeout_seconds: float,
    ) -> Dict[str, Any]:
        """等待文件处理完成

        Args:
            file_id: 文件ID
            poll_interval: 轮询间隔(秒)
            timeout_seconds: 超时时间(秒)

        Returns:
            最终状态字典

        Raises:
            MinerUException: 当处理失败或超时时抛出
        """
        start = time.monotonic()
        while True:
            status = self._get_processing_status(file_id)
            extract_result = status.get("extract_result") or {}
            state = extract_result.get("state")

            # 规范化状态
            normalized_state = self._normalize_processing_state(state)

            if normalized_state == "completed":
                self.logger.info(f"File {file_id} processing completed")
                return status
            elif normalized_state == "failed":
                error_msg = extract_result.get("err_msg") or "MinerU processing failed"
                raise MinerUException(error_msg)

            # 检查超时
            if time.monotonic() - start > timeout_seconds:
                raise MinerUException(f"MinerU processing timed out for file {file_id}")

            self.logger.info(
                "MinerU still processing file %s (state=%s), waiting %.1fs",
                file_id,
                state,
                poll_interval,
            )
            time.sleep(poll_interval)

    def _get_processing_status(self, file_id: str) -> Dict[str, Any]:
        """获取文件处理状态

        Args:
            file_id: 文件ID

        Returns:
            状态信息字典

        Raises:
            MinerUException: 当获取状态失败时抛出
        """
        batch_id, entry_index = self._parse_batch_identifier(file_id)
        if batch_id:
            data = self._get_batch_status(
                batch_id,
                action="Get batch processing status",
                entry_index=entry_index,
            )
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

    def _retrieve_results(self, file_id: str) -> Dict[str, Any]:
        """检索处理结果

        Args:
            file_id: 文件ID

        Returns:
            结果信息字典

        Raises:
            MinerUException: 当获取结果失败时抛出
        """
        batch_id, entry_index = self._parse_batch_identifier(file_id)
        if batch_id:
            data = self._get_batch_status(
                batch_id,
                action="Retrieve batch results",
                entry_index=entry_index,
            )
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

    # ==================== 结果构建相关私有方法 ====================

    def _build_file_result(
        self,
        *,
        file_id: str,
        file_path: Optional[str],
        extract_result: Dict[str, Any],
        fallback_url: Optional[str],
    ) -> Dict[str, Any]:
        """构建单个文件的处理结果

        Args:
            file_id: 文件ID
            file_path: 原始文件路径
            extract_result: 提取结果
            fallback_url: 备用URL

        Returns:
            标准化的结果字典

        Raises:
            MinerUException: 当处理状态为失败时抛出
        """
        normalized_state = self._normalize_processing_state(extract_result.get("state"))
        if normalized_state == "failed":
            err_msg = extract_result.get("err_msg") or "MinerU reported a failure while processing the file"
            raise MinerUException(err_msg)

        file_name = extract_result.get("file_name")
        if not file_name and file_path:
            file_name = os.path.basename(file_path)
        if not file_name:
            file_name = file_id

        full_zip_url = (
            extract_result.get("full_zip_url")
            or extract_result.get("download_url")
            or fallback_url
            or f"mineru://{file_id}"
        )

        return {
            "file_id": extract_result.get("file_id") or file_id,
            "file_name": file_name,
            "state": normalized_state,
            "full_zip_url": full_zip_url,
        }

    def _normalize_processing_state(self, state: Optional[str]) -> str:
        """规范化处理状态

        Args:
            state: 原始状态字符串

        Returns:
            规范化的状态: completed/failed/processing
        """
        if not state:
            return "processing"

        normalized_state = state.lower()
        if normalized_state in {"completed", "success", "finished", "done"}:
            return "completed"
        if normalized_state in {"failed", "error", "timeout", "terminated"}:
            return "failed"
        return "processing"

    # ==================== 批处理相关私有方法 ====================

    def _get_extract_result_from_batch(
        self,
        *,
        batch_id: str,
        entry_index: Optional[int],
        cache: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """从批处理结果中获取指定条目

        使用缓存避免重复请求

        Args:
            batch_id: 批处理ID
            entry_index: 条目索引
            cache: 缓存字典

        Returns:
            提取结果字典
        """
        if batch_id not in cache:
            batch_payload = self._get_batch_results(batch_id)
            extract_result = batch_payload.get("extract_result")
            if isinstance(extract_result, list):
                cache[batch_id] = extract_result
            elif isinstance(extract_result, dict):
                cache[batch_id] = [extract_result]
            else:
                cache[batch_id] = []

        entries = cache[batch_id]
        if not entries:
            return {}

        if entry_index is not None and 0 <= entry_index < len(entries):
            return entries[entry_index]
        return entries[0]

    def _get_batch_results(self, batch_id: str) -> Dict[str, Any]:
        """批量获取任务结果

        Args:
            batch_id: 批处理ID

        Returns:
            批处理结果字典

        Raises:
            MinerUException: 当获取失败时抛出
        """
        return self._get_batch_status(batch_id, action="Get batch results")

    def _get_batch_status(
        self,
        batch_id: str,
        action: str,
        entry_index: Optional[int] = None,
    ) -> Dict[str, Any]:
        """获取批处理状态

        Args:
            batch_id: 批处理ID
            action: 操作描述
            entry_index: 条目索引(可选)

        Returns:
            批处理状态字典

        Raises:
            MinerUException: 当批处理URL未配置或请求失败时抛出
        """
        if not self.batch_status_url:
            raise MinerUException("Batch status URL is not configured for MinerU client")

        response = self._request(
            "GET",
            f"{self.batch_status_url}{batch_id}",
            action=action,
        )
        payload = self._handle_api_response(response.json(), action)
        data = payload.get("data", payload)
        normalized_results = self._normalize_extract_results(
            data.get("extract_result"),
            data.get("batch_id") or batch_id,
        )

        if entry_index is None:
            extract_payload: Any = normalized_results
        else:
            if normalized_results and 0 <= entry_index < len(normalized_results):
                extract_payload = normalized_results[entry_index]
            else:
                extract_payload = normalized_results[0] if normalized_results else {}

        return {
            "batch_id": data.get("batch_id") or batch_id,
            "extract_result": extract_payload,
        }

    def _normalize_extract_results(
        self,
        extract_result: Any,
        batch_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        """规范化提取结果

        Args:
            extract_result: 原始提取结果
            batch_id: 批处理ID

        Returns:
            规范化的结果列表
        """
        if isinstance(extract_result, list):
            entries = [entry for entry in extract_result if isinstance(entry, dict)]
        elif isinstance(extract_result, dict):
            entries = [extract_result]
        else:
            return []

        normalized_entries: List[Dict[str, Any]] = []
        for idx, entry in enumerate(entries):
            normalized = dict(entry)
            if batch_id:
                normalized.setdefault("batch_id", batch_id)
            if not normalized.get("file_id") and batch_id:
                normalized["file_id"] = self._build_batch_identifier(batch_id, idx)
            normalized_entries.append(normalized)
        return normalized_entries

    # ==================== HTTP请求相关私有方法 ====================

    def _request(
        self,
        method: str,
        url: str,
        *,
        action: str,
        include_auth_header: bool = True,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> requests.Response:
        """统一的HTTP请求发送与异常处理

        Args:
            method: HTTP方法
            url: 请求URL
            action: 操作描述(用于日志)
            include_auth_header: 是否包含认证头
            timeout: 超时时间(秒)
            **kwargs: 其他请求参数

        Returns:
            HTTP响应对象

        Raises:
            MinerUException: 当请求失败时抛出
        """
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
        """处理API响应,检查错误码

        Args:
            payload: API响应负载
            action: 操作描述

        Returns:
            处理后的响应数据

        Raises:
            MinerUException: 当响应包含错误码时抛出
        """
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

    # ==================== 请求负载构建私有方法 ====================

    def _build_upload_payload(
        self,
        files: List[str],
        file_configs: Optional[Dict[str, Any]],
        request_options: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """构建申请上传URL的请求负载

        Args:
            files: 文件路径列表
            file_configs: 文件配置
            request_options: 请求选项

        Returns:
            请求负载字典
        """
        payload_files = []
        configs = file_configs or {}

        for file in files:
            file_entry: Dict[str, Any] = {
                "name": os.path.basename(file),
            }
            # 合并每个文件的配置
            file_entry.update(configs.get(file, {}))
            payload_files.append(file_entry)

        payload: Dict[str, Any] = {"files": payload_files}
        payload.update(self._build_request_options(request_options))
        return payload

    def _build_request_options(self, request_options: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """构建请求级别的配置选项

        Args:
            request_options: 请求选项

        Returns:
            配置选项字典
        """
        options = request_options or {}
        payload: Dict[str, Any] = {}

        model_version = options.get("model_version") or self.model_version
        if model_version:
            payload["model_version"] = model_version

        if "extra_formats" in options:
            payload["extra_formats"] = options["extra_formats"]
        elif getattr(self.config, "extra_formats", None):
            payload["extra_formats"] = list(self.config.extra_formats)

        for key in ("enable_formula", "enable_table", "language", "callback", "seed"):
            if key in options and options[key] is not None:
                payload[key] = options[key]

        return payload

    # ==================== 响应解析相关私有方法 ====================

    def _normalize_file_entries(
        self,
        payload: Dict[str, Any],
        requested_files: List[str],
    ) -> List[Dict[str, Any]]:
        """规范化文件条目列表

        Args:
            payload: API响应负载
            requested_files: 请求的文件列表

        Returns:
            规范化的文件条目列表
        """
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

        # 处理字典类型的条目
        if entries and isinstance(entries[0], dict):
            for idx, entry in enumerate(entries):
                normalized = dict(entry)
                entry_batch_id = normalized.get("batch_id") or batch_id or entry.get("batch_id")
                if entry_batch_id:
                    normalized["batch_id"] = entry_batch_id
                normalized.setdefault("file_index", idx)

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

                if not file_id and entry_batch_id:
                    file_id = self._build_batch_identifier(entry_batch_id, idx)

                if file_id:
                    normalized["file_id"] = file_id
                if upload_url:
                    normalized["upload_url"] = upload_url
                if "file_name" not in normalized and idx < len(requested_files):
                    normalized["file_name"] = os.path.basename(requested_files[idx])
                normalized_entries.append(normalized)
            return normalized_entries

        # 处理字符串类型的条目(上传URL列表)
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
                    "file_index": idx,
                    "source_file": requested_files[idx] if idx < len(requested_files) else None,
                    "file_name": os.path.basename(requested_files[idx]) if idx < len(requested_files) else None,
                }
            )

        return normalized_entries

    def _search_for_list(self, payload: Dict[str, Any], candidate_keys: List[str]) -> List[Any]:
        """在负载中搜索列表类型的值

        Args:
            payload: 搜索目标字典
            candidate_keys: 候选键名列表

        Returns:
            找到的第一个非空列表,未找到返回空列表
        """
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
        """在负载中搜索指定键的值

        Args:
            payload: 搜索目标字典
            target_key: 目标键名

        Returns:
            找到的值,未找到返回None
        """
        stack: List[Dict[str, Any]] = [payload]
        while stack:
            current = stack.pop()
            if target_key in current and current[target_key]:
                return current[target_key]
            for value in current.values():
                if isinstance(value, dict):
                    stack.append(value)
        return None

    # ==================== 工具方法 ====================

    def _build_batch_identifier(self, batch_id: Optional[str], index: int) -> Optional[str]:
        """构建批处理标识符

        Args:
            batch_id: 批处理ID
            index: 索引

        Returns:
            批处理标识符,格式为 "batch::batch_id::index"
        """
        if not batch_id:
            return None
        return f"batch::{batch_id}::{index}"

    def _parse_batch_identifier(self, file_id: Optional[str]) -> Tuple[Optional[str], Optional[int]]:
        """解析批处理标识符

        Args:
            file_id: 文件ID

        Returns:
            (batch_id, entry_index) 元组
        """
        if not isinstance(file_id, str) or not file_id.startswith("batch::"):
            return None, None
        parts = file_id.split("::")
        batch_id = parts[1] if len(parts) >= 2 else None
        try:
            entry_index = int(parts[2]) if len(parts) >= 3 else None
        except (ValueError, TypeError):
            entry_index = None
        return batch_id, entry_index

    def _log_extract_progress(self, extract_result: Dict[str, Any]) -> None:
        """记录提取进度日志

        Args:
            extract_result: 提取结果字典
        """
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
