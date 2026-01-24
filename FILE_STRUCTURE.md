"""重构后的项目文件结构"""

# 📁 重构后项目文件结构

## 新增文件清单

### 1. 接口层 (`src/domain/interfaces/`)

```
src/domain/interfaces/
├── __init__.py (更新)
│   - 导出新接口: IPipelineStep, IPipelineContext, IResultAccumulator
│   - 新增函数: run_pipeline_refactored()
│   - 保持向后兼容: run_pipeline()
│
└── pipeline_step.py (新增 - 4.9KB)
    ├── IPipelineStep - 管道步骤接口
    │   ├── name: str (步骤名称)
    │   ├── description: str (步骤描述)
    │   ├── execute(context) (执行步骤)
    │   ├── validate_prerequisites(context) (前置条件验证)
    │   └── rollback(context) (回滚操作)
    │
    ├── IPipelineContext - 管道上下文接口
    │   ├── get/set/update/remove (参数访问)
    │   ├── has (参数存在性检查)
    │   ├── mark_step_complete (标记完成)
    │   ├── is_step_complete (检查完成)
    │   └── get_completed_steps (获取完成列表)
    │
    └── IResultAccumulator - 结果累积器接口
        ├── accumulate(step_name, results) (累积)
        ├── get_accumulated() (获取累积)
        ├── build_final_payload() (构建最终输出)
        ├── add_metadata(key, value) (添加元数据)
        └── clear() (清除)
```

### 2. 应用服务层 (`src/application/services/`)

```
src/application/services/
├── __init__.py (更新)
│   导出: RefactoredPipelineOrchestrator, PipelineContext, 
│          ResultAccumulator, 所有步骤类
│
├── pipeline_context.py (新增 - 150行)
│   └── PipelineContext (IPipelineContext的具体实现)
│       ├── 参数管理: get, set, update, has, remove
│       ├── 步骤追踪: mark_step_complete, is_step_complete
│       ├── 执行监控: record_step_start, get_step_duration
│       └── 错误管理: record_error, has_errors, get_errors
│
├── result_accumulator.py (新增 - 120行)
│   └── ResultAccumulator (IResultAccumulator的具体实现)
│       ├── 结果收集: accumulate, get_accumulated
│       ├── 输出构建: build_final_payload
│       ├── 元数据: add_metadata
│       └── 结果查询: get_step_result, has_step_results
│
├── pdf_processing_step.py (新增 - 140行)
│   └── PDFProcessingStep (IPipelineStep实现)
│       单一职责: PDF文本提取、语言检测、BBox提取
│       输入: pdf_path, out_dir
│       输出: raw_text, detected_language, bbox_metadata, page_count
│
├── translation_step.py (新增 - 180行)
│   └── TranslationStep (IPipelineStep实现)
│       单一职责: 文档翻译、术语一致性管理
│       输入: raw_text, detected_language, page_count
│       输出: english_markdown, glossary_terms
│       特性: 分块处理、术语提取、一致性维护
│
├── evidence_processing_step.py (新增 - 200行)
│   └── EvidenceProcessingStep (IPipelineStep实现)
│       单一职责: 证据提取、迭代改进、质量评分
│       输入: english_markdown, bbox_metadata
│       输出: evidence, arbiter_score, arbiter_feedback
│       特性: KB检索、迭代优化、二级搜索
│
├── highlighting_step.py (新增 - 120行)
│   └── HighlightingStep (IPipelineStep实现)
│       单一职责: 文档高亮显示
│       输入: english_markdown, evidence, bbox_metadata
│       输出: highlighted_markdown, highlighted_doc_path
│       特性: BBox智能匹配
│
├── report_generation_step.py (新增 - 230行)
│   └── ReportGenerationStep (IPipelineStep实现)
│       单一职责: 最终报告生成
│       输入: evidence, arbiter_feedback, 所有前步输出
│       输出: final_payload, html_report_path
│       特性: JSON构建、HTML生成、图表提取
│
├── refactored_pipeline_orchestrator.py (新增 - 200行)
│   └── RefactoredPipelineOrchestrator
│       职责: 协调步骤执行、管理上下文、收集结果
│       方法:
│       ├── process_pdf() - 执行完整管道
│       ├── _execute_step() - 执行单个步骤
│       ├── _extract_step_results() - 提取结果
│       ├── _rollback_steps() - 回滚所有步骤
│       └── _build_response() - 构建最终响应
│
└── pipeline_adapter.py (新增 - 140行)
    ├── PipelineFactory
    │   ├── create_orchestrator() - 创建协调器
    │   └── create_processor_with_defaults() - 快速创建处理器
    │
    └── PipelineProcessor
        ├── process_pdf() - 处理PDF
        ├── get_execution_summary() - 执行摘要
        └── get_accumulated_results() - 累积结果

保持兼容: pipeline_orchestrator.py (原始文件保留)
```

