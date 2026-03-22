# API 层

API 层负责处理 HTTP 请求，包括路由定义、请求验证、依赖注入和响应格式化。

## 目录结构

```
api/
├── __init__.py
├── dependencies.py       # 依赖注入和错误处理
└── routes/
    ├── __init__.py
    ├── core.py           # 核心路由 (健康检查、文件上传)
    ├── task.py           # 任务管理路由
    ├── evidence.py       # 证据查询路由
    └── stream.py         # 流式响应路由
```

## 职责

API 层的主要职责：

1. **路由定义**: 定义 HTTP 端点和请求方法
2. **请求验证**: 验证请求参数和请求体
3. **依赖注入**: 注入服务依赖
4. **错误处理**: 统一错误处理和响应格式化
5. **文档生成**: 自动生成 OpenAPI/Swagger 文档

## 架构位置

```
HTTP Request
    ↓
API Layer (路由 + 验证)
    ↓
Presentation Layer (控制器)
    ↓
Application Layer (服务)
    ↓
Domain Layer (业务逻辑)
```

## 核心组件

### dependencies.py

依赖注入和错误处理工具：

```python
from src.api.dependencies import build_log_link, contract_http_exception

# 构建日志链接
log_link = build_log_link(request_id)

# 统一错误处理
raise contract_http_exception(503, "INTERNAL_ERROR", "Service unavailable")
```

### routes/core.py

核心路由，包括：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/pdf/check_hash` | GET | PDF 哈希检查 |
| `/pdf/upload` | POST | PDF 上传 |
| `/results/{document_id}/{object_path}` | GET | 下载处理结果 |
| `/logs/reissue` | GET | 重新生成日志链接 |

### routes/task.py

任务管理路由：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/tasks` | POST | 创建任务 |
| `/tasks/{task_id}` | GET | 获取任务状态 |
| `/tasks/{task_id}/cancel` | POST | 取消任务 |

### routes/evidence.py

证据查询路由：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/evidence/search` | POST | 证据检索 |
| `/evidence/{evidence_id}` | GET | 获取证据详情 |
| `/evidence/aggregate` | POST | 证据聚合 |

### routes/stream.py

流式响应路由：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/stream/{task_id}` | GET | 流式任务状态推送 |

## 使用示例

### 定义新路由

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

class CreateTaskRequest(BaseModel):
    document_id: str = Field(..., description="Document ID")
    gene_symbol: str = Field(..., description="Gene symbol")
    variant: str = Field(..., description="Variant name")

class CreateTaskResponse(BaseModel):
    task_id: str
    status: str

@router.post(
    "/tasks",
    tags=["Task"],
    summary="Create task",
    description="Create a new evidence extraction task.",
    response_model=CreateTaskResponse,
)
async def create_task(request: CreateTaskRequest):
    """Create a new evidence extraction task."""
    # 实现逻辑
    pass
```

### 依赖注入

```python
from fastapi import Depends
from src.application.services.document_service import DocumentService

def get_document_service() -> DocumentService:
    """获取文档服务实例"""
    return DocumentService()

@router.post("/documents")
async def upload_document(
    service: DocumentService = Depends(get_document_service)
):
    """上传文档"""
    pass
```

### 错误处理

```python
from src.api.dependencies import contract_http_exception

@router.get("/resource/{id}")
async def get_resource(id: str):
    resource = await find_resource(id)
    if not resource:
        raise contract_http_exception(
            404, 
            "RESOURCE_NOT_FOUND", 
            f"Resource {id} not found"
        )
    return resource
```

## 响应模型

使用 Pydantic 定义响应模型：

```python
from pydantic import BaseModel, Field

class HealthResponse(BaseModel):
    status: str = Field(..., description="Overall health status.")
    details: dict[str, bool] = Field(..., description="Dependency status map.")
    timestamp: str = Field(..., description="UTC timestamp in ISO-8601 format.")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "ok",
                "details": {"postgres": True, "redis": True, "minio": True},
                "timestamp": "2026-02-10T08:00:00+00:00",
            }
        }
```

## 标签分类

API 端点按功能分类：

| 标签 | 说明 |
|------|------|
| `Health` | 健康检查 |
| `File` | 文件操作 |
| `Task` | 任务管理 |
| `Evidence` | 证据查询 |
| `Graph` | 图谱查询 |
| `Stream` | 流式响应 |

## 最佳实践

### 1. 请求验证

始终使用 Pydantic 模型验证请求：

```python
# ✅ 推荐
@router.post("/tasks")
async def create_task(request: CreateTaskRequest):
    pass

# ❌ 不推荐
@router.post("/tasks")
async def create_task(request: dict):
    pass
```

### 2. 错误处理

使用统一的错误处理函数：

```python
# ✅ 推荐
raise contract_http_exception(500, "INTERNAL_ERROR", "Error message")

# ❌ 不推荐
raise HTTPException(status_code=500, detail="Error message")
```

### 3. 文档注释

为每个端点添加清晰的文档：

```python
@router.get(
    "/health",
    tags=["Health"],
    summary="Check service health",
    description="Check database/queue/storage connectivity and report a combined status.",
    response_model=HealthResponse,
)
async def health_check():
    """Return aggregated status for core dependencies."""
    pass
```

### 4. 依赖注入

使用依赖注入解耦服务：

```python
# 定义依赖
def get_service() -> Service:
    return Service()

# 使用依赖
@router.get("/resource")
async def get_resource(service: Service = Depends(get_service)):
    pass
```

## 测试

### 单元测试

```python
import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

### 集成测试

```python
@pytest.mark.integration
async def test_pdf_upload():
    with open("test.pdf", "rb") as f:
        response = client.post("/api/pdf/upload", files={"file": f})
    assert response.status_code == 200
    assert "task_id" in response.json()
```

## 相关文档

- [后端 README](../../README.md)
- [应用层 README](../../../README.md)
- [API 文档](http://localhost:8000/docs)

---

**最后更新**: 2026-03-22 (v3.0)
