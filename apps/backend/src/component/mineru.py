import requests
from typing import List, Dict, Any, Callable, Optional
import time
import json
from uuid import uuid4
from .enums import MINERU_TASK_STATE_MAP, MINERU_ERROR_DETAIL_MAP, mineru_response_code
from loguru import logger
from .models import (
    FileUploadItem, 
    BatchUploadRequest, 
    BatchUploadResponseData, 
    ApiResponse, 
    FileExtractResult, 
    MinerURequest,
    MinerUResponse,
    BatchStatusData
)
from config import settings as cfg
from utils.timer import Timer
from utils import file_utils
from utils import exceptions as exc


class MinerUComponent:
    """Mineru 文件解析组件"""
    def __init__(self, token: Optional[str] = None):
        self.token = token or cfg.mineru_api_token
        self.mineru_version = cfg.mineru_version
        self.download_dir = cfg.mineru_download_dir
    # ==================== 辅助函数 ====================

    def _is_success_code(self, code: Any) -> bool:
        return str(code) == mineru_response_code.SUCCESS.value


    def _format_error_detail(self, code: Any) -> str:
        detail = MINERU_ERROR_DETAIL_MAP.get(str(code))
        if not detail:
            return ""
        reason, suggestion = detail
        return f"（{reason}；建议：{suggestion}）"

    def upload_local_files_batch(
        self,
        token: str,
        file_paths: list,
        common_params: dict = None
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """
        通过 Mineru API 批量上传本地文件并获取 batch_id。

        Args:
            token (str): 官网申请的 API Token。
            file_paths (list): 本地文件路径列表。
            common_params (dict, optional): 应用于所有文件的公共配置参数，例如 model_version。

        Returns:
            tuple: (success: bool, batch_id: str or None, error_message: str or None)
        """
        if not file_paths:
            return False, None, "file_paths list is empty."

        # 步骤 1: 准备请求
        apply_url = "https://mineru.net/api/v4/file-urls/batch"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

        # 构建标准化请求体
        try:
            files_data = [
                FileUploadItem(name=path.split("/")[-1].split("\\")[-1])
                for path in file_paths
            ]
            
            request = BatchUploadRequest(
                files=[item.model_dump() for item in files_data],
                **(common_params or {})
            )
            request_body = request.model_dump(exclude_none=True)
        except Exception as e:
            return False, None, f"Failed to build request: {e}"

        try:
            print("正在申请上传链接...")
            response = requests.post(apply_url, headers=headers, json=request_body)
            
            if response.status_code != 200:
                return False, None, f"Request to get URLs failed with status {response.status_code}. Response: {response.text}"

            result = response.json()
            print(f"申请链接响应: {result}")
            
            # 解析为标准化响应结构
            try:
                api_response = ApiResponse(**result)
            except Exception as e:
                return False, None, f"Failed to parse response: {e}"

            if not self._is_success_code(api_response.code):
                detail = self._format_error_detail(api_response.code)
                return False, None, f"API Error: {api_response.msg}{detail}"

            # 解析批量上传响应数据
            try:
                upload_data = BatchUploadResponseData(**api_response.data)
                batch_id = upload_data.batch_id
                urls = upload_data.file_urls
            except Exception as e:
                return False, None, f"Failed to parse upload data: {e}"

            if len(urls) != len(file_paths):
                return False, None, f"Mismatch between number of upload URLs ({len(urls)}) and file paths ({len(file_paths)})"

            # 步骤 2: 上传文件
            print("开始上传文件...")
            for i, (file_path, upload_url) in enumerate(zip(file_paths, urls)):
                print(f"正在上传文件 {i+1}/{len(file_paths)}: {file_path}")
                try:
                    with open(file_path, 'rb') as f:
                        # PUT 请求上传文件
                        upload_response = requests.put(upload_url, data=f)
                        
                        if upload_response.status_code != 200:
                            print(f"上传失败，文件: {file_path}, 状态码: {upload_response.status_code}, 响应: {upload_response.text}")
                            # 可以选择在此处中断或继续上传下一个
                            return False, batch_id, f"Failed to upload file {file_path} to {upload_url}"
                        
                        print(f"文件 {file_path} 上传成功.")
                except FileNotFoundError:
                    print(f"文件未找到: {file_path}")
                    return False, batch_id, f"File not found: {file_path}"
                except Exception as e:
                    print(f"上传文件 {file_path} 时发生错误: {e}")
                    return False, batch_id, f"Error uploading file {file_path}: {e}"

            print("所有文件上传完成.")
            return True, batch_id, None

        except requests.exceptions.RequestException as e:
            print(f"网络请求错误: {e}")
            return False, None, f"Network error: {e}"
        except Exception as e:
            print(f"程序执行错误: {e}")
            return False, None, f"Execution error: {e}"


    def query_batch_status(
        self,
        token: str,
        batch_id: str
    ) -> tuple[bool, Optional[BatchStatusData], Optional[str]]:
        """
        通过 Mineru API 查询批量任务的状态。

        Args:
            token (str): 官网申请的 API Token。
            batch_id (str): 批量任务的 ID。

        Returns:
            tuple: (success: bool, status_info: BatchStatusData or None, error_message: str or None)
        """
        status_url = f"https://mineru.net/api/v4/extract-results/batch/{batch_id}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

        try:
            response = requests.get(status_url, headers=headers)
            print(f"查询状态响应状态码: {response.status_code}")
            
            if response.status_code != 200:
                return False, None, f"Request to query status failed with status {response.status_code}. Response: {response.text}"

            result = response.json()
            print(f"查询状态响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
            
            # 解析为标准化响应结构
            try:
                api_response = ApiResponse(**result)
            except Exception as e:
                return False, None, f"Failed to parse response: {e}"

            if not self._is_success_code(api_response.code):
                detail = self._format_error_detail(api_response.code)
                return False, None, f"API Error: {api_response.msg}{detail}"

            # 解析批量状态数据
            try:
                if api_response.data:
                    status_data = BatchStatusData(**api_response.data)
                    return True, status_data, None
                else:
                    return False, None, "No data in response"
            except Exception as e:
                logger.warning(f"Failed to parse as BatchStatusData: {e}, returning raw data")
                return False, None, f"Failed to parse status data: {e}"

        except requests.exceptions.RequestException as e:
            print(f"查询状态时网络请求错误: {e}")
            return False, None, f"Network error while querying status: {e}"
        except Exception as e:
            print(f"查询状态时程序执行错误: {e}")
            return False, None, f"Execution error while querying status: {e}"



    def upload_local_files_batch_with_callback(
        self,
        token: str,
        file_paths: list,
        callback_url: str,
        common_params: dict = None
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """
        通过 Mineru API 批量上传本地文件，并设置 callback URL 接收解析结果（推荐方式）。

        Args:
            token (str): 官网申请的 API Token。
            file_paths (list): 本地文件路径列表。
            callback_url (str): 解析结果回调通知的 URL（支持 HTTP/HTTPS）。
            common_params (dict, optional): 应用于所有文件的公共配置参数。

        Returns:
            tuple: (success: bool, batch_id: str or None, error_message: str or None)
            
        说明：
            callback 接口要求：
            - 支持 POST 方法、UTF-8 编码
            - Content-Type: application/json
            - 接收参数：checksum（SHA256校验）、content（JSON字符串）
            - 返回 HTTP 200 表示接收成功，其他状态码视为失败
            - 失败时最多重复推送 5 次
        """
        if not file_paths:
            return False, None, "file_paths list is empty."
        
        if not callback_url:
            return False, None, "callback_url is required."

        # 构建标准化请求体
        try:
            files_data = [
                FileUploadItem(name=path.split("/")[-1].split("\\")[-1])
                for path in file_paths
            ]
            
            request = BatchUploadRequest(
                files=[item.model_dump() for item in files_data],
                callback=callback_url,
                **(common_params or {})
            )
            request_body = request.model_dump(exclude_none=True)
        except Exception as e:
            return False, None, f"Failed to build request: {e}"

        apply_url = "https://mineru.net/api/v4/file-urls/batch"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

        try:
            print(f"正在申请上传链接（callback: {callback_url}）...")
            response = requests.post(apply_url, headers=headers, json=request_body)
            
            if response.status_code != 200:
                return False, None, f"Request failed with status {response.status_code}. Response: {response.text}"

            result = response.json()
            print(f"申请链接响应: {result}")
            
            # 解析为标准化响应结构
            try:
                api_response = ApiResponse(**result)
            except Exception as e:
                return False, None, f"Failed to parse response: {e}"

            if not self._is_success_code(api_response.code):
                detail = self._format_error_detail(api_response.code)
                return False, None, f"API Error: {api_response.msg}{detail}"

            # 解析批量上传响应数据
            try:
                upload_data = BatchUploadResponseData(**api_response.data)
                batch_id = upload_data.batch_id
                urls = upload_data.file_urls
            except Exception as e:
                return False, None, f"Failed to parse upload data: {e}"

            if len(urls) != len(file_paths):
                return False, None, f"Mismatch between URLs ({len(urls)}) and files ({len(file_paths)})"

            # 上传文件
            print("开始上传文件...")
            for i, (file_path, upload_url) in enumerate(zip(file_paths, urls)):
                print(f"正在上传文件 {i+1}/{len(file_paths)}: {file_path}")
                try:
                    with open(file_path, 'rb') as f:
                        upload_response = requests.put(upload_url, data=f)
                        
                        if upload_response.status_code != 200:
                            print(f"上传失败，文件: {file_path}, 状态码: {upload_response.status_code}")
                            return False, batch_id, f"Failed to upload file {file_path}"
                        
                        print(f"文件 {file_path} 上传成功.")
                except FileNotFoundError:
                    return False, batch_id, f"File not found: {file_path}"
                except Exception as e:
                    return False, batch_id, f"Error uploading file {file_path}: {e}"

            print(f"所有文件上传完成。解析结果将推送至: {callback_url}")
            return True, batch_id, None

        except requests.exceptions.RequestException as e:
            return False, None, f"Network error: {e}"
        except Exception as e:
            return False, None, f"Execution error: {e}"


    def poll_batch_status_until_done(
        self,
        token: str,
        batch_id: str,
        interval: int = 5,
        max_attempts: int = 60
    ) -> Optional[BatchStatusData]|FileExtractResult:
        """
        轮询批量任务状态，直到所有任务完成或失败（备选方式）。

        Args:
            token (str): API Token。
            batch_id (str): 批量任务 ID。
            interval (int): 轮询间隔（秒）。
            max_attempts (int): 最大轮询次数。
        
        Returns:
            Optional[BatchStatusData]|FileExtractResult: 最终状态信息（BatchStatusData 或 FileExtractResult 实例），失败返回 None。
        """
        print(f"开始轮询任务状态 (batch_id: {batch_id})，最长等待 {max_attempts * interval / 60:.2f} 分钟...")
        
        for attempt in range(max_attempts):
            success, status_data, error = self.query_batch_status(token, batch_id)
            
            if not success:
                print(f"轮询失败 (Attempt {attempt + 1}): {error}")
                if attempt < max_attempts - 1:
                    time.sleep(interval)
                    continue
                else:
                    print("达到最大轮询次数，退出。")
                    return status_data
            
            results = status_data.extract_result
            all_done = True
            any_failed = False
            
            for file_result in results:
                state = file_result.state
                file_name = file_result.file_name
                state_desc = MINERU_TASK_STATE_MAP.get(state)
                full_zip_url = file_result.full_zip_url
                
                if state == "done":
                    print(f"✓ 文件 '{file_name}' 已完成。")
                    if full_zip_url:
                        print(f"  ✓ 结果下载链接: {full_zip_url}")
                elif state_desc:
                    print(f"⏳ 文件 '{file_name}' 当前状态: {state}（{state_desc}）")
                    all_done = False
                    if state == "failed":
                        any_failed = True
                        err_msg = file_result.err_msg or "N/A"
                        print(f"  ✗ 错误信息: {err_msg}")
                else:
                    print(f"❓ 文件 '{file_name}' 状态未知: {state}")
                    all_done = False
            
            if all_done:
                print("\n✓ 所有文件任务已完成！")
                if any_failed:
                    print("⚠ 但其中有失败的任务，请检查错误信息。")
                return status_data
            
            time.sleep(interval)
        
        print(f"\n达到最大轮询次数 ({max_attempts})，任务可能仍在进行中。请稍后再检查。")
        return status_data

    @Timer("mineru上传文件")
    def minerU_pipeline(self, request:MinerURequest) ->MinerUResponse|None:
        token = self.token
        success, batch_id, error_msg = self.upload_local_files_batch(
            token,
            request.file_paths,
            common_params={"model_version": self.mineru_version},
        )
        if not success or not batch_id:
            logger.error(f"批量上传失败，无法继续。错误: {error_msg}")
            return None
        logger.debug(f"批量上传申请结果 batch_id: {batch_id}")
        status_info = self.query_batch_status(token=token, batch_id=batch_id)
        logger.debug(f"初始状态: {status_info}")
        #轮询等待解析完成
        try:
            final_status = self.poll_batch_status_until_done(token=token, batch_id=batch_id)
            logger.debug(f"最终状态: {final_status}")
        except Exception as e:
            logger.exception(f"轮询过程中出现错误: {e}")
            final_status = None
            
        #download results
        try:
            if not final_status:
                logger.error("最终状态为空，无法下载结果。")
                return None
                
            download_folder = file_utils.ensure_directory_exists(self.download_dir)
            logger.debug(f"下载目录: {download_folder}")
            download_zip_path = uuid4().hex
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
        
        # 列出解压目录下的所有文件并找到.md文件并返回解压文件夹路径
        try:
            #列出解压目录下的所有文件
            all_files = file_utils.get_all_files_in_directory(extracted_folder)
            logger.debug(f"解压目录下的所有文件: {all_files}")
            #找到.md文件以验证解压成功
            md_file_path = file_utils.find_file_in_directory(extracted_folder, ".md")
            logger.debug(f"找到的.md文件路径: {md_file_path}")
            # 返回解压文件夹路径，以便调用者可以访问所有文件（包括图片）
            return MinerUResponse(
                task_id=batch_id,
                status="done",
                message="文件解析完成",
                folder_path=extracted_folder,
            )
        except exc.FileProcessingException as e:
            logger.exception(f"查找.md文件时出现错误: {e}")
            return None