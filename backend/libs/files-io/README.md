# files-io

> 统一的本地 + S3 文件 I/O Rust 库，为 Lingua Seeker 提供文件读写、归档压缩、SHA-256 去重能力。

## 概览

`files-io` 是一个 `rlib` crate，通过 PyO3 暴露 Python 绑定，由 `rust-io` 门面注册为 `rust_io.files` 子模块。支持本地文件系统和 S3 存储的统一操作接口，包含归档（zip/tar/tar.gz）处理和基于 SHA-256 的文件去重。

## 公开 API

### `File` 类（`pyclass`）

构造函数通过路径前缀自动选择后端：`s3://` 开头使用 S3Backend，否则使用 LocalBackend。

| 方法 | 签名 | 说明 |
|------|------|------|
| `__init__` | `(path, access_key=None, secret_key=None, endpoint=None, region=None)` | 创建文件对象，S3 路径需要 access_key/secret_key |
| `read` | `(as_text=False) -> bytes \| str` | 读取全部内容，`as_text=True` 返回字符串 |
| `read_chunk` | `(offset, size) -> bytes` | 分块读取 |
| `write` | `(data: bytes \| str) -> None` | 写入文件（自动创建父目录） |
| `exists` | `() -> bool` | 检查文件是否存在 |
| `metadata` | `() -> dict` | 返回元数据（size, mtime, is_file, is_dir, is_symlink, permissions） |
| `rename` | `(dst) -> None` | 重命名/移动文件 |
| `copy` | `(dst) -> None` | 复制文件 |
| `remove` | `() -> None` | 删除文件 |
| `remove_dir_all` | `() -> None` | 递归删除目录 |
| `list_dir` | `() -> list[str]` | 列出目录内容 |
| `content_hash` | `() -> str` | 计算 SHA-256 哈希（本地分块读取，S3 读取全部后哈希） |
| `compress` | `(output_path, format) -> int` | 压缩目录（format: `zip`/`tar`/`tar.gz`/`tgz`），返回条目数 |
| `extract` | `(output_dir) -> int` | 解压归档（自动检测格式），返回条目数 |
| `copy_async` | `(dst) -> Coroutine` | 异步复制（在 `spawn_blocking` 中执行） |
| `compress_async` | `(output_path, format) -> Coroutine` | 异步压缩 |
| `extract_async` | `(output_dir) -> Coroutine` | 异步解压 |

支持上下文管理器（`with` 语句）。

### 批量操作（`pyfunction`）

| 函数 | 签名 | 说明 |
|------|------|------|
| `batch_copy` | `(sources, destinations, access_key=None, secret_key=None, endpoint=None, region=None) -> dict` | 批量复制，返回 `{success: [...], failed: [{path, error}]}` |
| `batch_compress` | `(dir_paths, output_paths, format="zip") -> dict` | 批量压缩目录 |
| `batch_copy_async` | `(同 batch_copy) -> Coroutine` | 异步批量复制（在 `spawn_blocking` 中顺序执行） |

### 去重（`pyfunction`）

| 函数 | 签名 | 说明 |
|------|------|------|
| `check_duplicate` | `(file_path, known_hashes: list[str]) -> dict` | 检查文件是否重复，返回 `{hash, is_duplicate}` |
| `batch_hash` | `(file_paths: list[str]) -> dict` | 批量计算哈希，返回 `{hashes: {path: hash}, errors: {path: error}}` |

### 工具函数（`pyfunction`）

| 函数 | 签名 | 说明 |
|------|------|------|
| `compute_sha256` | `(file_path) -> str` | 计算单个文件的 SHA-256 哈希 |
| `write_file` | `(file_path, data: bytes) -> None` | 直接写入字节数据 |
| `validate_pdf_magic` | `(data: bytes) -> bool` | 检查数据是否以 `%PDF` 开头 |

## 架构

```
files-io/src/
├── lib.rs              # 模块声明
├── error.rs            # FileError 枚举（IO/S3/Path/Archive/Zip/Hash/TaskJoin）
├── hash.rs             # SHA-256 哈希（hash_file 分块读取，hash_bytes 内存哈希）
├── backends/
│   ├── mod.rs          # FileOps trait + FileMetadata 结构体
│   ├── local.rs        # LocalBackend — 本地文件系统实现
│   └── s3.rs           # S3Backend — AWS S3 实现
├── archive/
│   ├── mod.rs
│   ├── zip.rs          # zip 压缩/解压
│   └── tar_gz.rs       # tar/tar.gz 压缩/解压
└── py/
    ├── mod.rs          # 子模块声明
    ├── file.rs         # File pyclass — 统一文件操作入口
    ├── parallel.rs     # batch_copy/batch_compress/batch_copy_async
    ├── dedup.rs        # check_duplicate/batch_hash
    └── utils.rs        # compute_sha256/write_file/validate_pdf_magic
```

- `FileOps` trait 定义统一接口：`read_all`、`read_chunk`、`write`、`exists`、`metadata`、`rename`、`copy`、`remove`、`list_dir` 等
- `File` 类根据路径自动分发到 `LocalBackend` 或 `S3Backend`
- 归档支持 zip、tar、tar.gz/tgz 三种格式
- 哈希使用 1MB 分块读取，适用于大文件
- 错误通过 `FileError` → `PyErr` 自动映射到 Python 异常类型

## 使用示例

```python
import rust_io.files as files_io

# 本地文件操作
f = files_io.File("/tmp/report.txt")
f.write("analysis results")
print(f.read(as_text=True))
print(f.content_hash())

# S3 操作
s3f = files_io.File("s3://bucket/data.csv", access_key="AKIA...", secret_key="...")
s3f.write(b"col1,col2\n1,2\n")
print(s3f.metadata())

# 归档
archive = files_io.File("/tmp/output_dir")
archive.compress("/tmp/output.zip", "zip")
archive.extract("/tmp/extracted/")

# 批量操作
result = files_io.batch_copy(
    ["/tmp/a.txt", "/tmp/b.txt"],
    ["/tmp/copy_a.txt", "/tmp/copy_b.txt"],
)
print(result)  # {"success": [...], "failed": [...]}

# 去重
dup = files_io.check_duplicate("/tmp/file.pdf", ["abc123...", "def456..."])
print(dup["is_duplicate"])
```

## 依赖

| 依赖 | 版本 | 说明 |
|------|------|------|
| `pyo3` | `0.28.2` | Python 绑定 |
| `pyo3-async-runtimes` | `0.28` | Tokio 异步运行时集成 |
| `tokio` | `1` | 异步运行时（rt-multi-thread, fs） |
| `aws-sdk-s3` | `1` | AWS S3 客户端 |
| `aws-config` | `1` | AWS 配置加载 |
| `aws-credential-types` | `1` | AWS 凭证类型 |
| `zip` | `2` | zip 归档处理 |
| `tar` | `0.4` | tar 归档处理 |
| `flate2` | `1` | gzip 压缩 |
| `sha2` | `0.10` | SHA-256 哈希 |
| `hex` | `0.4` | 十六进制编码 |
| `serde` / `serde_json` | `1` | 序列化 |
| `pythonize` | `0.28` | Rust → Python 对象转换 |
| `thiserror` | `2` | 错误类型派生 |
