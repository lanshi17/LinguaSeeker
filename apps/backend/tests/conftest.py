"""测试配置文件

为PubMed API测试提供公共配置和fixtures
"""
import os
import sys
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_path))

# 测试环境变量
os.environ["PUBMED_API_KEY"] = "test_api_key_12345"
os.environ["PUBMED_BASE_URL"] = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
os.environ["TEST_ENV"] = "true"

@pytest.fixture
def event_loop():
    """创建事件循环fixture"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_parser_service():
    """创建模拟的parser_service"""
    mock_service = AsyncMock()

    # 设置模拟方法
    mock_service.create_task_from_pubmed = AsyncMock(return_value="test_task_123")
    mock_service.get_task_status = AsyncMock(return_value={
        "task_id": "test_task_123",
        "status": "Parsing",
        "progress": 50,
        "chunks_created": 120
    })
    mock_service.upload_and_parse_pdf = AsyncMock(return_value={
        "task_id": "pdf_task_123",
        "status": "Processing"
    })

    return mock_service

@pytest.fixture
def mock_logger():
    """创建模拟的logger"""
    logger = MagicMock()
    logger.info = MagicMock()
    logger.debug = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    return logger

@pytest.fixture
def mock_aiohttp_response():
    """创建模拟的aiohttp响应"""

    def create_response(status=200, json_data=None, text_data=None, raise_for_status=None):
        response = AsyncMock()

        if raise_for_status is not None:
            response.raise_for_status.side_effect = raise_for_status
        else:
            response.raise_for_status = MagicMock()

        if json_data:
            response.json = AsyncMock(return_value=json_data)
        else:
            response.json = AsyncMock()

        if text_data:
            response.text = AsyncMock(return_value=text_data)
        else:
            response.text = AsyncMock()

        response.status = status

        return response

    return create_response

@pytest.fixture
def pubmed_xml_response():
    """PubMed API的模拟XML响应"""
    return """<?xml version="1.0" ?>
<!DOCTYPE PubmedArticleSet PUBLIC "-//NLM//DTD PubMedArticle, 1st January 2019//EN" "https://dtd.nlm.nih.gov/ncbi/pubmed/out/pubmed_190101.dtd">
<PubmedArticleSet>
    <PubmedArticle>
        <MedlineCitation Status="MEDLINE" Owner="NLM">
            <PMID Version="1">12345678</PMID>
            <DateCreated>
                <Year>2024</Year>
                <Month>01</Month>
                <Day>15</Day>
            </DateCreated>
            <Article PubModel="Print">
                <Journal>
                    <ISSN IssnType="Print">1234-5678</ISSN>
                    <JournalIssue CitedMedium="Print">
                        <Volume>12</Volume>
                        <Issue>3</Issue>
                        <PubDate>
                            <Year>2024</Year>
                            <Month>Mar</Month>
                        </PubDate>
                    </JournalIssue>
                    <Title>Test Journal of Medicine</Title>
                    <ISOAbbreviation>Test J Med</ISOAbbreviation>
                </Journal>
                <ArticleTitle>Novel genetic variant associated with cardiovascular disease risk in the test population</ArticleTitle>
                <Pagination>
                    <MedlinePgn>123-130</MedlinePgn>
                </Pagination>
                <Abstract>
                    <AbstractText Label="BACKGROUND" NlmCategory="BACKGROUND">This study investigates novel genetic variants.</AbstractText>
                    <AbstractText Label="METHODS" NlmCategory="METHODS">We conducted genome-wide association studies.</AbstractText>
                    <AbstractText Label="RESULTS" NlmCategory="RESULTS">We identified a significant association (p &lt; 5×10⁻⁸).</AbstractText>
                    <AbstractText Label="CONCLUSIONS" NlmCategory="CONCLUSIONS">Our findings highlight important genetic factors.</AbstractText>
                </Abstract>
                <AuthorList CompleteYN="Y">
                    <Author ValidYN="Y">
                        <LastName>Smith</LastName>
                        <ForeName>John</ForeName>
                        <Initials>J</Initials>
                        <AffiliationInfo>
                            <Affiliation>University of Test, Department of Genetics</Affiliation>
                        </AffiliationInfo>
                    </Author>
                    <Author ValidYN="Y">
                        <LastName>Johnson</LastName>
                        <ForeName>Emily</ForeName>
                        <Initials>E</Initials>
                        <AffiliationInfo>
                            <Affiliation>Test Medical Center, Division of Cardiology</Affiliation>
                        </AffiliationInfo>
                    </Author>
                    <Author ValidYN="Y">
                        <LastName>Chen</LastName>
                        <ForeName>Wei</ForeName>
                        <Initials>W</Initials>
                        <AffiliationInfo>
                            <Affiliation>Institute of Genetic Medicine</Affiliation>
                        </AffiliationInfo>
                    </Author>
                </AuthorList>
                <Language>eng</Language>
                <PublicationTypeList>
                    <PublicationType UI="D016428">Journal Article</PublicationType>
                </PublicationTypeList>
            </Article>
        </MedlineCitation>
    </PubmedArticle>
</PubmedArticleSet>"""

@pytest.fixture
def pubmed_search_response():
    """PubMed搜索API的模拟JSON响应"""
    return {
        "header": {
            "type": "esearch",
            "version": "0.3"
        },
        "esearchresult": {
            "count": "1",
            "retmax": "1",
            "retstart": "0",
            "idlist": ["12345678"],
            "translationset": [],
            "querytranslation": "12345678[PMID]"
        }
    }

@pytest.fixture
def valid_pmid():
    """有效的PMID"""
    return "12345678"

@pytest.fixture
def invalid_pmid():
    """无效的PMID"""
    return "abc123"

@pytest.fixture
def user_id():
    """测试用户ID"""
    return "test_user_123"
