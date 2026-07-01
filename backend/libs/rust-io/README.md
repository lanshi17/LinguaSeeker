# rust-io

> Lingua Seeker 的 PyO3 门面 crate，将 `net-io` 和 `files-io` 注册为 `rust_io` Python 模块的子模块。

## 概览

`rust-io` 是唯一构建为 `cdylib`（`.so`/`.pyd`）的 crate，通过 `import rust_io` 加载。它本身不包含业务逻辑，仅负责：

1. 创建 `rust_io.net` 子模块，注册 `net-io` 的所有 `#[pyfunction]`
2. 创建 `rust_io.files` 子模块，注册 `files-io` 的所有 `#[pyfunction]` 和 `#[pyclass]`
3. 通过 `sys.modules` 注册子模块，使其可通过 `import rust_io.net` / `import rust_io.files` 直接访问

## 公开 API

`rust-io` 本身不定义业务 API，完整 API 参考见各子 crate：

| Python 模块 | 来源 crate | 说明 |
|-------------|-----------|------|
| `rust_io.net` | [net-io](../net-io/README.md) | 15 个文献数据源、MinerU API、Web 爬取 |
| `rust_io.files` | [files-io](../files-io/README.md) | File 类、批量操作、去重、工具函数 |

### `rust_io.net` 注册的函数

| 函数 | 说明 |
|------|------|
| `fetch_one` | 单数据源文献搜索/下载 |
| `fetch_multi` | 并行多数据源搜索 |
| `scrape_web` | 数据源网页爬取 |
| `scrape_html` | CSS 选择器 HTML 解析 |
| `extract_pdf_links` | 提取 PDF 链接 |
| `download_file` | 文件下载 |
| `mineru_create_task` | MinerU 创建解析任务 |
| `mineru_get_result` | MinerU 查询任务结果 |
| `mineru_batch_submit` | MinerU 批量提交 |
| `mineru_batch_result` | MinerU 批量结果查询 |
| `mineru_create_upload_url` | MinerU 获取上传 URL |
| `mineru_create_batch_upload_urls` | MinerU 批量获取上传 URL |
| `mineru_upload_local_file` | MinerU 上传单个本地文件 |
| `mineru_upload_local_files` | MinerU 上传多个本地文件 |

### `rust_io.files` 注册的函数/类

| 名称 | 类型 | 说明 |
|------|------|------|
| `File` | class | 统一文件操作（本地 + S3） |
| `batch_copy` | function | 批量文件复制 |
| `batch_compress` | function | 批量目录压缩 |
| `batch_copy_async` | function | 异步批量复制 |
| `check_duplicate` | function | 文件去重检查 |
| `batch_hash` | function | 批量 SHA-256 哈希 |
| `compute_sha256` | function | 单文件 SHA-256 |
| `write_file` | function | 写入字节数据 |
| `validate_pdf_magic` | function | PDF 魔数校验 |

## 架构

```
rust-io/src/
└── lib.rs    # #[pymodule] rust_io — 注册 net 和 files 子模块
```

### 子模块注册机制

```rust
#[pymodule]
fn rust_io(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // 1. 创建子模块
    let net = PyModule::new(m.py(), "net")?;
    // 2. 添加函数
    net.add_function(wrap_pyfunction!(net_io::py::fetch_one, &net)?)?;
    // ... 更多函数
    // 3. 注册到父模块 + sys.modules
    register_submodule(m, "rust_io.net", &net)?;

    let files = PyModule::new(m.py(), "files")?;
    files.add_class::<files_io::py::file::File>()?;
    // ... 更多函数
    register_submodule(m, "rust_io.files", &files)?;
    Ok(())
}
```

`register_submodule` 辅助函数完成两步操作：
1. `parent.add_submodule(submodule)` — 注册到父模块
2. `sys.modules["rust_io.net"] = submodule` — 使 `import rust_io.net` 可用

## 使用示例

```python
# 通过 rust_io 门面访问所有功能
import rust_io

# 或直接导入子模块
import rust_io.net as net_io
import rust_io.files as files_io

# 文献搜索
result = await net_io.fetch_one("crossref", "search", {"query": "CRISPR"})

# 文件操作
f = files_io.File("/tmp/output.txt")
f.write("hello")
print(f.read(as_text=True))
```

## 构建

```bash
# 从 backend/ 目录构建（maturin 会自动解析 Cargo.toml 中的 path 依赖）
cd backend
uv run maturin develop --release -m libs/rust-io/Cargo.toml
```

构建产物为 `rust_io.so`（Linux/macOS）或 `rust_io.pyd`（Windows），包含 `net-io` 和 `files-io` 的全部代码（静态链接）。

## 依赖

| 依赖 | 版本 | 说明 |
|------|------|------|
| `pyo3` | `0.28.2` | Python 绑定（extension-module） |
| `pyo3-async-runtimes` | `0.28` | Tokio 异步运行时集成 |
| `net-io` | path | HTTP/Web I/O crate |
| `files-io` | path | 文件 I/O crate |
