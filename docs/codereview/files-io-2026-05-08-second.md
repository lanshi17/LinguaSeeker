# files-io 第二次代码审查报告
> 审查日期：2026-05-08
> 审查范围：feat/files-io-module 分支

---

## 🔄 变更回顾（自第一次审查）
✅ **已修复**：新增了 `FileError::TaskJoin` 变体，替换了原来的 `Other` 用于 tokio task join errors！

---

## 🔍 本次审查发现

### 🔴 **依然存在的阻塞问题：路径遍历漏洞**
- **位置**：`backend/libs/files-io/src/archive/zip.rs` 和 `backend/libs/files-io/src/archive/tar_gz.rs`
- **问题**：解压时未验证文件路径，恶意归档可使用 `../` 覆盖系统文件！

### 🟡 **本地文件 copy 性能优化待实现**
- **位置**：`backend/libs/files-io/src/backends/local.rs`
- **问题**：当前实现是手动分块复制，建议使用 `std::fs::copy`（高度优化的系统调用）！

### ⚠️ **重大架构变更待验证：user_upload 模块被删除**
- **变更**：`backend/src/core/ingest_and_digitize_data/user_upload/` 整个模块被删除！
- **问题**：未看到迁移代码！原有的上传验证、存储逻辑（`contracts.py`, `service.py`, `workflow.py` 及其测试）全部被删除！需要确认这是否是预期的，或是否有替代实现！

---

## 📝 建议修复优先级

| 优先级 | 问题 | 原因 |
| --- | --- | --- |
| P0 | 路径遍历漏洞 | 高危安全问题，必须修复！ |
| P0 | user_upload 模块迁移 | 功能删除未替代，可能破坏现有流程！ |
| P1 | 本地 copy 使用 std::fs::copy | 性能优化 |
| P2 | 文档与 S3 测试 | 提升可维护性与覆盖 |

---

## 🔧 修复建议代码示例

### 修复 Zip 解压路径遍历
```rust
// backend/libs/files-io/src/archive/zip.rs
use std::path::{Component, PathBuf};

pub fn extract(archive_path: &str, output_dir: &str) -> Result<u64, FileError> {
    let output_path = PathBuf::from(output_dir).canonicalize()?; // 规范化输出目录
    let file = fs::File::open(archive_path)?;
    let mut archive = zip::ZipArchive::new(file).map_err(|e| FileError::Archive(e.to_string()))?;
    fs::create_dir_all(&output_path)?;
    let mut count: u64 = 0;
    
    for i in 0..archive.len() {
        let mut file = archive.by_index(i).map_err(|e| FileError::Archive(e.to_string()))?;
        let outpath = output_path.join(file.mangled_name());
        
        // 验证路径在输出目录内
        let outpath = outpath.canonicalize()?;
        if !outpath.starts_with(&output_path) {
            return Err(FileError::Archive("Path traversal attempt detected".into()));
        }
        
        if file.name().ends_with('/') {
            fs::create_dir_all(&outpath)?;
        } else {
            if let Some(parent) = outpath.parent() {
                fs::create_dir_all(parent)?;
            }
            let mut outfile = fs::File::create(&outpath)?;
            std::io::copy(&mut file, &mut outfile)?;
            count += 1;
        }
    }
    Ok(count)
}
```

### 修复本地 Copy 实现
```rust
// backend/libs/files-io/src/backends/local.rs
fn copy(&self, src: &str, dst: &str) -> Result<(), FileError> {
    if let Some(parent) = Path::new(dst).parent() {
        fs::create_dir_all(parent)?;
    }
    fs::copy(src, dst)?;
    Ok(())
}
```
