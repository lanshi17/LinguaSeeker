"""应用入口文件 - ACMG-PS3 智能评级系统

技术栈:
- 后端框架: FastAPI
- Agent框架: LangGraph
- 主力LLM: DeepSeek-V3.2
- 仲裁LLM: Claude Opus 4.5
- PDF解析: MinerU (Magic-PDF)
- 图数据库: Neo4j
- 向量数据库: Milvus/Qdrant
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from src.config.app_config import AppConfig
from src.config.database_config import DatabaseConfig
from src.utils.container import container
from src.utils.logger import Logger
from src.utils.exceptions import ACMGException
from src.api.router import api_router


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理
    
    启动时：
    - 初始化配置
    - 连接数据库（Neo4j, Milvus, PostgreSQL）
    - 初始化LLM客户端（DeepSeek, Claude）
    - 初始化MinerU解析服务
    
    关闭时：
    - 关闭所有数据库连接
    - 清理资源
    """
    # 启动初始化
    logger.info("🚀 Initializing ACMG-PS3 Intelligence System...")
    
    # 加载配置
    app_config = AppConfig.from_env()
    db_config = DatabaseConfig.from_env()
    
    # 设置日志
    Logger.setup_logging(
        log_level="DEBUG" if app_config.debug else "INFO"
    )
    
    # 初始化数据库连接
    logger.info("📊 Connecting to databases...")
    try:
        await container.initialize_databases(db_config)
        logger.info("  ✓ PostgreSQL connected")
        logger.info("  ✓ Neo4j connected")
        logger.info("  ✓ Milvus/Qdrant connected")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        raise
    
    # 初始化LLM客户端
    logger.info("🤖 Initializing LLM clients...")
    try:
        await container.initialize_llm_clients(app_config.llm)
        logger.info("  ✓ DeepSeek-V3.2 (Primary)")
        logger.info("  ✓ Claude Opus 4.5 (Arbiter)")
    except Exception as e:
        logger.error(f"❌ LLM initialization failed: {e}")
        raise
    
    # 初始化依赖注入容器
    logger.info("📦 Initializing dependency injection...")
    container.initialize()
    
    # 初始化MinerU服务
    logger.info("📄 Initializing MinerU (Magic-PDF) service...")
    try:
        await container.initialize_mineru(app_config.mineru)
        logger.info("  ✓ MinerU service ready")
    except Exception as e:
        logger.warning(f"⚠️  MinerU service unavailable: {e}")
    
    logger.info(f"✅ System started successfully!")
    logger.info(f"🌐 API: http://{app_config.host}:{app_config.port}{app_config.api_prefix}")
    logger.info(f"📚 Docs: http://{app_config.host}:{app_config.port}/docs")
    
    yield
    
    # 关闭清理
    logger.info("🛑 Shutting down...")
    container.close()
    logger.info("✅ Cleanup completed")


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    
    # 加载配置
    app_config = AppConfig.from_env()
    
    # 创建FastAPI应用
    app = FastAPI(
        title=app_config.app_name,
        description="ACMG-PS3 Variant Pathogenicity Classification System with GraphRAG",
        version=app_config.version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url=f"{app_config.api_prefix}/openapi.json"
    )
    
    # CORS中间件配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应该配置具体域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 全局异常处理
    @app.exception_handler(ACMGException)
    async def acmg_exception_handler(request: Request, exc: ACMGException):
        """处理自定义业务异常"""
        return JSONResponse(
            status_code=400,
            content={
                "error": exc.code,
                "message": exc.message,
                "detail": str(exc)
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """处理未捕获的异常"""
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "detail": str(exc) if app_config.debug else None
            }
        )
    
    # 健康检查端点
    @app.get("/health")
    async def health_check():
        """健康检查端点"""
        return {
            "status": "healthy",
            "service": app_config.app_name,
            "version": app_config.version,
            "environment": app_config.environment.value
        }
    
    @app.get("/")
    async def root():
        """根路径"""
        return {
            "message": "ACMG-PS3 Intelligence System",
            "version": app_config.version,
            "docs": "/docs",
            "health": "/health"
        }
    
    # 注册API路由
    app.include_router(
        api_router,
        prefix=app_config.api_prefix
    )
    
    return app


# 创建全局应用实例
app = create_app()


def main():
    """主函数 - 用于开发环境启动"""
    app_config = AppConfig.from_env()
    
    # 使用uvicorn启动服务
    uvicorn.run(
        "main:app",
        host=app_config.host,
        port=app_config.port,
        reload=app_config.debug,  # 开发模式下启用热重载
        log_level="debug" if app_config.debug else "info",
        access_log=True
    )


if __name__ == "__main__":
    main()
