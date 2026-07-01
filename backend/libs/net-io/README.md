# net-io

> 高性能 HTTP/Web I/O Rust 库，为 Lingua Seeker 提供 15 个学术文献数据源接入、MinerU 文档解析 API 和网页爬取能力。

## 概览

`net-io` 是一个 `rlib` crate，通过 PyO3 暴露 Python 绑定，由 `rust-io` 门面注册为 `rust_io.net` 子模块。核心功能包括：

- **文献数据源**：15 个学术数据源的统一搜索/下载接口
- **MinerU API v4**：文档解析任务的完整生命周期管理（创建/查询/批量/本地上传）
- **Web 爬取**：HTML 解析、PDF 链接提取、网页抓取

## 公开 API

### 文献数据源（`pyfunction`）

| 函数 | 签名 | 说明 |
|------|------|------|
| `fetch_one` | `(provider, action, params, timeout_ms=None, max_retries=None, proxy=None) -> dict` | 单数据源文献搜索/下载 |
| `fetch_multi` | `(providers, action, params, timeout_ms=None, max_retries=None, proxy=None) -> list[dict]` | 并行多数据源搜索，单个失败不影响其他 |
| `scrape_web` | `(provider, action, params, timeout_ms=None, max_retries=None, proxy=None) -> dict` | 通过数据源爬取网页内容 |

### Web 爬取（`pyfunction`）

| 函数 | 签名 | 说明 |
|------|------|------|
| `scrape_html` | `(html, css_selector) -> list[dict]` | CSS 选择器解析 HTML，返回匹配元素及属性 |
| `extract_pdf_links` | `(html, base_url) -> list[str]` | 从 HTML 提取 PDF 链接（`<a href>` + `<meta citation_pdf_url>`） |
| `download_file` | `(url, timeout_ms=None, max_retries=None, proxy=None) -> dict` | 下载文件，返回 `{bytes, final_url, status_code}` |

### MinerU API v4（`pyfunction`）

| 函数 | 签名 | 说明 |
|------|------|------|
| `mineru_create_task` | `(url, token, model_version=None, is_ocr=None, enable_formula=None, enable_table=None, language=None, data_id=None, page_ranges=None, no_cache=None, cache_tolerance=None, timeout_ms=None, proxy=None) -> dict` | 创建单个文档解析任务 |
| `mineru_get_result` | `(task_id, token, timeout_ms=None, proxy=None) -> dict` | 查询任务结果 |
| `mineru_batch_submit` | `(files, token, ...) -> dict` | 批量提交 URL 解析任务 |
| `mineru_batch_result` | `(batch_id, token, timeout_ms=None, proxy=None) -> dict` | 查询批量任务结果 |
| `mineru_create_upload_url` | `(filename, token, content_type=None, ...) -> dict` | 获取本地文件预签名上传 URL |
| `mineru_create_batch_upload_urls` | `(files, token, callback=None, seed=None, extra_formats=None, ...) -> dict` | 批量获取预签名上传 URL |
| `mineru_upload_local_file` | `(upload_url, file_path, content_type=None, timeout_ms=None, proxy=None) -> dict` | 上传单个本地文件到预签名 URL |
| `mineru_upload_local_files` | `(file_paths, token, data_ids=None, is_ocr=None, page_ranges=None, callback=None, seed=None, extra_formats=None, ...) -> dict` | 上传本地文件并自动提交解析 |

## 架构

```
net-io/src/
├── lib.rs          # 模块声明
├── error.rs        # GatewayError 枚举（Http/Json/Io/Url/Provider/Other）
├── types.rs        # 共享类型（Action, FetchParams, FetchResult, MinerU*Request）
├── client.rs       # HttpClient — reqwest 封装，支持重试、代理、浏览器 UA
├── scraper.rs      # WebScraper — HTML 解析、PDF 链接提取、数据源爬取
├── mineru.rs       # MinerU API v4 客户端（create/batch/upload）
├── py.rs           # PyO3 绑定层 — 所有 #[pyfunction] 定义
└── providers/      # 15 个文献数据源实现
    ├── mod.rs      # 数据源注册与导出
    ├── crossref.rs
    ├── openalex.rs
    ├── europepmc.rs
    ├── pmc.rs
    ├── unpaywall.rs
    ├── arxiv.rs
    ├── biorxiv.rs   # BioRxiv + MedRxiv
    ├── base_search.rs
    ├── core_search.rs
    ├── doaj.rs
    ├── openaire.rs
    ├── scielo.rs
    ├── jstage.rs
    └── cinii.rs
```

