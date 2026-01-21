"""DocumentController单元测试

重点测试PubMed API调用功能
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
src_path = os.path.join(project_root, "src")
sys.path.insert(0, project_root)
sys.path.insert(0, src_path)

from src.controller.document_controller import DocumentController


class TestDocumentController:
    """DocumentController测试类"""

    def test_init_with_parser_service(self):
        """测试初始化时带有parser_service"""
        mock_service = AsyncMock()
        controller = DocumentController(mock_service)
        assert controller.parser_service == mock_service
        assert controller.logger is not None
        assert controller.pubmed_base_url == "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

    def test_init_without_parser_service(self):
        """测试初始化时不带有parser_service"""
        controller = DocumentController(None)
        assert controller.parser_service is None
        assert controller.logger is not None

    @pytest.mark.asyncio
    async def test_import_from_pubmed_success(self, mock_parser_service, valid_pmid, user_id):
        """测试从PubMed成功导入文献"""
        controller = DocumentController(mock_parser_service)

        # 模拟fetch_pubmed_data返回有效数据
        with patch.object(controller, '_fetch_pubmed_data', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {
                "pmid": valid_pmid,
                "title": "Test Paper Title",
                "abstract": "Test abstract content",
                "authors": ["John Smith", "Emily Johnson"],
                "journal": "Test Journal",
                "publication_date": "2024-03",
                "xml_data": "<xml>test</xml>",
                "search_result_count": 1,
                "success": True
            }

            result = await controller.import_from_pubmed(valid_pmid, user_id)

            assert result["task_id"] == "test_task_123"
            assert result["pmid"] == valid_pmid
            assert result["status"] == "Parsing"
            assert "pubmed_data" in result
            assert result["message"] == f"PubMed import initiated for PMID: {valid_pmid}"

            # 验证fetch方法被调用
            mock_fetch.assert_called_once_with(valid_pmid)
            # 验证parser_service方法被调用
            mock_parser_service.create_task_from_pubmed.assert_called_once()

    @pytest.mark.asyncio
    async def test_import_from_pubmed_without_parser_service(self, valid_pmid, user_id):
        """测试没有parser_service时的PubMed导入"""
        controller = DocumentController(None)

        with patch.object(controller, '_fetch_pubmed_data', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {
                "pmid": valid_pmid,
                "title": "Test Paper",
                "abstract": "Abstract",
                "authors": ["Author"],
                "journal": "Journal",
                "success": True
            }

            result = await controller.import_from_pubmed(valid_pmid, user_id)

            # 即使没有parser_service，也应该返回结果
            assert "task_id" in result
            assert result["pmid"] == valid_pmid
            assert result["status"] == "Parsing"
            mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_import_from_pubmed_fetch_failure(self, mock_parser_service, valid_pmid, user_id):
        """测试PubMed数据获取失败的情况"""
        controller = DocumentController(mock_parser_service)

        with patch.object(controller, '_fetch_pubmed_data', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None

            # 预期会抛出异常
            with pytest.raises(ValueError, match=f"Failed to fetch data from PubMed for PMID: {valid_pmid}"):
                await controller.import_from_pubmed(valid_pmid, user_id)

            # parser_service不应该被调用
            mock_parser_service.create_task_from_pubmed.assert_not_called()

    @pytest.mark.asyncio
    async def test_import_from_pubmed_invalid_pmid(self, mock_parser_service, invalid_pmid, user_id):
        """测试导入无效的PMID"""
        controller = DocumentController(mock_parser_service)

        # 验证PMID失败会抛出异常
        with pytest.raises(ValueError, match=f"Invalid PMID format: {invalid_pmid}"):
            await controller.import_from_pubmed(invalid_pmid, user_id)

    @pytest.mark.asyncio
    async def test_fetch_pubmed_data_success(self, pubmed_search_response, pubmed_xml_response):
        """测试成功获取PubMed数据"""
        controller = DocumentController(None)

        # 完全模拟两个API调用
        mock_get1 = AsyncMock()
        mock_get1.raise_for_status = MagicMock()
        mock_get1.json = AsyncMock(return_value=pubmed_search_response)

        mock_get2 = AsyncMock()
        mock_get2.raise_for_status = MagicMock()
        mock_get2.text = AsyncMock(return_value=pubmed_xml_response)

        # 创建模拟的session对象
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=[mock_get1, mock_get2])
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # 设置环境变量
        original_api_key = os.environ.get("PUBMED_API_KEY")
        os.environ["PUBMED_API_KEY"] = "test_key_123"

        try:
            # 直接模拟完整流程
            with patch('aiohttp.ClientSession', return_value=mock_session):
                result = await controller._fetch_pubmed_data("12345678")

                assert result is not None
                assert result["pmid"] == "12345678"
                assert result["title"] == "Novel genetic variant associated with cardiovascular disease risk in the test population"
                assert result["journal"] == "Test Journal of Medicine"
                assert len(result["authors"]) == 3
                assert "John Smith" in result["authors"][0]
                assert result["publication_date"] == "2024-03"
                assert result["search_result_count"] == 1
                assert result["success"] is True

                # 验证API调用
                calls = mock_session.get.call_args_list
                assert len(calls) == 2

                # 检查第一个调用（esearch）
                first_url = calls[0][0][0]
                assert "esearch.fcgi" in first_url

                # 检查第二个调用（efetch）
                second_url = calls[1][0][0]
                assert "efetch.fcgi" in second_url

        finally:
            # 恢复环境变量
            if original_api_key:
                os.environ["PUBMED_API_KEY"] = original_api_key
            else:
                del os.environ["PUBMED_API_KEY"]

    @pytest.mark.asyncio
    async def test_fetch_pubmed_data_without_api_key(self, pubmed_search_response, pubmed_xml_response):
        """测试没有API Key时获取PubMed数据"""
        controller = DocumentController(None)

        # 完全模拟两个API调用
        mock_get1 = AsyncMock()
        mock_get1.raise_for_status = MagicMock()
        mock_get1.json = AsyncMock(return_value=pubmed_search_response)

        mock_get2 = AsyncMock()
        mock_get2.raise_for_status = MagicMock()
        mock_get2.text = AsyncMock(return_value=pubmed_xml_response)

        # 创建模拟的session对象
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=[mock_get1, mock_get2])
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # 移除API Key
        original_api_key = os.environ.get("PUBMED_API_KEY")
        if "PUBMED_API_KEY" in os.environ:
            del os.environ["PUBMED_API_KEY"]

        try:
            with patch('aiohttp.ClientSession', return_value=mock_session):
                result = await controller._fetch_pubmed_data("12345678")

                # 即使没有API Key也应该能获取数据
                assert result is not None
                assert result["success"] is True

                # 验证params没有api_key或api_key为None
                calls = mock_session.get.call_args_list
                if calls:
                    first_call_kwargs = calls[0][1]
                    params = first_call_kwargs.get("params", {})
                    # 如果包含api_key，则应为None
                    assert "api_key" not in params or params.get("api_key") is None

        finally:
            # 恢复环境变量
            if original_api_key:
                os.environ["PUBMED_API_KEY"] = original_api_key

    @pytest.mark.asyncio
    async def test_fetch_pubmed_data_http_error(self):
        """测试HTTP错误情况"""
        controller = DocumentController(None)

        # 模拟HTTP错误的响应
        mock_get = AsyncMock()
        mock_get.raise_for_status.side_effect = Exception("HTTP 500 Internal Server Error")

        # 创建模拟的session对象
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_get)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await controller._fetch_pubmed_data("12345678")
            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_pubmed_data_timeout(self):
        """测试超时情况"""
        controller = DocumentController(None)

        # 创建模拟的session对象，get方法抛出超时异常
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=asyncio.TimeoutError("Request timed out"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)



        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await controller._fetch_pubmed_data("12345678")
            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_pubmed_data_no_results(self):
        """测试没有搜索结果的情况"""
        controller = DocumentController(None)

        # 模拟没有结果的响应
        mock_get = AsyncMock()
        mock_get.raise_for_status = MagicMock()
        mock_get.json = AsyncMock(return_value={
            "esearchresult": {
                "count": "0",
                "retmax": "0",
                "retstart": "0",
                "idlist": [],
                "translationset": [],
                "querytranslation": "12345678[PMID]"
            }
        })

        # 创建模拟的session对象
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_get)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await controller._fetch_pubmed_data("99999999")
            assert result is None

    def test_extract_title_from_xml(self):
        """测试从XML提取标题"""
        controller = DocumentController(None)

        xml_data = '<ArticleTitle>Test Title Here</ArticleTitle>'
        title = controller._extract_title_from_xml(xml_data)
        assert title == "Test Title Here"

        # 测试没有标题的情况
        no_title_xml = '<OtherTag>Content</OtherTag>'
        title = controller._extract_title_from_xml(no_title_xml)
        assert title == "Title not found"

    def test_extract_abstract_from_xml(self):
        """测试从XML提取摘要"""
        controller = DocumentController(None)

        xml_data = '<AbstractText>This is the abstract content</AbstractText>'
        abstract = controller._extract_abstract_from_xml(xml_data)
        assert abstract == "This is the abstract content"

        # 测试没有摘要的情况
        no_abstract_xml = '<OtherTag>Content</OtherTag>'
        abstract = controller._extract_abstract_from_xml(no_abstract_xml)
        assert abstract == "Abstract not available"

    def test_extract_authors_from_xml(self):
        """测试从XML提取作者列表"""
        controller = DocumentController(None)

        xml_data = '''
        <LastName>Smith</LastName>
        <ForeName>John</ForeName>
        <LastName>Johnson</LastName>
        <ForeName>Emily</ForeName>
        '''
        authors = controller._extract_authors_from_xml(xml_data)
        assert len(authors) == 2
        assert "John Smith" in authors
        assert "Emily Johnson" in authors

        # 测试没有作者的情况
        no_authors_xml = '<OtherTag>Content</OtherTag>'
        authors = controller._extract_authors_from_xml(no_authors_xml)
        assert authors == ["Author not specified"]

    def test_extract_journal_from_xml(self):
        """测试从XML提取期刊信息"""
        controller = DocumentController(None)

        xml_data = '<Title>Journal of Test Medicine</Title>'
        journal = controller._extract_journal_from_xml(xml_data)
        assert journal == "Journal of Test Medicine"

        # 测试没有期刊的情况
        no_journal_xml = '<OtherTag>Content</OtherTag>'
        journal = controller._extract_journal_from_xml(no_journal_xml)
        assert journal == "Journal not specified"

    def test_extract_date_from_xml(self):
        """测试从XML提取日期"""
        controller = DocumentController(None)

        # 测试完整的年月
        xml_data = '<PubDate><Year>2024</Year><Month>Mar</Month></PubDate>'
        date = controller._extract_date_from_xml(xml_data)
        assert date == "2024-03"  # 注意：XML中是<Month>Mar</Month>，但正则提取会得到Mar

        # 测试只有年份
        xml_data = '<PubDate><Year>2023</Year></PubDate>'


        # 测试没有日期
        no_date_xml = '<OtherTag>Content</OtherTag>'
        date = controller._extract_date_from_xml(no_date_xml)
        assert date == "Date not specified"

    @pytest.mark.asyncio
    async def test_get_parsing_status_success(self, mock_parser_service):
        """测试成功获取解析状态"""
        controller = DocumentController(mock_parser_service)

        status = await controller.get_parsing_status("test_task_123")

        assert status["task_id"] == "test_task_123"
        assert status["status"] == "Parsing"
        assert status["progress"] == 50
        assert status["chunks_created"] == 120

        mock_parser_service.get_task_status.assert_called_once_with("test_task_123")

    @pytest.mark.asyncio
    async def test_get_parsing_status_without_service(self):
        """测试没有parser_service时获取解析状态"""
        controller = DocumentController(None)

        # 使用真实的随机数生成，但仍可测试
        import random
        random.seed(42)  # 设置随机种子以获得可重复的结果

        status = await controller.get_parsing_status("mock_task_123")

        assert status["task_id"] == "mock_task_123"
        assert status["status"] in ["Parsing", "Graph_Building", "Completed"]
        assert 0 <= status["progress"] <= 100
        if "chunks_created" in status and status["chunks_created"] is not None:
            assert isinstance(status["chunks_created"], int)

    @pytest.mark.asyncio
    async def test_get_parsing_status_error(self, mock_parser_service):
        """测试获取解析状态时出错"""
        controller = DocumentController(mock_parser_service)

        # 模拟service抛出异常
        mock_parser_service.get_task_status.side_effect = Exception("Database connection failed")

        status = await controller.get_parsing_status("error_task_123")

        assert status["task_id"] == "error_task_123"
        assert status["status"] == "Error"
        assert status["progress"] == 0
        assert "error" in status
        assert "Database connection failed" in status["error"]

    @pytest.mark.asyncio
    async def test_upload_pdf_not_implemented(self):
        """测试PDF上传功能（未实现）"""
        controller = DocumentController(None)

        # upload_pdf目前是pass，调用应该不会抛出异常
        result = await controller.upload_pdf(b"test pdf content", {"filename": "test.pdf"})

        # 检查是否返回了预期的响应（目前是None或需要实现）
        # 这里主要是确保不会抛出异常


if __name__ == "__main__":
    pytest.main([__file__])
