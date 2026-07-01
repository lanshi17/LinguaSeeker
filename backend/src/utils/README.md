# Utils

> 通用工具函数库——日志、LLM 适配、异常处理、中间件、安全、文本处理和可观测性。

## Overview

`utils/` 提供后端各层共享的基础设施工具。无业务逻辑，纯横切关注点。

## Structure

```
utils/
├── logger.py              # 日志配置（loguru sinks + stdlib 拦截）
├── llm_adapter.py         # LLM 客户端适配器（密钥池轮转 + 自动故障转移）
├── exceptions.py          # 统一异常层次（域错误码 ↔ HTTP 状态码映射）
├── health.py              # 启动依赖健康检查（PostgreSQL、Redis）
├── middleware.py           # 请求监控中间件（日志、request_id、耗时）
├── security_headers.py    # 安全头中间件（HSTS、CSP、X-Frame-Options）
├── body_size_limit.py     # [在 src.api 中] 请求体大小限制
├── text.py                # 文本处理（文件名清理、JSON fence 剥离、group-id 解析、摘要提取）
├── text_normalize.py      # 文本归一化（空白折叠、大小写折叠、文档拼接）
├── ssrf.py                # SSRF 防护（URL 安全验证）
├── observability.py       # LangSmith 追踪 + 结构化日志装饰器
├── rust_io.py             # Rust 原生扩展延迟导入（files_io、net_io）
├── llm_params.py          # [兼容性 shim] 重导出 resolve_max_tokens
├── markdown_helpers.py    # [兼容性 shim] 重导出 extract_abstract_from_markdown
├── parsing.py             # [兼容性 shim] 重导出 parse_gene/variant_from_group_id
└── __init__.py
```

## Key Components

### `logger.py` — 日志配置

- 基于 loguru 的双 sink 配置：stderr（彩色，按环境过滤级别）+ 文件（INFO+，按日轮转，14 天保留，gzip 压缩）
- 拦截 stdlib `logging` 输出重定向到 loguru
- 幂等初始化（`setup_logging()` 多次调用安全）
- 日志路径：`backend/logs/YYYY-MM-DD/HHmmss.log`

```python
from src.utils.logger import get_logger
logger = get_logger()
```

### `llm_adapter.py` — LLM 客户端适配器

`LLMPoolAdapter` 包装多个 ChatOpenAI 客户端，提供：

- **Round-robin 密钥轮转** — 高并发场景均匀分配请求
- **自动故障转移** — 认证错误时标记密钥失败，自动切换
- **结构化输出** — `_StructuredOutputWrapper` 支持 `with_structured_output()` 接口

```python
from src.utils.llm_adapter import create_llm_client
client = create_llm_client(model="gpt-5", api_keys=["sk-1", "sk-2"], base_url="...")
```

`resolve_max_tokens()` 按百分比计算有效 max_tokens，确保不低于最小值。

### `exceptions.py` — 异常层次

```
ACMGException (基类，含 message + code)
├── NotFoundException         # 404
├── ValidationException       # 400
├── DatabaseException         # 500
├── LLMException              # 502
├── TranslationException      # 500
├── ParsingException          # 422
└── ServiceException          # 502
```

提供 `error_code_from_exception()` 和 `status_code_from_error_code()` 双向映射函数。

### `health.py` — 健康检查

启动时验证关键基础设施可达性：

- `check_all_connections()` — 并发检查所有注册的服务
- `HealthResult` — 包含 `postgres` 和 `redis` 的布尔状态
- 使用装饰器注册检查函数：`@_register("postgres")`

### `middleware.py` — 请求监控

`RequestMonitorMiddleware` 原始 ASGI 中间件（不缓冲响应体）：

- 生成或提取 `X-Request-ID`
- 注入 `scope["state"]["request_id"]`
- 响应头添加 `X-Request-ID`
- 记录请求方法、路径、状态码和耗时

### `security_headers.py` — 安全头

两个变体：

| 中间件 | 说明 |
|--------|------|
| `SecurityHeadersMiddleware` | 基础安全头（nosniff、DENY、CSP、Referrer-Policy、Permissions-Policy） |
| `SecurityHeadersMiddlewareHSTS` | 基础安全头 + HSTS（1 年、含子域、preload） |

### `text.py` — 文本处理

| 函数 | 说明 |
|------|------|
| `sanitize_filename()` | 清理文件名中的非法字符（120 字符上限） |
| `strip_json_fences()` | 剥离 LLM 输出的 Markdown JSON 代码围栏 |
| `parse_gene_from_group_id()` | 从 `gene=BRCA1\|variant=...` 提取基因 |
| `parse_variant_from_group_id()` | 从 group_id 提取变异 |
| `extract_abstract_from_markdown()` | 从 Markdown 提取摘要（支持中英文模式） |

### `text_normalize.py` — 文本归一化

| 函数 | 说明 |
|------|------|
| `normalize_text()` | 空白折叠 + 大小写折叠 |
| `normalize_value()` | 异构值归一化为可比较字符串 |
| `block_text_from_dict()` | 从 ContentBlock dict 提取可读文本 |
| `concat_document_text()` | 拼接持久化 JSON 文档的全文（优先 formatted_text） |

### `ssrf.py` — SSRF 防护

- `is_private_ip()` — 检查主机名是否解析到私有/保留 IP
- `validate_url_safe()` — 验证 URL 不指向私有地址（仅允许 http/https）

### `observability.py` — 可观测性

`@traced_node("name")` 装饰器，同时添加 LangSmith 追踪和 loguru 日志，支持同步和异步函数。

### `rust_io.py` — Rust 原生扩展

延迟导入 `rust_io.files`（文件 I/O）和 `rust_io.net`（HTTP/MinerU），不可用时降级为 `None` 并记录警告。

## Dependencies

| 依赖 | 用途 |
|------|------|
| loguru | 结构化日志 |
| langchain-core / langchain-openai | LLM 客户端抽象 |
| langsmith | 追踪 |
| slowapi | 限流 |
| Starlette | ASGI 中间件 |
| Pydantic | 异常层次中的 SecretStr |