### HttpClient

- 基于 `reqwest`，默认浏览器 UA 模拟 Chrome，避免学术出版商 403
- 指数退避重试（默认 3 次，上限 1s/2s/4s）
- 默认超时 60s，连接超时 15s
- 支持 SOCKS5/HTTP 代理
- 方法：`get_json`、`get_text`、`get_bytes`、`post_json`、`put_bytes`、`get_json_with_auth`

### 数据源

15 个学术数据源，每个实现统一的 `Search`/`Download` action 接口：

| 数据源 | 说明 |
|--------|------|
| `crossref` | CrossRef DOI 元数据 |
| `openalex` | OpenAlex 学术图谱 |
| `europepmc` | Europe PMC 生物医学文献 |
| `pmc` | PubMed Central 全文 |
| `unpaywall` | 开放获取 PDF 链接 |
| `arxiv` | arXiv 预印本 |
| `biorxiv` | bioRxiv 预印本 |
| `medrxiv` | medRxiv 预印本 |
| `base` | BASE 学术搜索引擎 |
| `core` | CORE 开放获取聚合 |
| `doaj` | DOAJ 开放获取期刊 |
| `openaire` | OpenAire 欧洲开放科学 |
| `scielo` | SciELO 拉美学术文献 |
| `jstage` | J-STAGE 日本学术文献 |
| `cinii` | CiNii 日本学术论文 |

### 错误处理

`GatewayError` 自动映射为 Python 异常：

| Rust 错误 | Python 异常 |
|-----------|-------------|
| `Http` | `ConnectionError` |
| `Json` / `Url` | `ValueError` |
| `Provider` / `Other` | `RuntimeError` |
| `Io` | `OSError` |

## 使用示例

```python
import rust_io.net as net_io

# 单数据源搜索
result = await net_io.fetch_one("crossref", "search", {"query": "CRISPR", "limit": 5})

# 并行多数据源搜索
results = await net_io.fetch_multi(
    ["crossref", "openalex", "europepmc"],
    "search",
    {"query": "BRCA1 variant", "limit": 10},
)

# HTML 解析
elements = net_io.scrape_html(html_content, "a.download-link")
pdf_links = net_io.extract_pdf_links(html_content, "https://example.com")

# MinerU 文档解析
result = await net_io.mineru_create_task(
    url="https://example.com/paper.pdf",
    token="your_mineru_token",
    enable_formula=True,
    enable_table=True,
)
task_id = result["task_id"]
parsed = await net_io.mineru_get_result(task_id, "your_mineru_token")

# 本地文件上传解析
result = await net_io.mineru_upload_local_files(
    file_paths=["/tmp/paper.pdf"],
    token="your_mineru_token",
)
```

## 依赖

| 依赖 | 版本 | 说明 |
|------|------|------|
| `pyo3` | `0.28.2` | Python 绑定 |
| `pyo3-async-runtimes` | `0.28` | Tokio 异步运行时集成 |
| `reqwest` | `0.13` | HTTP 客户端（rustls, gzip, socks） |
| `tokio` | `1` | 异步运行时 |
| `futures` | `0.3` | 异步工具（join_all） |
| `scraper` | `0.26` | HTML 解析与 CSS 选择器 |
| `url` | `2` | URL 解析与构造 |
| `serde` / `serde_json` | `1` | 序列化 |
| `pythonize` | `0.28` | Rust → Python 对象转换 |
| `urlencoding` | `2` | URL 编码 |
| `thiserror` | `2` | 错误类型派生 |

## 环境变量

| 变量 | 说明 |
|------|------|
| `UNPAYWALL_EMAIL` | Unpaywall API 必需 |
| `PUBMED_API_KEY` | PMC/NCBI 可选，提升速率限制 |
| `BASE_API_KEY` | BASE 搜索可选 |
| `CORE_API_KEY` | CORE 搜索可选 |
