# Native Extensions

> Rust/PyO3 原生扩展，为 Lingua Seeker 提供文献采集、MinerU 文档解析、文件 I/O（本地 + S3）、归档处理和 SHA-256 去重能力。三个 crate，一个 Python 模块：`rust_io`。

## 概览

```
rust-io  (cdylib + rlib)  ← 唯一构建为 Python 扩展的 crate
 ├─ net-io    (rlib)      ← HTTP/Web I/O：15 个文献数据源 + MinerU API
 └─ files-io  (rlib)      ← 文件 I/O：本地 + S3、归档、SHA-256 去重
```

| Crate | Python 模块 | 构建类型 |
|-------|------------|----------|
| `rust-io` | `rust_io` | `cdylib`（`.so`/`.pyd`）— 通过 `import rust_io` 加载 |
| `net-io` | `rust_io.net` | `rlib` — 静态链接到 `rust-io` |
| `files-io` | `rust_io.files` | `rlib` — 静态链接到 `rust-io` |

`net-io` 和 `files-io` **不是**独立的 Python 模块。它们通过 `#[pyfunction]` 和 `#[pyclass]` 暴露 API，由 `rust-io` 门面模块通过 `register_submodule()` 注册为 `rust_io.net` 和 `rust_io.files` 两个子模块。

## 目录结构

```
backend/libs/
├── config-loader/    # 纯 Python：分层 YAML 配置加载器
├── rust-io/          # PyO3 门面 crate（cdylib）
├── net-io/           # HTTP/Web I/O crate（rlib）
└── files-io/         # 文件 I/O crate（rlib）
```

## 快速开始

```python
# 文献搜索（单数据源）
import rust_io.net as net_io
result = await net_io.fetch_one("crossref", "search", {"query": "CRISPR"})

# 并行多数据源搜索
results = await net_io.fetch_multi(
    ["crossref", "openalex", "europepmc"],
    "search",
    {"query": "BRCA1 variant", "limit": 5},
)

# 文件 I/O —— 本地和 S3 路径使用相同 API
import rust_io.files as files_io
f = files_io.File("/tmp/output/report.txt")
f.write("variant analysis results")
print(f.read(as_text=True))

# S3 显式凭证
s3f = files_io.File("s3://bucket/data.csv", access_key="AKIA...", secret_key="...")
```

## 构建与安装

```bash
# 构建 Python 扩展（从 backend/ 目录）
cd backend
uv run maturin develop --release -m libs/rust-io/Cargo.toml

# 运行各子 crate 的 Rust 单元测试
cargo test -p net-io
cargo test -p files-io

# 运行 Python 集成测试
uv run pytest backend/tests/ -v

# Rust 代码检查
cargo clippy --all-targets -- -D warnings

# Python 代码检查
uv run ruff check
```

每个 crate 有独立的 `Cargo.lock`（非 workspace）。添加/更新依赖后，在 crate 目录下运行 `cargo check`。

## 环境变量

| 变量 | 使用者 | 说明 |
|------|--------|------|
| `UNPAYWALL_EMAIL` | `net-io`（Unpaywall） | Unpaywall API 必需 |
| `PUBMED_API_KEY` | `net-io`（PMC）+ Python `pubmed_service` | 可选；NCBI E-utilities 速率限制从 3 提升至 10 req/s |
| `BASE_API_KEY` | `net-io`（BASE） | 可选；BASE 学术搜索 API 密钥 |
| `CORE_API_KEY` | `net-io`（CORE） | 可选；CORE 搜索 API 密钥 |
| `AWS_ACCESS_KEY_ID` | `files-io`（S3） | AWS 凭证链（显式传参时可选） |
| `AWS_SECRET_ACCESS_KEY` | `files-io`（S3） | AWS 凭证链 |
| `AWS_REGION` | `files-io`（S3） | 默认 `us-east-1` |

S3 凭证通过 `aws-sdk-s3` 默认链解析（环境变量、`~/.aws/credentials`、IMDS）。显式 kwargs 覆盖默认链。MinerU token 通过调用参数传入，不从环境变量读取。

## 子 Crate 参考

- **[rust-io](./rust-io/README.md)** — 门面 crate：子模块注册、完整 Python API 参考
- **[net-io](./net-io/README.md)** — HTTP I/O：15 个文献数据源、MinerU API v4、Web 爬虫
- **[files-io](./files-io/README.md)** — 文件 I/O：`File` 类、`FileOps` trait、后端、归档、去重
- **[config-loader](./config-loader/README.md)** — 纯 Python 分层 YAML 配置加载器
