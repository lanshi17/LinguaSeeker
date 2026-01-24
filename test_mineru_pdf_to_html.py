# from mineru import MineruKIEClient
from pathlib import Path
from typing import Optional
import requests
import time
import zipfile
import io
import os
from src.infrastructure.utils.logger import Logger
from src.infrastructure.utils.config import AppConfig

config= AppConfig.from_env()
#设置无代理
os.environ["http_proxy"] = ""
os.environ["https_proxy"] = ""
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
os.environ["SOCKS_PROXY"] = ""
os.environ["socks_proxy"] = ""
os.environ["ALL_PROXY"] = ""
os.environ["all_proxy"] = ""


token = config.mineru.api_token
url = config.mineru.api_url
# url = "https://mineru.net/api/v4/file-urls/batch"
header = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {token}"
}

file_path = ["simple_pdfs/sample_chinese.pdf"]

# 自动检测语言
print(f"Detecting language for: {file_path[0]}")
try:
    from src.infrastructure.repositories import PDFRepositoryImpl
    from src.domain.value_objects import Language
    from langdetect import detect
    import pytesseract
    from pdf2image import convert_from_path
    from langchain_community.document_loaders import PyPDFLoader
    
    # 使用简化的语言检测（不需要 OCR 配置）
    # 直接提取文本
    loader = PyPDFLoader(file_path[0])
    docs = loader.load()
    text = "\n".join(doc.page_content for doc in docs[:3])  # 只检测前3页
    
    if not text.strip():
        # 如果没有文本，尝试 OCR 第一页
        images = convert_from_path(file_path[0], first_page=1, last_page=1)
        text = pytesseract.image_to_string(images[0])
    
    if text.strip():
        # 使用 langdetect 检测
        detected_code = detect(text)
        
        # 映射到 MinerU API 语言代码
        lang_map = {
            "zh-cn": "ch",
            "zh-tw": "ch",
            "zh": "ch",
            "en": "en",
            "ja": "ja",
            "ru": "ru",
            "de": "de",
            "fr": "fr",
        }
        
        language = lang_map.get(detected_code, "en")
        print(f"Detected language code: {detected_code} -> MinerU code: {language}")
    else:
        print("No text found, using default 'en'")
        language = "en"
        
except Exception as e:
    print(f"Language detection failed: {e}, using default 'en'")
    language = "en"

data = {
    "files": [
        {"name": Path(file_path[0]).name, "data_id": "test_pdf_001"}
    ],
    "model_version":"pipeline",
    "language": language,
    "extra_formats": ["html"],
    "file.is_ocr": True
}

batch_id = None  # Initialize batch_id

try:
    response = requests.post(url,headers=header,json=data)
    if response.status_code == 200:
        result = response.json()
        print('response success. result:{}'.format(result))
        if result["code"] == 0:
            batch_id = result["data"]["batch_id"]
            urls = result["data"]["file_urls"]
            print('batch_id:{},urls:{}'.format(batch_id, urls))
            for i in range(0, len(urls)):
                with open(file_path[i], 'rb') as f:
                    res_upload = requests.put(urls[i], data=f)
                    if res_upload.status_code == 200:
                        print(f"{urls[i]} upload success")
                    else:
                        print(f"{urls[i]} upload failed")
        else:
            print('apply upload url failed,reason:{}'.format(result.get('msg')))
            print("Exiting due to API error.")
            exit(1)
    else:
        print('response not success. status:{} ,result:{}'.format(response.status_code, response))
        exit(1)
except Exception as err:
    print(err)
    exit(1)

if not batch_id:
    print("No batch_id available, cannot poll results.")
    exit(1)


### 轮询请求结果（直到成功并下载） ###
time.sleep(3)

poll_url = f"https://mineru.net/api/v4/extract-results/batch/{batch_id}"
poll_header = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {token}"
}

# 创建输出目录
output_dir = Path("outputs/mineru_results")
output_dir.mkdir(parents=True, exist_ok=True)
print(f"Output directory: {output_dir}")

attempt = 0
max_attempts = 300  # 最多轮询 300 次（2秒间隔 = 600秒 = 10分钟）
downloaded_any = False

