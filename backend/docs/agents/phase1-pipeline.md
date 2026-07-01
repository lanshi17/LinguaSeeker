# Phase 1: 文献采集管线

> 子代理专长：文献搜索、获取、解析的端到端管线实现。

## 职责范围

Phase 1 管线负责从学术数据源采集文献、解析文档内容、提取关键信息的完整流程。

### 核心模块

| 模块 | 路径 | 说明 |
|------|------|------|
| 文献搜索服务 | `app/services/literature.py` | 协调多数据源并行搜索 |
| MinerU 解析服务 | `app/services/mineru.py` | PDF 文档解析（公式/表格/OCR） |
| 文献 API 端点 | `app/api/literature.py` | REST API 接口 |
| 任务管理 | `app/api/tasks.py` | 异步任务状态查询 |

### 关键流程

```mermaid
graph LR
    A[搜索请求] --> B[数据源路由]
    B --> C[并行搜索 15+ 数据源]
    C --> D[结果聚合与去重]
    D --> E[PDF 下载]
    E --> F[MinerU 文档解析]
    F --> G[结构化数据提取]
    G --> H[证据入库]
```

### 涉及的原生扩展

- **net-io**：文献搜索（`fetch_one`/`fetch_multi`）、PDF 下载（`download_file`）、MinerU API 调用
- **files-io**：PDF 文件存储（本地/S3）、SHA-256 去重

### 关键配置

| 配置项 | 说明 |
|--------|------|
| `MINERU_API_KEY` | MinerU API 密钥 |
| `UNPAYWALL_EMAIL` | Unpaywall API 邮箱 |
| `PUBMED_API_KEY` | PubMed API 密钥（可选，提升速率限制） |
| `LITERATURE_MAX_CONCURRENT` | 最大并发搜索数 |
| `LITERATURE_TIMEOUT_MS` | 搜索超时（毫秒） |

### 数据源列表

15 个学术数据源，按领域分类：

- **综合**：CrossRef、OpenAlex、BASE、CORE、OpenAire
- **生物医学**：Europe PMC、PubMed Central、Unpaywall
- **预印本**：arXiv、bioRxiv、medRxiv
- **开放获取**：DOAJ、SciELO
- **亚洲**：J-STAGE（日本）、CiNii（日本）

### 测试

```bash
# 文献服务单元测试
uv run pytest tests/test_literature_service.py -v

# MinerU 集成测试
uv run pytest tests/test_mineru_service.py -v

# 端到端管线测试
uv run pytest tests/test_pipeline_e2e.py -v
```
