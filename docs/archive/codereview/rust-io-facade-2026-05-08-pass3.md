# Code Review: refactor/rust-io-facade (Pass 3)

- **Branch**: `refactor/rust-io-facade`
- **Date**: 2026-05-08
- **Reviewer**: Sisyphus (AI)
- **Scope**: 9 commits, 27 files changed (+151 / -87)
- **Pass**: Third (architecture + diff review against Rust review checklist)
- **Previous**: [Pass 2 Review](./rust-io-facade-2026-05-08.md)

---

## 1. Summary

本次审查基于 Pass 2 的发现，重新验证架构设计、依赖完整性和文档一致性。重点检查：

- Facade 模式实现正确性
- 依赖树清洁度
- Python 迁移完整性
- Rust Review Checklist（所有权、unsafe、异步、错误处理）

---

## 2. Architecture Verification

### 2.1 Crate 依赖图

```
rust-io (cdylib + rlib)
├── pyo3 [extension-module]  ✅ 仅此 crate 持有
├── pyo3-async-runtimes
├── tokio
├── serde_json               ⚠️ 未使用（见 3.1）
├── pythonize                ⚠️ 未使用（见 3.1）
├── files-io ───────────────→ rlib
│   ├── pyo3 (无 extension-module)
│   ├── sha2, hex, zip, tar, flate2
│   └── aws-sdk-s3
└── literature-io ──────────→ rlib
    ├── pyo3 (无 extension-module)
    ├── reqwest [rustls, gzip, socks]
    ├── scraper
    └── thiserror, url, urlencoding
```

**Verdict**: 依赖方向正确。`extension-module` feature 仅在 `rust-io` 中声明。

### 2.2 Python 子模块注册

`rust-io/src/lib.rs` 中的 `register_submodule()` 实现：

```rust
fn register_submodule(
    parent: &Bound<'_, PyModule>,
    full_name: &str,
    submodule: &Bound<'_, PyModule>,
) -> PyResult<()> {
    parent.add_submodule(submodule)?;
    parent.py().import("sys")?
        .getattr("modules")?
        .cast::<PyDict>()?
        .set_item(full_name, submodule)?;
    Ok(())
}
```

**验证**:
- ✅ `add_submodule` 正确挂载到父模块
- ✅ `sys.modules` 注册使 `import rust_io.literature` 直接可用
- ✅ 支持所有导入风格：`import rust_io.files` / `from rust_io.files import File` / `import rust_io.files as files_io`

### 2.3 Python 迁移检查

| 文件 | 旧导入 | 新导入 | 状态 |
|------|--------|--------|------|
| `gateway.py:197` | `import rust_io` → `rust_io.literature` | `import rust_io.literature as literature_io` | ✅ |
| `base.py:40` | `import rust_io` → `rust_io.literature` | `import rust_io.literature as literature_io` | ✅ |
| `base.py:63` | `import rust_io` → `rust_io.literature` | `import rust_io.literature as literature_io` | ✅ |
| `service.py:21` | `import files_io` | `import rust_io.files as files_io` | ✅ |

所有迁移均保留 `ImportError` 降级逻辑。

---

## 3. Findings

### 🔴 [blocking] Must Fix Before Merge

#### 3.1 `rust-io` 残留未使用的依赖

**File**: `backend/libs/rust-io/Cargo.toml:15-16`

```toml
[dependencies]
serde_json = "1"    # 新 lib.rs 中无直接使用
pythonize = "0.28"   # 新 lib.rs 中无直接使用
```

新 `lib.rs` 仅使用 `pyo3`、`pyo3::types::PyDict`、`std::path::Path`，不直接调用 `serde_json` 或 `pythonize`。这两个依赖通过子 crate 传递，`rust-io` 本身不需要。

**Fix**: 从 `[dependencies]` 中移除：

```toml
[dependencies]
pyo3 = { version = "0.28.2", features = ["extension-module"] }
pyo3-async-runtimes = { version = "0.28", features = ["tokio-runtime"] }
tokio = { version = "1", features = ["rt-multi-thread", "macros", "time"] }
files-io = { path = "../files-io" }
literature-io = { path = "../literature-io" }
```

#### 3.2 `literature-io` README 与实际架构不符

**File**: `backend/libs/literature-io/README.md`

README 描述 `literature_io` 为独立 PyO3 扩展：

```python
import literature_io
result = await literature_io.fetch_one(...)
```

但 `literature-io` 现在是 `rlib`-only，Python 无法直接 `import literature_io`。

**Fix**: 更新 README 开头说明：

```markdown
# literature-io

Rust library for literature acquisition. **Not a standalone Python module** —
access via `rust_io.literature` facade.

## From Python

```python
import rust_io.literature as literature_io
result = await literature_io.fetch_one("crossref", "search", {"query": "CRISPR"})
```
```

---

### 🟡 [important] Should Fix, Discuss if Disagree

#### 3.3 `rust-io` README 未更新

**File**: `backend/libs/rust-io/README.md`

模块结构仍描述旧架构：

```
src/
├── lib.rs              # 入口，PyO3 #[pymodule] 注册
├── py.rs               # Python 绑定层
├── client.rs           # HTTP 客户端
├── error.rs            # 错误类型
├── types.rs            # 共享类型
├── scraper.rs          # 网页抓取
└── providers/          # 数据源实现
```

这些文件已移至 `literature-io`。

**Fix**: 更新为 facade 架构：