### 3. 基础设施工具层 (`src/infrastructure/utils/`)

```
src/infrastructure/utils/
└── pipeline_utils.py (新增 - 工具集合)
    ├── BBoxMetadataManager
    │   ├── save_bbox_metadata() - 保存元数据
    │   ├── load_bbox_metadata() - 加载元数据
    │   └── find_bbox_for_text() - 查找匹配
    │
    ├── GlossaryExtractor
    │   ├── extract_glossary_terms() - 提取术语
    │   └── format_glossary_hint() - 格式化提示
    │
    └── PayloadBuilder
        ├── build_evidence_payload() - 构建证据部分
        ├── build_paths_payload() - 构建路径部分
        └── build_metadata_payload() - 构建元数据部分
```

### 4. 文档 (`docs/`)

```
docs/
├── REFACTORING_GUIDE.md (新增 - 完整指南)
│   ├── 概述
│   ├── 核心改进
│   ├── 接口层抽象
│   ├── 上下文管理
│   ├── 结果累积
│   ├── 管道步骤实现详解
│   ├── 新协调器
│   ├── 工厂模式
│   ├── 工具服务
│   ├── 架构对比
│   ├── 使用指南
│   ├── 测试改进
│   └── SOLID原则遵循
│
├── REFACTORING_CHECKLIST.md (新增 - 检查清单)
│   ├── 重构完成项
│   ├── 代码质量检查
│   ├── 职责分离检查
│   ├── 业务逻辑完整性验证
│   ├── 接口设计检查
│   ├── 依赖注入检查
│   ├── 测试可测性分析
│   ├── 向后兼容性验证
│   ├── 性能验证
│   └── 实施后续建议
│
└── QUICK_REFERENCE.md (新增 - 快速参考)
    ├── 核心组件一览
    ├── 常见使用场景
    ├── 数据流速查
    ├── 工具服务
    ├── 错误处理
    ├── 向后兼容
    ├── 性能优化建议
    ├── 测试示例
    ├── 快速决策树
    └── 环境变量
```

### 5. 项目根目录

```
project_root/
└── REFACTORING_SUMMARY.md (新增 - 总结报告)
    ├── 项目信息
    ├── 重构目标
    ├── 重构成果
    ├── 文档完整性
    ├── 使用方式
    ├── 向后兼容性
    ├── 性能改进
    ├── SOLID原则遵循
    ├── 代码质量指标
    └── 总结
```

## 文件统计

### 代码文件

| 分类 | 文件数 | 总行数 | 平均行数 |
|------|--------|--------|----------|
| 接口 | 1 | 165 | 165 |
| 步骤 | 5 | 870 | 174 |
| 上下文/累积 | 2 | 270 | 135 |
| 协调/工厂 | 2 | 340 | 170 |
| 工具 | 1 | 150 | 150 |
| **合计** | **11** | **1795** | **163** |

### 文档文件

| 文件 | 行数 | 内容 |
|------|------|------|
| REFACTORING_GUIDE.md | 500+ | 详细架构指南 |
| REFACTORING_CHECKLIST.md | 400+ | 实施检查清单 |
| QUICK_REFERENCE.md | 350+ | 快速参考 |
| REFACTORING_SUMMARY.md | 300+ | 总结报告 |
| **合计** | **1550+** | **完整文档** |

## 依赖关系图

