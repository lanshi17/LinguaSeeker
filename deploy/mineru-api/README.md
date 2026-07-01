# MinerU 文档解析部署

> MinerU PDF 解析服务部署说明，作为外部 Docker 容器运行于端口 44321。

## 概述

MinerU 文档解析服务作为独立 Docker 容器运行，配备专用 GPU，提供高质量 PDF 到结构化 Markdown 的转换能力。后端通过 HTTP API 调用此服务。

## 架构

```
Backend (FastAPI :8000)
  +-- POST http://localhost:44321/file_parse  -> MinerU doc-parse 容器
```

## 推理服务容器

| 容器 | 端口 | 模型 | 用途 |
|------|------|------|------|
| Embedding | 8002 | Qwen3-Embedding-0.6B | 文本嵌入 |
| Rerank | 8003 | bge-reranker-v2-m3 | 重排序 |
| Doc Parse | 44321 | MinerU2.5-Pro | PDF 文档解析 |

## 后端配置

```yaml
# backend/config/defaults/main.yaml
embedding:
  base_url: "http://localhost:8002"
rerank:
  base_url: "http://localhost:8003"
mineru:
  local_parse_url: "http://localhost:44321"
  local_model_id: "opendatalab/MinerU2.5-Pro-2604-1.2B"
  local_dpi: 200
  max_file_size_mb: 100
```

## 系统要求

- Python 3.12+
- CUDA 兼容 GPU（每个容器 8GB+ VRAM）
- Docker + NVIDIA Container Toolkit

## 使用方法

推理服务容器由独立项目构建和发布，不包含在本仓库的构建流程中。部署时需确保：

1. 模型权重已预下载到 `/opt/lingua-seeker-data/models/`
2. NVIDIA Container Toolkit 已安装
3. 容器已启动并可通过配置的端口访问
