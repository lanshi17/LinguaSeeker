import requests
from typing import List
from loguru import logger
import requests
import time
import json

def upload_local_files_batch(token: str, file_paths: list, common_params: dict = None):
    """
    通过 Minero API 批量上传本地文件并获取 batch_id。

    Args:
        token (str): 官网申请的 API Token。
        file_paths (list): 本地文件路径列表。
        common_params (dict, optional): 应用于所有文件的公共配置参数，例如 model_version。

    Returns:
        tuple: (success: bool, batch_id: str or None, error_message: str or None)
    """
    if not file_paths:
        return False, None, "file_paths list is empty."

    # 步骤 1: 请求批量上传 URL
    apply_url = "https://mineru.net/api/v4/file-urls/batch"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    # 准备请求体数据，将每个文件路径映射为一个包含 name 的对象
    files_data = []
    for path in file_paths:
        # 从路径中提取文件名
        filename = path.split("/")[-1].split("\\")[-1]
        files_data.append({"name": filename, "data_id": ""}) # data_id 可以根据需要设置

    request_body = {
        "files": files_data,
        # 将公共参数（如 model_version）合并到请求体顶层
        **(common_params or {})
    }

    try:
        print("正在申请上传链接...")
        response = requests.post(apply_url, headers=headers, json=request_body)
        
        if response.status_code != 200:
            return False, None, f"Request to get URLs failed with status {response.status_code}. Response: {response.text}"

        result = response.json()
        print(f"申请链接响应: {result}")

        if result["code"] != 0:
            return False, None, f"API Error applying for URLs: {result.get('msg', 'Unknown error')}"

        batch_id = result["data"]["batch_id"]
        urls = result["data"]["file_urls"]

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


def query_batch_status(token: str, batch_id: str):
    """
    通过 Minero API 查询批量任务的状态。

    Args:
        token (str): 官网申请的 API Token。
        batch_id (str): 批量任务的 ID。

    Returns:
        tuple: (success: bool, status_info: dict or None, error_message: str or None)
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

        if result["code"] != 0:
            return False, None, f"API Error querying status: {result.get('msg', 'Unknown error')}"

        status_info = result.get("data", {})
        return True, status_info, None

    except requests.exceptions.RequestException as e:
        print(f"查询状态时网络请求错误: {e}")
        return False, None, f"Network error while querying status: {e}"
    except Exception as e:
        print(f"查询状态时程序执行错误: {e}")
        return False, None, f"Execution error while querying status: {e}"


def poll_batch_status_until_done(token: str, batch_id: str, interval: int = 10, max_attempts: int = 360):
    """
    轮询批量任务状态，直到所有任务完成或失败。

    Args:
        token (str): API Token。
        batch_id (str): 批量任务 ID。
        interval (int): 轮询间隔（秒）。
        max_attempts (int): 最大轮询次数。
    
    Returns:
        dict: 最终状态信息。
    """
    print(f"开始轮询任务状态 (batch_id: {batch_id})，最长等待 {max_attempts * interval / 60:.2f} 分钟...")
    for attempt in range(max_attempts):
        success, status_data, error = query_batch_status(token, batch_id)
        
        if not success:
            print(f"轮询失败 (Attempt {attempt + 1}): {error}")
            if attempt < max_attempts - 1:
                 time.sleep(interval)
                 continue
            else:
                print("达到最大轮询次数，退出。")
                return status_data
        
        results = status_data.get("extract_result", [])
        all_done = True
        any_failed = False
        for file_result in results:
            state = file_result.get("state", "unknown")
            file_name = file_result.get("file_name", "unknown")
            if state in ["done"]:
                print(f"文件 '{file_name}' 已完成。")
            elif state in ["failed", "converting", "pending", "running", "waiting-file"]:
                print(f"文件 '{file_name}' 当前状态: {state}...")
                all_done = False
                if state == "failed":
                    any_failed = True
                    print(f"  -> 错误信息: {file_result.get('err_msg', 'N/A')}")
            else:
                print(f"文件 '{file_name}' 状态未知: {state}")
                all_done = False
        
        if all_done:
            print("\n所有文件任务已完成！")
            if any_failed:
                print("但其中有失败的任务，请检查错误信息。")
            return status_data
        
        time.sleep(interval)
    
    print(f"\n达到最大轮询次数 ({max_attempts})，任务可能仍在进行中。请稍后再检查。")
    return status_data


if __name__ == "__main__":
    # --- 配置 ---
    TOKEN = "YOUR_API_TOKEN_HERE"  # 替换为您自己的 API Token
    LOCAL_FILE_PATHS = ["demo.pdf", "demo2.pdf"] # 替换为您的本地文件路径列表
    COMMON_PARAMS = { # 可选的公共参数
        "model_version": "vlm",
        "enable_formula": True,
        "enable_table": True,
        # "callback": "http://127.0.0.1/callback", # 可选
        # "seed": "your_seed_for_callback",       # 如果使用 callback 必须提供
    }

    # --- 执行流程 ---
    print("--- 开始批量上传本地文件 ---")
    success, batch_id, error = upload_local_files_batch(TOKEN, LOCAL_FILE_PATHS, COMMON_PARAMS)

    if not success:
        print(f"批量上传流程失败: {error}")
        exit(1)

    print(f"--- 成功提交批量任务，Batch ID: {batch_id} ---")

    # --- 查询状态 ---
    print("\n--- 开始查询任务状态 ---")
    final_status = poll_batch_status_until_done(TOKEN, batch_id)

    # --- 输出最终结果 ---
    print("\n--- 最终任务状态 ---")
    print(json.dumps(final_status, indent=2, ensure_ascii=False))

    # --- 提取下载链接 (如果需要) ---
    print("\n--- 提取下载链接 ---")
    results = final_status.get("extract_result", [])
    for file_result in results:
        file_name = file_result.get("file_name")
        state = file_result.get("state")
        download_url = file_result.get("full_zip_url")
        if state == "done" and download_url:
            print(f"文件 '{file_name}' 下载链接: {download_url}")
        elif state == "failed":
             print(f"文件 '{file_name}' 解析失败: {file_result.get('err_msg', 'N/A')}")
        else:
            print(f"文件 '{file_name}' 状态: {state}, 下载链接不可用。")