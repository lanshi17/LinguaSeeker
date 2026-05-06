# rust-io

ACMG Lingua 的高性能 I/O 原生扩展，通过 PyO3 暴露给 Python，提供学术文献搜索和下载能力。

## 快速上手

```bash
# 构建
cargo build

# 检查（不链接）
cargo check

# 测试
cargo test

# 通过 maturin 构建 wheel 并安装到 Python 环境
pip install maturin
maturin develop --release
```

构建后在 Python 中直接导入：

```python
import rust_io

# 所有函数都在 rust_io.literature 子模块下
result = await rust_io.literature.fetch_one("crossref", "search", {"query": "CRISPR", "limit": 10})
```

## 模块结构

```
src/
├── lib.rs              # 入口，PyO3 #[pymodule] 注册
├── py.rs               # Python 绑定层：参数解析 + provider 分发
├── client.rs           # HTTP 客户端（reqwest + 重试 + 代理）
├── error.rs            # 错误类型 GatewayError
├── types.rs            # 共享类型：Action, FetchParams, FetchResult
├── scraper.rs          # 通用网页抓取
└── providers/          # 各数据源实现
    ├── mod.rs           # re-export 所有 provider
    ├── crossref.rs      # CrossRef API
    ├── openalex.rs      # OpenAlex API
    ├── europepmc.rs     # Europe PMC API
    ├── pmc.rs           # PubMed Central API
    ├── doaj.rs          # DOAJ API（搜索 + 下载）
    ├── jstage.rs        # J-STAGE API（搜索 + 下载）
    └── unpaywall.rs     # Unpaywall API（DOI → OA 链接）
```

### 调用链路

```
Python 调用
  → py.rs (参数解析、类型转换)
    → execute_provider() (provider 分发)
      → providers/xxx.rs (具体 API 调用)
        → client.rs (HTTP 请求)
    → 返回 FetchResult
  → pythonize 转为 Python dict
```

## 从 Python 使用

### 函数签名

三个异步函数，均在 `rust_io.literature` 下：

```python
async def fetch_one(
    provider: str,          # 数据源名: "crossref" | "openalex" | "europepmc" | "pmc" | "doaj" | "jstage" | "unpaywall"
    action: str,            # "search" | "download"
    params: dict,           # 参数字典（见下文）
    timeout_ms: int = None, # 请求超时，默认 30000
    max_retries: int = None,# 最大重试次数，默认 2
    proxy: str = None,      # SOCKS/HTTP 代理地址
) -> dict: ...

async def fetch_multi(
    providers: list[str],   # 多个数据源，并行请求
    action: str,
    params: dict,
    ...
) -> list[dict]: ...

async def scrape_web(
    provider: str,
    action: str,
    params: dict,
    ...
) -> dict: ...              # 通用网页抓取
```

### params 字典结构

```python
{
    "query": "CRISPR gene editing",  # 搜索关键词
    "limit": 20,                     # 返回条数上限
    "raw": False,                    # 是否返回原始 API 响应
    "selected_index": 0,             # download 时选择第几条结果
    "selected_title": "...",         # download 时指定标题
    "detail_link": "https://...",    # 直接指定详情页 URL
    "identifiers": {                 # 标识符（unpaywall 必须传 doi）
        "doi": "10.1234/xxx",
        "pmid": "12345678",
        "pmcid": "PMC1234567",
        "issn": "1234-5678",
    },
}
```

### 返回结构（FetchResult）

```python
{
    "provider": "crossref",
    "success": True,
    "items": [...],           # search 结果列表
    "downloads": [...],       # download 结果（含 pdf_url）
    "warnings": [],           # 警告信息
    "raw": {...},             # 原始 API 响应（需 params.raw=True）
    "meta": {...},            # 元数据（如 total_results）
}
```

### 使用示例

