import pytest
from src.domain.mineru import MinerUComponent
from pathlib import Path
from loguru import logger
from src.utils import file_utils
 
mineru = MinerUComponent()



@pytest.mark.unit
def test_minerU_pipeline_on_sample_pdf():
    import os
    #禁用代理 unset http_proxy https_proxy all_proxy  
    os.environ.pop("http_proxy", None)
    os.environ.pop("https_proxy", None)
    os.environ.pop("all_proxy", None)    
    #测试单个文件
    file_path=Path(os.getcwd() + "/knowledge_docs/Richards 等 - 2015 - Standards and guidelines for the interpretation of sequence variants a joint consensus recommendati.pdf")
    parse_folder_path = mineru.minerU_pipeline([str(file_path)])
    assert isinstance(parse_folder_path, str)
    # 文件夹列表包含.md文件和图片文件
    all_files = file_utils.get_all_files_in_directory(parse_folder_path)
    md_files = [f for f in all_files if f.endswith(".md")]
    image_files = [f for f in all_files if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp"))]
    assert len(md_files) > 0, "未找到.md文件"
    assert len(image_files) > 0, "未找到图片文件"
    logger.debug(f"找到的.md文件: {md_files}")
    logger.debug(f"找到的图片文件: {image_files}")
    logger.success("minerU_pipeline 解析测试通过。")
    
#测试处理不存在的文件
@pytest.mark.unit
def test_minerU_pipeline_on_nonexistent_file():
    import os
    #禁用代理 unset http_proxy https_proxy all_proxy  
    os.environ.pop("http_proxy", None)
    os.environ.pop("https_proxy", None)
    os.environ.pop("all_proxy", None)    
    #测试单个文件
    file_path=Path(os.getcwd() + "/demo_pdf/nonexistent_file.pdf")
    parse_folder_path = mineru.minerU_pipeline([str(file_path)])
    assert parse_folder_path is None, "预期返回 None 但实际返回了路径"
    logger.success("minerU_pipeline 处理不存在文件测试通过。")
    
#测试处理空文件列表
@pytest.mark.unit
def test_minerU_pipeline_on_empty_file_list():
    import os
    #禁用代理 unset http_proxy https_proxy all_proxy  
    os.environ.pop("http_proxy", None)
    os.environ.pop("https_proxy", None)
    os.environ.pop("all_proxy", None)    
    #测试空文件列表
    parse_folder_path = mineru.minerU_pipeline([])
    assert parse_folder_path is None, "预期返回 None 但实际返回了路径"
    logger.success("minerU_pipeline 处理空文件列表测试通过。")
    
#测试处理非支持格式文件
@pytest.mark.unit
def test_minerU_pipeline_on_unsupported_file_format():
    import os
    #禁用代理 unset http_proxy https_proxy all_proxy  
    os.environ.pop("http_proxy", None)
    os.environ.pop("https_proxy", None)
    os.environ.pop("all_proxy", None)    
    #测试非支持格式文件
    file_path=Path(os.getcwd() + "/demo_pdf/unsupported_file.txt")
    parse_folder_path = mineru.minerU_pipeline([str(file_path)])
    assert parse_folder_path is None, "预期返回 None 但实际返回了路径"
    logger.success("minerU_pipeline 处理非支持格式文件测试通过。")
    
#测试处理批量文件
@pytest.mark.unit
def test_minerU_pipeline_on_batch_files():
    import os
    #禁用代理 unset http_proxy https_proxy all_proxy  
    os.environ.pop("http_proxy", None)
    os.environ.pop("https_proxy", None)
    os.environ.pop("all_proxy", None)    
    #测试批量文件
    file1=Path(os.getcwd() + "/demo_pdf/test_ja01.pdf")
    file2=Path(os.getcwd() + "/demo_pdf/test_de01.pdf")
    parse_folder_path = mineru.minerU_pipeline([str(file1), str(file2)])
    assert isinstance(parse_folder_path, str)
    # 文件夹列表包含.md文件和图片文件
    all_files = file_utils.get_all_files_in_directory(parse_folder_path)
    md_files = [f for f in all_files if f.endswith(".md")]
    image_files = [f for f in all_files if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp"))]
    assert len(md_files) > 0, "未找到.md文件"
    assert len(image_files) > 0, "未找到图片文件"
    logger.debug(f"找到的.md文件: {md_files}")
    logger.debug(f"找到的图片文件: {image_files}")
    logger.success("minerU_pipeline 批量文件解析测试通过。")
    
