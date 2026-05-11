# Model Server

ACMG-Lingua 的本地模型推理微服务。提供 Embedding、Rerank、VLM 文档提取的 OpenAI 兼容 API，统一运行在 8001 端口。所有推理后端基于 vllm 统一引擎。

## 快速启动

```bash
cd services/model-server

# 安装依赖（复用 backend venv，vllm 由 pyproject.toml 管理）
uv pip install -e "../../.[dev]"

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
| `POST` | `/v1/embeddings` | 向量嵌入（vllm） |
| `POST` | `/v1/rerank` | 重排序（vllm） |
| `POST` | `/v1/chat/completions` | VLM 文档提取（MinerU + vllm，多模态） |

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

### VLM 文档提取

```bash
curl http://localhost:8001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "opendatalab/MinerU2.5-Pro-2604-1.2B",
    "messages": [
      {"role": "user", "content": [
        {"type": "text", "text": "Extract this document."},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,<BASE64_IMAGE>"}}
      ]}
    ]
  }'
```

响应格式：
```json
{
  "id": "vlm-abc123",
  "object": "vlm.extraction",
  "model": "opendatalab/MinerU2.5-Pro-2604-1.2B",
  "metadata": {"total_pages": 1, "title": null},
  "pages": [{"page_number": 1, "markdown": "...", "figures": [], "tables": []}],
  "full_markdown": "...",
  "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
}
```

### Health

```json
// GET /health
{
  "status": "ok",
  "models": {
    "embedding": true,
    "rerank": true,
    "vlm": true
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
│   ├── embedding.py       # EmbeddingService (vllm task="embed")
│   ├── rerank.py          # RerankService (vllm task="score")
│   └── llm.py             # LLMService / VLM (vllm + MinerUClient)
└── api/                   # 路由层
    ├── health.py
    ├── embedding.py
    ├── rerank.py
    ├── chat.py
    └── vlm.py             # /v1/chat/completions 多模态端点
```

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
| `VLM_MODEL_ID` | _(空)_ | MinerU VLM 模型，配置后启用 VLM 端点 |
| `VLM_IMAGE_ANALYSIS` | `false` | 是否启用图像/图表分析 |
| `VLLM_GPU_MEMORY_UTILIZATION` | `0.9` | vllm GPU 显存分配比例 |

## 日志

- 控制台：INFO 级别，带时间戳
- 文件：`logs/model-server_YYYY-MM-DD.log`，DEBUG 级别，按日轮转，保留 14 天
- 请求监控：每条请求自动记录 `METHOD /path → STATUS (Xms)`