```python
import asyncio
import rust_io

async def main():
    # 搜索
    result = await rust_io.literature.fetch_one(
        "crossref", "search", {"query": "ACMG guidelines", "limit": 5}
    )
    print(result["items"])

    # 多源并发搜索
    results = await rust_io.literature.fetch_multi(
        ["crossref", "openalex", "europepmc"],
        "search",
        {"query": "BRCA1 variant classification", "limit": 10},
    )

    # 下载（通过 DOI 获取 OA 链接）
    dl = await rust_io.literature.fetch_one(
        "unpaywall", "download",
        {"identifiers": {"doi": "10.1038/ng.3126"}},
    )
    print(dl["downloads"])  # [{"pdf_url": "https://..."}]

asyncio.run(main())
```

## 修改代码指南

### 新增 Provider

1. **创建文件** `src/providers/myprovider.rs`：

```rust
use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{FetchParams, FetchResult};

pub struct MyProvider;

impl MyProvider {
    pub async fn search(
        client: &HttpClient,
        query: &str,
        limit: Option<u32>,
    ) -> Result<FetchResult, GatewayError> {
        let params = serde_json::json!({ "q": query, "size": limit.unwrap_or(20) });
        let json = client.get_json("https://api.example.com/search", &params).await?;

        let items = json
            .get("results")
            .and_then(|v| v.as_array())
            .map(|a| a.to_vec())
            .unwrap_or_default();

        Ok(FetchResult {
            provider: "myprovider".into(),
            success: true,
            items,
            downloads: vec![],
            warnings: vec![],
            raw: Some(json),
            meta: None,
        })
    }
}
```

2. **注册模块** — `src/providers/mod.rs`：

```rust
mod myprovider;
pub use myprovider::MyProvider;
```

3. **接入分发** — `src/py.rs` 的 `execute_provider()` 中添加匹配分支：

```rust
("myprovider", Action::Search) => MyProvider::search(client, query, params.limit).await,
```

完成。Python 侧即可调用 `fetch_one("myprovider", "search", {...})`。

### 给现有 Provider 增加 Download 支持

在 provider 文件中添加 `download_urls` 方法：

```rust
impl MyProvider {
    pub async fn download_urls(
        client: &HttpClient,
        params: &FetchParams,
    ) -> Result<FetchResult, GatewayError> {
        // 1. 调用 search 获取候选
        // 2. 根据 selected_index 选取条目
        // 3. 提取 PDF 链接，构造 downloads 数组
        Ok(FetchResult {
            provider: "myprovider".into(),
            success: true,
            items: vec![],
            downloads: vec![serde_json::json!({ "pdf_url": "https://..." })],
            warnings: vec![],
            raw: None,
            meta: None,
        })
    }
}
```

然后在 `execute_provider()` 中添加：

```rust
("myprovider", Action::Download) => MyProvider::download_urls(client, params).await,
```

### 错误处理

所有 provider 返回 `Result<_, GatewayError>`。错误类型定义在 `src/error.rs`：

```rust
pub enum GatewayError {
    Http(reqwest::Error),      // HTTP 请求失败
    Json(serde_json::Error),   // JSON 解析失败
    Url(url::ParseError),      // URL 解析失败
    Provider { provider, message }, // 业务错误
    Other(String),             // 其他错误
}
```

添加新的错误类型时，在 `GatewayError` 中增加变体即可。

### HTTP 客户端

`HttpClient`（`src/client.rs`）封装了 reqwest，提供：

- `get_json(url, query_params)` — GET 请求，返回 JSON，query_params 自动拼接到 URL
- `get_text(url)` — GET 请求，返回纯文本
- 自动重试（指数退避）、超时、gzip、代理支持

不需要手动创建 `Client`，provider 接收的 `&HttpClient` 由 `py.rs` 创建并传入。

## 依赖

| Crate | 用途 |
|-------|------|
| pyo3 | Python 绑定 |
| pyo3-async-runtimes | 异步函数 → Python coroutine |
| pythonize | Rust 值 → Python 对象 |
| reqwest | HTTP 客户端 |
| tokio | 异步运行时 |
| scraper | HTML 解析（scrape_web） |
| serde / serde_json | JSON 序列化 |
| thiserror | 错误类型派生 |
| url | URL 解析 |
| urlencoding | URL 编码 |
