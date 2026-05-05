# Model Server

ACMG-Lingua 的本地模型推理微服务。提供 Embedding、Rerank、LLM（规划中）的 OpenAI 兼容 API，统一运行在 8001 端口。

## 快速启动

```bash
cd services/model-server

# 安装依赖（复用 backend venv）
uv pip install sentence-transformers torch --index-url https://download.pytorch.org/whl/cpu
uv pip install loguru

# 启动（默认 8001）
uv run python main.py

# 自定义端口
uv run python main.py --port 8002
```

模型在首次请求时懒加载，启动速度 < 1s。

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查，返回各模型就绪状态 |
| `POST` | `/v1/embeddings` | 向量嵌入 |
| `POST` | `/v1/rerank` | 重排序 |
| `POST` | `/v1/chat/completions` | LLM 对话（需配置 `llm_model_id`） |

### Embedding

```bash
curl http://localhost:8001/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"input": ["hello", "world"]}'
```

### Rerank

```bash
curl http://localhost:8001/v1/rerank \
  -H 'Content-Type: application/json' \
  -d '{"query": "deep learning", "documents": ["neural networks", "weather"], "top_k": 2}'
```

### Health

```json
// GET /health
{
  "status": "ok",
  "models": {
    "embedding": true,
    "rerank": true
  }
}
```

## 项目结构

```
app/
├── config.py              # 配置（读 .env.local / 环境变量）
├── enums/model_type.py    # 模型类型枚举
├── models/schemas.py      # 请求/响应体（Pydantic，全层共享）
├── utils/logger.py        # loguru 日志 + 请求监控中间件
├── domain/                # 推理逻辑
│   ├── base.py            # BaseModelService 抽象基类
│   ├── embedding.py       # EmbeddingService
│   ├── rerank.py          # RerankService
│   └── llm.py             # LLMService（占位）
└── api/                   # 路由层
    ├── health.py
    ├── embedding.py
    ├── rerank.py
    └── chat.py
```

**分层职责：**

- `api/` — HTTP 路由，参数校验，调用 domain
- `domain/` — 模型加载与推理，不依赖 FastAPI
- `models/` — 数据契约，所有层引用
- `enums/` — 状态枚举
- `utils/` — 日志、中间件等公共组件
- `config.py` — 环境配置，单一来源
- `main.py` — 组装入口，把 domain bind 到 api

## 增减模型

### 新增一个模型（以 Embedding 为例）

**1. domain — 写推理服务**

```python
# app/domain/my_model.py
from app.domain.base import BaseModelService

class MyModelService(BaseModelService):
    def __init__(self, model_id: str = "org/model-name"):
        super().__init__(model_id)

    def _load(self):
        # 加载模型到 self._model
        ...

    def infer(self, **kwargs):
        self.ensure_loaded()
        # 推理逻辑
        ...
```

**2. models — 定义请求/响应体**

```python
# app/models/schemas.py 中追加
class MyModelRequest(BaseModel):
    input: str

class MyModelResponse(BaseModel):
    output: str
    model: str
```

**3. api — 写路由**

```python
# app/api/my_model.py
from fastapi import APIRouter
from app.models import MyModelRequest, MyModelResponse

router = APIRouter(tags=["my-model"])
_service = None

def bind(service):
    global _service
    _service = service

@router.post("/v1/my-model", response_model=MyModelResponse)
def run(req: MyModelRequest):
    assert _service is not None
    result = _service.infer(input=req.input)
    return MyModelResponse(output=result, model=_service.model_id)
```

**4. main.py — 组装**

```python
from app.domain.my_model import MyModelService
from app.api import my_model

_svc = MyModelService(model_id="org/model-name")
my_model.bind(_svc)

# include_router
app.include_router(my_model.router)

# 注册到 health
health.register_services({"my-model": _svc})
```

### 移除一个模型

反向操作：删除 domain → api route → main.py 中的 bind / include_router / register_services。

## 配置

通过环境变量或 `.env.local` 配置（与 backend 共享同一文件）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `8001` | 监听端口 |
| `HF_HOME` | `~/.cache/huggingface/hub` | HuggingFace 模型缓存 |
| `EMBEDDING_MODEL_ID` | `Qwen/Qwen3-Embedding-0.6B` | Embedding 模型 |
| `EMBEDDING_DIMENSION` | `1024` | 向量维度 |
| `RERANK_MODEL_ID` | `BAAI/bge-reranker-v2-m3` | Rerank 模型 |
| `LLM_MODEL_ID` | _(空)_ | 本地 LLM 模型，配置后启用 chat 端点 |

## 日志

- 控制台：INFO 级别，带时间戳
- 文件：`logs/model-server_YYYY-MM-DD.log`，DEBUG 级别，按日轮转，保留 14 天
- 请求监控：每条请求自动记录 `METHOD /path → STATUS (Xms)`