```
src/
└── lib.rs              # Facade: 注册 rust_io.literature 和 rust_io.files 子模块

依赖:
├── files-io/           # 文件 I/O (hash, S3, archive, dedup)
└── literature-io/      # 文献获取 (providers, client, scraper)
```

#### 3.4 `files-io` 的 `pyo3-async-runtimes` 依赖

**File**: `backend/libs/files-io/Cargo.toml:13`

```toml
pyo3-async-runtimes = { version = "0.28", features = ["tokio-runtime"] }
```

检查 `files-io/src/py/` 下的文件：

- `utils.rs` — 同步函数
- `dedup.rs` — 同步函数
- `file.rs` — 需确认
- `parallel.rs` — `batch_copy_async` 可能使用

如果 `parallel.rs` 中的 async 函数使用了 `pyo3_async_runtimes`，则保留合理。否则应移除以减少编译时间。

#### 3.5 缺少 Facade 集成测试

无测试验证 facade 正确委托到子 crate。Pass 2 中提到的 `test_rust_io_facade.py` 应存在。建议验证其内容覆盖：

```python
def test_literature_submodule_importable():
    import rust_io.literature
    assert hasattr(rust_io.literature, 'fetch_one')
    assert hasattr(rust_io.literature, 'fetch_multi')

def test_files_submodule_importable():
    import rust_io.files
    assert hasattr(rust_io.files, 'compute_sha256')
    assert hasattr(rust_io.files, 'File')
```

---

### 🟢 [nit] Nice to Have, Not Blocking

#### 3.6 `register_submodule` 可提取为共享宏

当前两个调用点（literature、files）代码相同。如果未来有更多子 crate，可提取为宏：

```rust
macro_rules! register_python_submodule {
    ($parent:expr, $full_name:expr, $submodule:expr) => {{
        $parent.add_submodule($submodule)?;
        $parent.py().import("sys")?
            .getattr("modules")?
            .cast::<pyo3::types::PyDict>()?
            .set_item($full_name, $submodule)?;
        Ok(())
    }};
}
```

当前两个调用点不需要抽象。

---

## 4. Rust Review Checklist

| 检查项 | 结果 | 备注 |
|--------|------|------|
| **所有权/借用** | ✅ | 无新增 clone/Arc/RefCell |
| **Unsafe 代码** | ✅ | 无 unsafe 块（grep 命中为字符串字面量） |
| **异步/并发** | ✅ | 无新增 async 代码；沿用现有模式 |
| **取消安全性** | N/A | 无 select!/timeout 新增 |
| **spawn vs await** | ✅ | 无新增 spawn |
| **错误处理** | ✅ | 沿用 thiserror + From 模式 |
| **性能** | ✅ | 无热路径变更 |
| **cargo clippy** | ⚠️ | 未运行，建议验证 |
| **cargo fmt** | ⚠️ | 未运行，建议验证 |
| **文档注释** | ✅ | 公共 API 有文档 |

---

## 5. Pass 2 问题追踪

| # | 问题 | 状态 | 备注 |
|---|------|------|------|
| 3.1 | Dead test file `test_files_io.py` | ⚠️ 待确认 | 需检查是否已删除或迁移 |
| 3.2 | S3 `block_on()` 设计 | ℹ️ 已知 | 设计决策，建议文档化 |
| 3.3 | S3 `is_tracked` 原始字段 | ℹ️ 已知 | 建议改用方法 |
| 3.4 | Zip symlink escape | ℹ️ 已知 | 安全加固建议 |
| 3.5 | `HttpClient::default()` panic | ℹ️ 已知 | 建议移除或改用 expect |
| 3.6 | `fetch_multi` 顺序执行 | ℹ️ 已知 | 性能优化建议 |
| 3.7 | Unpaywall fallback email | ℹ️ 已知 | 合规建议 |
| 3.8 | DOI 未 URL 编码 | ℹ️ 已知 | Bug 修复建议 |
| 3.9 | 指数退避溢出风险 | ℹ️ 已知 | 防御性编程建议 |
| 3.10 | 错误类型信息丢失 | ℹ️ 已知 | Python 异常映射建议 |

---

## 6. Decision

🔄 **Request Changes** — 2 个 blocking 问题：

1. **移除 `rust-io` 中未使用的 `serde_json` 和 `pythonize` 依赖**（3.1）
2. **更新 `literature-io` README 以反映 rlib-only 架构**（3.2）

修复后可合并。Pass 2 中的 important/nit 问题可作为后续优化。

---

## 7. Files Reviewed

### Rust — `rust-io` (facade)
- `backend/libs/rust-io/Cargo.toml` — ⚠️ 残留依赖
- `backend/libs/rust-io/pyproject.toml` — ✅
- `backend/libs/rust-io/src/lib.rs` — ✅

### Rust — `files-io`
- `backend/libs/files-io/Cargo.toml` — ⚠️ pyo3-async-runtimes 待确认
- `backend/libs/files-io/src/lib.rs` — ✅
- `backend/libs/files-io/src/py/utils.rs` — ✅

### Rust — `literature-io`
- `backend/libs/literature-io/Cargo.toml` — ✅
- `backend/libs/literature-io/src/lib.rs` — ✅
- `backend/libs/literature-io/README.md` — ⚠️ 内容过时

### Python
- `backend/pyproject.toml` — ✅
- `backend/src/core/ingest_and_digitize_data/literature_acquisition/gateway.py` — ✅
- `backend/src/core/ingest_and_digitize_data/literature_acquisition/web/base.py` — ✅
- `backend/src/core/ingest_and_digitize_data/user_upload/service.py` — ✅
