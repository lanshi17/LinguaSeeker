# 快速参考: 生产管道故障排查

## ✅ 已修复的问题

### 问题 1: NumPy 2.0 警告
**状态**: ✅ **已修复**

FastText 库在加载模型时会产生 NumPy 2.0 兼容性警告。

**解决方案**: 模块级警告抑制
```python
# 在 src/infrastructure/ocr/mineru_ocr_service.py 顶部
import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', message='.*copy.*')
```

### 问题 2: SSL/代理错误
**状态**: ✅ **已修复**

环境代理设置导致 CDN 连接失败。

**解决方案**: 清理代理环境变量
```bash
# 运行前清理代理变量
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
unset SOCKS_PROXY socks_proxy ALL_PROXY all_proxy
```

---

## 📊 最新测试结果

```
INPUT: simple_pdfs/sample_chinese.pdf
OUTPUT: outputs/final_test/

Language Detection:  ✓ zh → ch (MinerU API)
NumPy Warnings:     ✓ 0 warnings
SSL Errors:         ✓ 0 errors
MinerU Batch ID:    0dd37c51-3efa-4738-8dd6-549cc502bb0d
ZIP Download:       ✓ 8 files
Image Extraction:   ✓ 3 images
Processing Time:    5.69s (MinerU) + 733.99s (Evidence) = ~12 min total
Arbiter Score:      8.0/100
```

---

## 🔧 日常运行检查清单

### 启动管道前

- [ ] 清理代理环境变量
- [ ] 确保网络连接正常 (无代理干扰)
- [ ] FastText 模型已缓存 (~/.fasttext_models/lid.176.ftz)

### 监控运行

查看这些日志行：

```
# ✅ 正常的语言检测日志
"Mapped FastText detected language zh -> ch for MinerU"
"Detected PDF language: ch"
"Got batch_id=..."
"PDF uploaded successfully"
"✓ Processing complete at attempt 3"
"✓ Extracted 8 files"

# ❌ 需要关注的日志
"FastText language detection failed"  (应该只有 DEBUG 级别)
"SSLError" or "UNEXPECTED_EOF_WHILE_READING"  (代理问题)
"batch_id=None"  (MinerU API 问题)
```

### 成功完成标志

```
Processing complete
...
Evidence processing complete: score=X.X, iterations=N
✓ 完整管线处理 | XXXs
```

---

## 📝 日志级别说明

| 日志级别 | 含义 | 示例 |
|---------|------|------|
| INFO | 正常操作 | "Detected PDF language: ch" |
| WARNING | 需要注意但不致命 | "KB similarity low (0.548); triggering fallback" |
| ERROR | 严重错误，可能导致失败 | "Failed to download FastText model" |
| DEBUG | 详细调试信息 | "Using cached FastText model: ..." |

---

## 🚨 常见问题排查

### Q1: 出现 "Unable to avoid copy while creating an array" 警告
**A**: 这是 FastText 的 NumPy 2.0 兼容性警告，已在模块级别被抑制。如果仍然看到，说明：
- 可能是 DEBUG 日志（正常）
- 或者有新的 FastText 版本冲突

**解决**: 检查 warnings.filterwarnings 是否在文件顶部

### Q2: SSL 连接错误 SSLEOFError
**A**: 环境代理变量干扰了连接。

**解决**:
```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY SOCKS_PROXY socks_proxy ALL_PROXY all_proxy
# 然后重新运行
python main.py "input.pdf"
```

### Q3: FastText 模型加载失败 "lid.176.ftz cannot be opened"
**A**: 模型文件不存在或损坏。

**解决**:
```bash
# 删除缓存
rm -rf ~/.fasttext_models/

# 重新运行（会自动下载模型）
python main.py "input.pdf"
```

### Q4: MinerU batch_id 为 None
**A**: MinerU API 调用失败。

**检查**:
- 网络连接是否正常
- 代理设置是否清理
- API 服务是否在线

---

## 📈 性能指标

### 处理时间分布

```
Chinese PDF (sample_chinese.pdf):
├── MinerU 处理:     5.69s
├── 翻译:            0.00s  (已是英文)
├── 证据提取:        733.99s (长期任务)
├── 高亮:            0.00s
└── 报告生成:        0.00s
┗━ 总计:            ~12 分钟
```

### 并发限制

- 同时最多 1 个 PDF 处理 (由于 MinerU API 限制)
- FastText 模型在内存中只加载一次 (类级别缓存)
- 知识库索引在首次加载后被缓存

---

## 🔐 生产环境配置

### 推荐的环境变量

```bash
# 清理代理 (确保无代理)
unset http_proxy
unset https_proxy
unset HTTP_PROXY
unset HTTPS_PROXY
unset SOCKS_PROXY
unset socks_proxy
unset ALL_PROXY
unset all_proxy

# 设置日志级别 (可选)
export LOG_LEVEL=INFO

# 设置输出目录
export OUTPUT_DIR=/path/to/outputs
```

### 启动脚本示例

```bash
#!/bin/bash

# 清理代理环境
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY SOCKS_PROXY socks_proxy ALL_PROXY all_proxy

# 启动处理
cd /home/lanshi/Documents/Graduate/02_Research/05_Multi-ACMG-MinerU-demo
python main.py "$1" --out-dir outputs/

echo "Processing complete!"
```

---

## 📞 支持

如果遇到其他问题，检查：
1. `docs/PRODUCTION_FIX_SUMMARY.md` - 详细修复说明
2. `docs/FASTTEXT_INTEGRATION.md` - FastText 集成细节
3. `docs/DEPLOYMENT_AND_USAGE_GUIDE.md` - 部署指南

