"""API路由聚合"""

from fastapi import APIRouter

from src.controller.task_controller import TaskController
from src.controller.document_controller import DocumentController
from src.controller.variant_controller import VariantController
from src.controller.report_controller import ReportController
from src.controller.graph_controller import GraphController
from src.controller.translation_controller import router as translation_router


# 创建主路由
api_router = APIRouter()


# ==================== 任务管理路由 ====================
task_router = APIRouter(prefix="/tasks", tags=["Tasks"])


@task_router.post("/")
async def create_task(request_data: dict):
    """创建新任务"""
    controller = TaskController(None)  # TODO: 注入service
    return await controller.create_task(request_data)


@task_router.get("/{task_id}")
async def get_task(task_id: str):
    """获取任务详情"""
    controller = TaskController(None)
    return await controller.get_task(task_id)


@task_router.get("/")
async def list_tasks(user_id: str, limit: int = 10, offset: int = 0):
    """获取任务列表"""
    controller = TaskController(None)
    return await controller.list_tasks(user_id, limit, offset)


@task_router.delete("/{task_id}")
async def cancel_task(task_id: str):
    """取消任务"""
    controller = TaskController(None)
    return await controller.cancel_task(task_id)


# ==================== 文档管理路由 ====================
document_router = APIRouter(prefix="/documents", tags=["Documents"])


@document_router.post("/upload")
async def upload_pdf(file_data: bytes, metadata: dict):
    """上传PDF文档"""
    controller = DocumentController(None)
    return await controller.upload_pdf(file_data, metadata)


@document_router.post("/import/pubmed")
async def import_from_pubmed(pmid: str, user_id: str):
    """从PubMed导入文献"""
    controller = DocumentController(None)
    return await controller.import_from_pubmed(pmid, user_id)


@document_router.get("/parsing/{task_id}")
async def get_parsing_status(task_id: str):
    """获取解析状态"""
    controller = DocumentController(None)
    return await controller.get_parsing_status(task_id)


# ==================== 变异查询路由 ====================
variant_router = APIRouter(prefix="/variants", tags=["Variants"])


@variant_router.post("/query")
async def query_variant(query_data: dict):
    """查询变异并获取评级"""
    controller = VariantController(None, None)
    return await controller.query_variant(query_data)


@variant_router.get("/rating/{task_id}")
async def get_variant_rating(task_id: str):
    """获取变异评级结果"""
    controller = VariantController(None, None)
    return await controller.get_variant_rating(task_id)


@variant_router.post("/evidence/search")
async def search_evidence(search_query: dict):
    """混合检索证据"""
    controller = VariantController(None, None)
    return await controller.search_evidence(search_query)


@variant_router.get("/evidence-chain")
async def get_evidence_chain(gene_symbol: str, cdna_change: str):
    """获取完整证据链"""
    controller = VariantController(None, None)
    return await controller.get_evidence_chain(gene_symbol, cdna_change)


# ==================== 报告管理路由 ====================
report_router = APIRouter(prefix="/reports", tags=["Reports"])


@report_router.get("/{report_id}")
async def get_report(report_id: str):
    """获取报告详情"""
    controller = ReportController(None)
    return await controller.get_report(report_id)


@report_router.get("/task/{task_id}")
async def get_report_by_task(task_id: str):
    """根据任务ID获取报告"""
    controller = ReportController(None)
    return await controller.get_report_by_task(task_id)


@report_router.get("/{report_id}/export")
async def export_report(report_id: str, format: str = "json"):
    """导出报告"""
    controller = ReportController(None)
    return await controller.export_report(report_id, format)


@report_router.get("/")
async def list_reports(user_id: str, limit: int = 10, offset: int = 0):
    """获取报告列表"""
    controller = ReportController(None)
    return await controller.list_reports(user_id, limit, offset)


# ==================== 知识图谱路由 ====================
graph_router = APIRouter(prefix="/graph", tags=["Knowledge Graph"])


@graph_router.post("/query")
async def query_graph(cypher_query: str):
    """执行Cypher查询"""
    controller = GraphController(None, None)
    return await controller.query_graph(cypher_query)


@graph_router.post("/nl-query")
async def natural_language_query(nl_query: str):
    """自然语言查询图谱"""
    controller = GraphController(None, None)
    return await controller.natural_language_query(nl_query)


@graph_router.get("/subgraph")
async def get_subgraph(node_id: str, node_type: str, depth: int = 2):
    """获取子图"""
    controller = GraphController(None, None)
    return await controller.get_subgraph(node_id, node_type, depth)

@graph_router.get("/stats")
async def get_graph_statistics():
    """获取图谱统计信息"""
    controller = GraphController(None, None)
    return await controller.get_graph_statistics()


# ==================== 翻译管理路由 ====================
api_router.include_router(translation_router)

# ==================== 注册所有路由 ====================
api_router.include_router(task_router)
api_router.include_router(document_router)
api_router.include_router(variant_router)
api_router.include_router(report_router)
api_router.include_router(graph_router)