while attempt < max_attempts:
    attempt += 1
    try:
        res = requests.get(poll_url, headers=poll_header, timeout=30)
        print(f"\n[Poll attempt {attempt}] Status: {res.status_code}")
        
        if res.status_code == 200:
            j = res.json()
            
            if isinstance(j, dict) and j.get("code") == 0:
                data_obj = j.get("data", {})
                extract_result = data_obj.get("extract_result", [])
                
                if extract_result:
                    result_item = extract_result[0]
                    state = result_item.get("state", "unknown")
                    file_name = result_item.get("file_name", "unknown")
                    data_id = result_item.get("data_id", "unknown")
                    
                    print(f"  File: {file_name} (ID: {data_id})")
                    print(f"  State: {state}")
                    
                    # 如果处理中，显示进度
                    if state == "running" or state == "converting":
                        progress = result_item.get("extract_progress", {})
                        extracted = progress.get("extracted_pages", 0)
                        total = progress.get("total_pages", 0)
                        if extracted or total:
                            print(f"  Progress: {extracted}/{total} pages extracted")
                    
                    # 如果完成或成功，尝试下载资源
                    elif state == "success" or state == "done":
                        print(f"\n✓ Processing complete!")
                        
                        # 检查是否有 full_zip_url（新版 API）
                        full_zip_url = result_item.get("full_zip_url")
                        if full_zip_url:
                            print(f"  Downloading result zip from {full_zip_url}...")
                            try:
                                zip_res = requests.get(full_zip_url, timeout=120)
                                if zip_res.status_code == 200:
                                    # 直接在内存中解压
                                    with zipfile.ZipFile(io.BytesIO(zip_res.content)) as zf:
                                        # 列出所有文件
                                        file_list = zf.namelist()
                                        print(f"  Zip contains {len(file_list)} files:")
                                        for fname in file_list[:10]:  # 只显示前10个
                                            print(f"    - {fname}")
                                        if len(file_list) > 10:
                                            print(f"    ... and {len(file_list) - 10} more files")
                                        
                                        # 解压所有文件
                                        zf.extractall(output_dir)
                                        print(f"  ✓ Extracted {len(file_list)} files to {output_dir}")
                                        downloaded_any = True
                                else:
                                    print(f"  ✗ Failed to download zip: {zip_res.status_code}")
                            except Exception as e:
                                print(f"  ✗ Zip download/extract error: {e}")
                            
                            if downloaded_any:
                                print(f"\n✓ All files downloaded to {output_dir}")
                            break
                        
                        # 旧版 API：检查 file_urls
                        file_urls = result_item.get("file_urls", {})
                        print(f"  Available formats: {list(file_urls.keys())}")
                        
                        if not file_urls:
                            print(f"  ⚠ No file_urls returned yet. Continuing polling...")
                            time.sleep(2)
                            continue
                        
                        # 下载 HTML
                        if "html" in file_urls:
                            html_url = file_urls["html"]
                            html_file = output_dir / f"{data_id}.html"
                            print(f"  Downloading HTML...")
                            try:
                                html_res = requests.get(html_url, timeout=60)
                                if html_res.status_code == 200:
                                    html_file.write_bytes(html_res.content)
                                    print(f"  ✓ HTML saved to {html_file} ({len(html_res.content)} bytes)")
                                    downloaded_any = True
                                else:
                                    print(f"  ✗ Failed to download HTML: {html_res.status_code}")
                            except Exception as e:
                                print(f"  ✗ HTML download error: {e}")
                        
                        # 下载 Markdown
                        if "md" in file_urls:
                            md_url = file_urls["md"]
                            md_file = output_dir / f"{data_id}.md"
                            print(f"  Downloading Markdown...")
                            try:
                                md_res = requests.get(md_url, timeout=60)
                                if md_res.status_code == 200:
                                    md_file.write_bytes(md_res.content)
                                    print(f"  ✓ Markdown saved to {md_file} ({len(md_res.content)} bytes)")
                                    downloaded_any = True
                                else:
                                    print(f"  ✗ Failed to download Markdown: {md_res.status_code}")
                            except Exception as e:
                                print(f"  ✗ Markdown download error: {e}")
                        
                        # 下载 JSON（如果存在）
                        if "json" in file_urls:
                            json_url = file_urls["json"]
                            json_file = output_dir / f"{data_id}.json"
                            print(f"  Downloading JSON...")
                            try:
                                json_res = requests.get(json_url, timeout=60)
                                if json_res.status_code == 200:
                                    json_file.write_bytes(json_res.content)
                                    print(f"  ✓ JSON saved to {json_file} ({len(json_res.content)} bytes)")
                                    downloaded_any = True
                                else:
                                    print(f"  ✗ Failed to download JSON: {json_res.status_code}")
                            except Exception as e:
                                print(f"  ✗ JSON download error: {e}")
                        
                        if downloaded_any:
                            print(f"\n✓ All files downloaded to {output_dir}")
                        break
                    
                    # 如果失败
                    elif state == "failed":
                        err_msg = result_item.get("err_msg", "Unknown error")
                        print(f"  ✗ Processing failed: {err_msg}")
                        break
            else:
                print(f"  ✗ API error: {j.get('msg')}")
                break
        
        time.sleep(2)
        
    except Exception as e:
        print(f"  ✗ Poll error: {e}")
        time.sleep(2)

if attempt >= max_attempts:
    print(f"\n⚠ Polling timed out after {max_attempts} attempts")