```
项目应用层
    ↓
run_pipeline_refactored()
    ├── PipelineFactory
    │   └── create_processor_with_defaults()
    │       └── RefactoredPipelineOrchestrator
    │           └── IPipelineStep[] (5个步骤)
    │               ├── PDFProcessingStep
    │               ├── TranslationStep
    │               ├── EvidenceProcessingStep
    │               ├── HighlightingStep
    │               └── ReportGenerationStep
    │
    ├── PipelineContext (IPipelineContext实现)
    │   └── 管理上下文和状态
    │
    └── ResultAccumulator (IResultAccumulator实现)
        └── 收集和组织结果
```

## 类继承/实现关系

```
接口层 (Domain)
├── IPipelineStep (interface)
│   ├── PDFProcessingStep ✓
│   ├── TranslationStep ✓
│   ├── EvidenceProcessingStep ✓
│   ├── HighlightingStep ✓
│   └── ReportGenerationStep ✓
│
├── IPipelineContext (interface)
│   └── PipelineContext ✓
│
└── IResultAccumulator (interface)
    └── ResultAccumulator ✓

协调层 (Application)
├── RefactoredPipelineOrchestrator
│   ├── 使用 IPipelineStep[]
│   ├── 使用 PipelineContext
│   └── 使用 ResultAccumulator
│
├── PipelineFactory
│   └── 创建 RefactoredPipelineOrchestrator
│
└── PipelineProcessor
    └── 使用 RefactoredPipelineOrchestrator

工具层 (Infrastructure)
├── BBoxMetadataManager
├── GlossaryExtractor
└── PayloadBuilder
```

## 初始化导出

### `src/domain/interfaces/__init__.py`

```python
from .pipeline_step import IPipelineStep, IPipelineContext, IResultAccumulator

def run_pipeline_refactored(pdf_path, out_dir="outputs"):
    """新的推荐API"""
    
def run_pipeline(pdf_path, out_dir="outputs"):
    """保留的旧API（向后兼容）"""

__all__ = [
    "run_pipeline",
    "run_pipeline_refactored",
    "IPipelineStep",
    "IPipelineContext",
    "IResultAccumulator",
    # ... 其他导出
]
```

### `src/application/services/__init__.py`

```python
from .pipeline_orchestrator import PipelineOrchestrator  # 保留
from .refactored_pipeline_orchestrator import RefactoredPipelineOrchestrator  # 新增
from .pipeline_context import PipelineContext  # 新增
from .result_accumulator import ResultAccumulator  # 新增
from .pdf_processing_step import PDFProcessingStep  # 新增
from .translation_step import TranslationStep  # 新增
from .evidence_processing_step import EvidenceProcessingStep  # 新增
from .highlighting_step import HighlightingStep  # 新增
from .report_generation_step import ReportGenerationStep  # 新增
from .pipeline_adapter import PipelineFactory, PipelineProcessor  # 新增

__all__ = [
    # 新的类
    "RefactoredPipelineOrchestrator",
    "PipelineContext",
    "ResultAccumulator",
    "PDFProcessingStep",
    "TranslationStep",
    "EvidenceProcessingStep",
    "HighlightingStep",
    "ReportGenerationStep",
    "PipelineFactory",
    "PipelineProcessor",
    # 保留的类
    "PipelineOrchestrator",
]
```

## 快速文件查找

### 查找特定功能的实现

```bash
# 查找PDF处理
grep -r "class PDFProcessingStep" src/

# 查找翻译
grep -r "class TranslationStep" src/

# 查找证据提取
grep -r "class EvidenceProcessingStep" src/

# 查找高亮
grep -r "class HighlightingStep" src/

# 查找报告生成
grep -r "class ReportGenerationStep" src/

# 查找协调器
grep -r "class RefactoredPipelineOrchestrator" src/

# 查找接口定义
grep -r "class IPipelineStep" src/
```

## 代码质量特性

### 所有新文件的特性

✅ **单一职责**: 每个类只负责一个职责
✅ **接口清晰**: 通过接口定义清晰合同
✅ **依赖注入**: 构造函数注入所有依赖
✅ **错误处理**: 完整的前置条件验证和错误记录
✅ **可测试性**: 支持模拟依赖的独立测试
✅ **可维护性**: 代码分散在逻辑单元中
✅ **可扩展性**: 易于添加新步骤
✅ **向后兼容**: 保留原有API

