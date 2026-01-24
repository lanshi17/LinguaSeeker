# MinerU 集成检查清单

## ✅ 已完成的工作

### 1. 核心服务实现
- [x] 创建 `MinerUOCRService` 类
  - [x] 实现 `pdf_to_html()` 方法
  - [x] 实现 `pdf_to_markdown()` 方法
  - [x] 实现任务提交 `_submit_task()`
  - [x] 实现轮询 `_poll_task_completion()`
  - [x] 完整的错误处理和日志

- [x] 创建 `MinerURemoteService` 类
  - [x] 支持远程 URL 处理
  - [x] 实现 `pdf_to_html_from_url()`

### 2. 仓储层集成
- [x] 更新 `PDFRepositoryImpl`
  - [x] 添加 `use_mineru` 参数
  - [x] 自动后备到 Qwen（当 MinerU 不可用时）
  - [x] 实现新的 `extract_html()` 方法
  - [x] 保持向后兼容性

### 3. 应用层集成
- [x] 更新 `PDFProcessingStep`
  - [x] 添加 MinerU HTML 提取逻辑
  - [x] 支持 `use_mineru` 上下文标志
  - [x] 存储 HTML 输出路径和内容

- [x] 创建 `HTMLProcessingStep`
  - [x] 后处理 MinerU HTML 输出
  - [x] 添加样式增强
  - [x] 验证 HTML 结构

### 4. 配置管理
- [x] 更新 `LLMConfig`
  - [x] 添加 MinerU 配置字段
  - [x] 设置默认值

- [x] 更新 `AppConfig.from_env()`
  - [x] 从环境变量加载 MinerU 配置
  - [x] 支持所有 MinerU 参数

### 5. 环境配置
- [x] `.env.development` 已包含 MinerU 配置
  - [x] `MINERU_API_URL`
  - [x] `MINERU_API_TOKEN`
  - [x] `MINERU_TIMEOUT`
  - [x] `MINERU_MAX_FILE_SIZE_MB`

### 6. 文档和示例
- [x] 创建详细集成指南 (`MINERU_INTEGRATION.md`)
- [x] 提供使用示例 (`examples/mineru_ocr_example.py`)
- [x] 创建集成测试 (`tests/test_mineru_integration.py`)

## 📋 使用步骤

### 快速开始

```python
from src.infrastructure.utils.config import AppConfig
from src.infrastructure.ocr import MinerUOCRService

# 1. 加载配置
config = AppConfig.from_env()

# 2. 创建服务
service = MinerUOCRService(config.llm)

# 3. 转换 PDF
html = service.pdf_to_html("document.pdf", "output.html")
```

### 在管道中使用

```python
from src.application.services import PipelineContext, PDFProcessingStep

context = PipelineContext()
context.update({
    "pdf_path": "document.pdf",
    "out_dir": "/output",
    "use_mineru": True,  # 启用 MinerU
})

step = PDFProcessingStep(pdf_repo, lang_detector)
step.execute(context)

html_path = context.get("html_output_path")
```

## 🔧 环境变量要求

在 `.env.development` 中确保设置：

```bash
MINERU_API_URL="https://mineru.net/api/v4/extract/task"
MINERU_API_TOKEN="your_token"  # 从官网申请
MINERU_TIMEOUT="300"
MINERU_MAX_FILE_SIZE_MB="100"
```

## ✨ 新增功能

### 1. 直接 PDF → HTML 转换
- 无需多步骤处理
- 保持原始格式和结构

### 2. 异步任务处理
- 提交任务后轮询结果
- 自动超时处理

### 3. HTML 后处理
- 自动添加样式
- 增强可读性和呈现

### 4. 多种输出格式
- HTML（完整结构）
- Markdown（从 HTML 提取）
- 纯文本

## 🧪 测试验证

运行集成测试验证实现：

```bash
# 运行所有测试
python -m pytest tests/test_mineru_integration.py -v

# 运行特定测试
python -m pytest tests/test_mineru_integration.py::MinerUIntegrationTest::test_mineru_service_initialization -v

# 手动运行
python tests/test_mineru_integration.py
```

测试覆盖：
- ✓ 服务初始化
- ✓ 配置加载
- ✓ 仓储集成
- ✓ 后备方案
- ✓ 管道支持

## 📊 性能指标

| 操作 | 预计时间 |
|-----|--------|
| 服务初始化 | < 100ms |
| 提交任务 | 1-2s |
| 轮询等待（中等 PDF） | 30-60s |
| 总转换时间（< 1MB） | 10-30s |

## 🔄 后备和兼容性

系统自动处理故障：

```python
# 如果 MinerU 初始化失败，自动使用 Qwen
repo = PDFRepositoryImpl(config.llm, use_mineru=True)

# 强制使用 Qwen（如果需要）
repo = PDFRepositoryImpl(config.llm, use_mineru=False)
```

## 📝 文件清单

### 新增文件
- ✓ `src/infrastructure/ocr/mineru_ocr_service.py` (350+ 行)
- ✓ `src/application/services/html_processing_step.py` (240+ 行)
- ✓ `examples/mineru_ocr_example.py` (180+ 行)
- ✓ `tests/test_mineru_integration.py` (300+ 行)
- ✓ `MINERU_INTEGRATION.md` (详细文档)

### 修改的文件
- ✓ `src/infrastructure/ocr/__init__.py` (导出新类)
- ✓ `src/infrastructure/repositories/pdf_repository_impl.py` (添加 extract_html)
- ✓ `src/application/services/pdf_processing_step.py` (HTML 输出支持)
- ✓ `src/application/services/__init__.py` (导出 HTMLProcessingStep)
- ✓ `src/infrastructure/utils/config.py` (MinerU 配置)

## 🚀 下一步建议

### 可选优化
1. **缓存层**：缓存已转换的 HTML
2. **并发处理**：使用线程池处理多个 PDF
3. **存储优化**：压缩 HTML 输出
4. **监控**：添加性能和错误监控
5. **文档生成**：从 HTML 生成 PDF/Word

### 集成建议
1. 在生产环境测试 MinerU API
2. 建立备用方案（Qwen OCR）
3. 配置合适的超时时间
4. 实现重试逻辑
5. 添加性能监控

## 📞 支持资源

- **官方文档**: https://mineru.net
- **API 参考**: https://mineru.net/docs/api
- **项目文档**: 见 `MINERU_INTEGRATION.md`
- **测试代码**: 见 `tests/test_mineru_integration.py`
- **使用示例**: 见 `examples/mineru_ocr_example.py`

## 🎯 验证清单

在生产部署前，请确保：

- [ ] 已从 MinerU 官网申请 API Token
- [ ] `.env.development` 中正确设置所有 MinerU 配置
- [ ] 已运行集成测试并通过
- [ ] 已在小规模数据上测试
- [ ] 已验证 HTML 输出质量
- [ ] 已备份原有的 Qwen OCR 实现
- [ ] 已更新相关文档和培训材料

---

**状态**: ✅ 完成  
**日期**: 2026年1月24日  
**版本**: 2.1.0
