"""文档上传和解析相关API"""
import asyncio
import os
from typing import Dict, Any, Optional
import logging
import aiohttp
import re


class DocumentController:
    """文档管理控制器

    处理PDF上传、文献导入等操作
    """

    def __init__(self, parser_service):
        self.parser_service = parser_service
        self.logger = logging.getLogger(__name__)
        self.pubmed_base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

    async def upload_pdf(self, file_data: bytes, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """POST /api/documents/upload - 上传PDF文档

        Request:
        - Content-Type: multipart/form-data
        - file: PDF文件
        - user_id: UUID
        - filename: string

        Response:
        {
            "task_id": "uuid",
            "status": "Parsing",
            "message": "PDF uploaded and parsing started"
        }
        """
        # TODO: 验证文件格式
        # TODO: 调用parser_service上传和解析
        # TODO: 返回任务ID
        pass

    async def import_from_pubmed(self, pmid: str, user_id: str) -> Dict[str, Any]:
        """POST /api/documents/import/pubmed - 从PubMed导入文献

        Request Body:
        {
            "pmid": "12345678",
            "user_id": "uuid"
        }

        Response:
        {
            "task_id": "uuid",
            "pmid": "12345678",
            "status": "Parsing",
            "pubmed_data": {...}
        }
        """
        self.logger.info(f"Importing from PubMed for PMID: {pmid}, user: {user_id}")

        # 1. 验证PMID格式
        from src.utils.validators import Validator
        if not Validator.validate_pmid(pmid):
            raise ValueError(f"Invalid PMID format: {pmid}")

        # 2. 获取PubMed API数据
        pubmed_data = await self._fetch_pubmed_data(pmid)

        if not pubmed_data:
            raise ValueError(f"Failed to fetch data from PubMed for PMID: {pmid}")

        # 3. 调用parser_service创建解析任务
        try:
            if self.parser_service:
                # 保存PubMed数据到数据库或触发解析流程
                task_id = await self.parser_service.create_task_from_pubmed(
                    pubmed_data, user_id
                )
            else:
                # 模拟任务ID
                import uuid
                task_id = str(uuid.uuid4())
                self.logger.warning("Parser service not available, returning mock task ID")
        except Exception as e:
            self.logger.error(f"Failed to create task: {e}")
            task_id = "task_failed"

        return {
            "task_id": task_id,
            "pmid": pmid,
            "status": "Parsing",
            "pubmed_data": pubmed_data,
            "message": f"PubMed import initiated for PMID: {pmid}"
        }

    async def _fetch_pubmed_data(self, pmid: str) -> Optional[Dict[str, Any]]:
        """从PubMed API获取文献数据

        使用PubMed E-Utilities API:
        - esearch: 搜索文献
        - efetch: 获取详细数据
        """
        api_key = os.getenv("PUBMED_API_KEY", "")

        # 如果没有API Key，可以使用公共查询（有速率限制）
        esearch_params = {
            "db": "pubmed",
            "term": f"{pmid}[PMID]",
            "retmode": "json",
            "retmax": 1,
            "api_key": api_key if api_key else None,
        }

        try:
            async with aiohttp.ClientSession() as session:
                # 第一步：搜索文献
                self.logger.debug(f"Fetching PubMed data for PMID: {pmid}")

                # 1. 搜索获取UID列表
                response = await session.get(
                    self.pubmed_base_url,
                    params={k: v for k, v in esearch_params.items() if v is not None},
                    timeout=30
                )
                response.raise_for_status()
                search_result = await response.json()

                # 检查是否有结果
                if "esearchresult" not in search_result:
                    self.logger.error(f"No esearchresult in PubMed response for PMID: {pmid}")
                    return None

                id_list = search_result.get("esearchresult", {}).get("idlist", [])
                if not id_list:
                    self.logger.warning(f"No PubMed results found for PMID: {pmid}")
                    return None

                # 2. 获取详细数据
                efetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
                efetch_params = {
                    "db": "pubmed",
                    "id": ",".join(id_list),
                    "retmode": "xml",  # 使用XML格式获取更多字段
                    "rettype": "abstract",
                    "api_key": api_key if api_key else None,
                }

                efetch_response = await session.get(
                    efetch_url,
                    params={k: v for k, v in efetch_params.items() if v is not None},
                    timeout=30
                )
                efetch_response.raise_for_status()
                xml_data = await efetch_response.text()

                # 解析XML数据（简化版）
                pubmed_data = {
                    "pmid": pmid,
                    "title": self._extract_title_from_xml(xml_data),
                    "abstract": self._extract_abstract_from_xml(xml_data),
                    "authors": self._extract_authors_from_xml(xml_data),
                    "journal": self._extract_journal_from_xml(xml_data),
                    "publication_date": self._extract_date_from_xml(xml_data),
                    "xml_data": xml_data[:5000] if len(xml_data) > 5000 else xml_data,
                    "search_result_count": len(id_list),
                    "success": True
                }

                self.logger.info(f"Successfully fetched PubMed data for PMID: {pmid}")
                return pubmed_data

        except aiohttp.ClientError as e:
            self.logger.error(f"HTTP error fetching PubMed data for {pmid}: {e}")
        except asyncio.TimeoutError:
            self.logger.error(f"Timeout fetching PubMed data for {pmid}")
        except Exception as e:
            self.logger.error(f"Error fetching PubMed data for {pmid}: {e}")

        return None

    def _extract_title_from_xml(self, xml_data: str) -> str:
        """从PubMed XML提取标题"""
        title_match = re.search(r'<ArticleTitle>([^<]+)</ArticleTitle>', xml_data)
        return title_match.group(1) if title_match else "Title not found"

    def _extract_abstract_from_xml(self, xml_data: str) -> str:
        """从PubMed XML提取摘要"""
        abstract_match = re.search(r'<AbstractText[^>]*>([^<]+)</AbstractText>', xml_data)
        return abstract_match.group(1) if abstract_match else "Abstract not available"

    def _extract_authors_from_xml(self, xml_data: str) -> list:
        """从PubMed XML提取作者列表"""
        authors = []
        author_matches = re.findall(r'<LastName>([^<]+)</LastName>\s*<ForeName>([^<]+)</ForeName>', xml_data)
        for last_name, forename in author_matches:
            authors.append(f"{forename} {last_name}")
        return authors if authors else ["Author not specified"]

    def _extract_journal_from_xml(self, xml_data: str) -> str:
        """从PubMed XML提取期刊信息"""
        journal_match = re.search(r'<Title>([^<]+)</Title>', xml_data)
        return journal_match.group(1) if journal_match else "Journal not specified"

    def _extract_date_from_xml(self, xml_data: str) -> str:
        """从PubMed XML提取出版日期"""
        year_match = re.search(r'<PubDate>.*?<Year>(\d{4})</Year>', xml_data, re.DOTALL)
        month_match = re.search(r'<PubDate>.*?<Month>([^<]+)</Month>', xml_data, re.DOTALL)

        year = year_match.group(1) if year_match else ""
        month_raw = month_match.group(1) if month_match else ""

        # 月份转换：将月份名称转换为数字
        month_map = {
            'Jan': '01', 'January': '01',
            'Feb': '02', 'February': '02',
            'Mar': '03', 'March': '03',
            'Apr': '04', 'April': '04',
            'May': '05',
            'Jun': '06', 'June': '06',
            'Jul': '07', 'July': '07',
            'Aug': '08', 'August': '08',
            'Sep': '09', 'September': '09',
            'Oct': '10', 'October': '10',
            'Nov': '11', 'November': '11',
            'Dec': '12', 'December': '12'
        }

        month = month_map.get(month_raw, month_raw)

        if year and month:
            return f"{year}-{month}"
        elif year:
            return year
        else:
            return "Date not specified"

    async def get_parsing_status(self, task_id: str) -> Dict[str, Any]:
        """GET /api/documents/parsing/{task_id} - 获取解析状态

        Response:
        {
            "task_id": "uuid",
            "status": "Parsing | Graph_Building | Completed",
            "progress": 50,
            "chunks_created": 120
        }
        """
        self.logger.info(f"Getting parsing status for task: {task_id}")

        try:
            if self.parser_service:
                # 从parser_service获取状态
                status_data = await self.parser_service.get_task_status(task_id)
            else:
                # 返回模拟状态
                import random
                status_data = {
                    "task_id": task_id,
                    "status": random.choice(["Parsing", "Graph_Building", "Completed"]),
                    "progress": random.randint(0, 100),
                    "chunks_created": random.randint(10, 500) if random.random() > 0.5 else None,
                }
                self.logger.warning("Parser service not available, returning mock status")

            return status_data

        except Exception as e:
            self.logger.error(f"Error getting parsing status for {task_id}: {e}")
            return {
                "task_id": task_id,
                "status": "Error",
                "progress": 0,
                "error": str(e),
                "message": f"Failed to get status: {e}"
            }
