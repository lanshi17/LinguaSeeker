"""快速参考指南 - 重构架构速查"""

# 重构架构快速参考

## 核心组件一览

### 1. 接口层

#### IPipelineStep
```python
from src.domain.interfaces.pipeline_step import IPipelineStep

# 实现这个接口来创建新的处理步骤
class MyStep(IPipelineStep):
    @property
    def name(self) -> str:
        return "my_step"
    
    def execute(self, context: IPipelineContext) -> None:
        # 实现处理逻辑
        pass
```

#### IPipelineContext
```python
from src.domain.interfaces.pipeline_step import IPipelineContext

# 用于步骤间数据传递
context.get(key)              # 获取数据
context.set(key, value)       # 设置数据
context.has(key)              # 检查是否存在
context.update({...})         # 批量更新
context.mark_step_complete()  # 标记完成
```

#### IResultAccumulator
```python
from src.domain.interfaces.pipeline_step import IResultAccumulator

# 用于收集步骤结果
accumulator.accumulate(step_name, results)  # 累积
accumulator.build_final_payload()           # 构建最终输出
```

### 2. 步骤实现

#### PDFProcessingStep
```python
from src.application.services import PDFProcessingStep

step = PDFProcessingStep(pdf_repo, lang_detector)
# 输出: raw_text, detected_language, bbox_metadata, page_count
```

#### TranslationStep
```python
from src.application.services import TranslationStep

step = TranslationStep(translator)
# 输出: english_markdown, glossary_terms
```

#### EvidenceProcessingStep
```python
from src.application.services import EvidenceProcessingStep

step = EvidenceProcessingStep(rag_repo, evidence_extractor, arbiter)
# 输出: evidence, arbiter_score, arbiter_feedback, iterations_performed
```

#### HighlightingStep
```python
from src.application.services import HighlightingStep

step = HighlightingStep()
# 输出: highlighted_markdown, highlighted_doc_path
```

#### ReportGenerationStep
```python
from src.application.services import ReportGenerationStep

step = ReportGenerationStep()
# 输出: final_payload, final_structured_path, html_report_path
```

### 3. 上下文管理

```python
from src.application.services import PipelineContext

# 创建上下文
context = PipelineContext()

# 使用
context.set("key", value)
if context.has("key"):
    value = context.get("key")

# 追踪执行
context.mark_step_complete("step_name")
completed = context.get_completed_steps()  # ['step1', 'step2']

# 错误处理
context.record_error("step_name", "error message")
if context.has_errors():
    errors = context.get_errors()

# 获取执行摘要
summary = context.get_execution_summary()
```

### 4. 结果累积

```python
from src.application.services import ResultAccumulator

# 创建累积器
accumulator = ResultAccumulator()

# 累积结果
accumulator.accumulate("pdf_processing", {"key": "value"})
accumulator.accumulate("translation", {"key": "value"})

# 获取全部结果
results = accumulator.get_accumulated()
# {"pdf_processing": {...}, "translation": {...}}

# 构建最终输出
payload = accumulator.build_final_payload()

# 添加元数据
accumulator.add_metadata("timestamp", datetime.now())
```

### 5. 协调器

```python
from src.application.services import RefactoredPipelineOrchestrator

# 创建协调器
steps = [
    PDFProcessingStep(...),
    TranslationStep(...),
    EvidenceProcessingStep(...),
    HighlightingStep(),
    ReportGenerationStep(),
]
orchestrator = RefactoredPipelineOrchestrator(steps)

# 执行
request = ProcessPDFRequest("input.pdf", "outputs")
response = orchestrator.process_pdf(request)

# 获取摘要
summary = orchestrator.get_execution_summary()
results = orchestrator.get_accumulated_results()
```

### 6. 工厂模式（推荐）

```python
from src.application.services import PipelineFactory

# 快速创建处理器
processor = PipelineFactory.create_processor_with_defaults(
    cfg, pdf_repo, rag_repo, lang_detector, 
    translator, evidence_extractor, arbiter
)

# 使用处理器
response = processor.process_pdf(request)
```

## 常见使用场景

### 场景 1: 使用默认管道

```python
from src.domain.interfaces import run_pipeline_refactored

# 最简单的方式
result = run_pipeline_refactored("input.pdf", "outputs")
```

### 场景 2: 自定义步骤

```python
from src.domain.interfaces.pipeline_step import IPipelineStep

class CustomValidationStep(IPipelineStep):
    @property
    def name(self) -> str:
        return "custom_validation"
    
    @property
    def description(self) -> str:
        return "自定义验证步骤"
    
    def validate_prerequisites(self, context) -> bool:
        return context.has("evidence")
    
    def execute(self, context) -> None:
        evidence = context.get("evidence")
        # 自定义验证逻辑
        is_valid = self._validate(evidence)
        context.update({"is_valid": is_valid})
        context.mark_step_complete(self.name)
    
    def rollback(self, context) -> None:
        context.remove("is_valid")
    
    def _validate(self, evidence) -> bool:
        # 验证逻辑
        pass
```

### 场景 3: 跳过某个步骤

```python
# 创建不包含报告生成的管道
steps = [
    PDFProcessingStep(...),
    TranslationStep(...),
    EvidenceProcessingStep(...),
    HighlightingStep(),
    # 跳过 ReportGenerationStep
]
orchestrator = RefactoredPipelineOrchestrator(steps)
```

### 场景 4: 添加中间步骤

```python
# 在高亮和报告生成之间添加自定义步骤
steps = [
    PDFProcessingStep(...),
    TranslationStep(...),
    EvidenceProcessingStep(...),
    HighlightingStep(),
    CustomValidationStep(),        # 新增
    ReportGenerationStep(),
]
```

### 场景 5: 获取执行统计

```python
orchestrator = RefactoredPipelineOrchestrator(steps)
response = orchestrator.process_pdf(request)

# 获取执行摘要
summary = orchestrator.get_execution_summary()
print(f"已完成步骤: {summary['completed_steps']}")
print(f"总步骤数: {summary['total_steps']}")
print(f"是否有错误: {summary['has_errors']}")
print(f"错误详情: {summary['errors']}")

# 获取每个步骤的执行时间
durations = summary['step_durations']
for step, duration in durations.items():
    print(f"{step}: {duration:.2f}s")
```

## 数据流速查

### 完整数据流

```
PDF 输入
  ↓
PDFProcessingStep
  输出: raw_text, detected_language, bbox_metadata, page_count
  ↓
TranslationStep
  输入: raw_text, detected_language, page_count
  输出: english_markdown, glossary_terms
  ↓
EvidenceProcessingStep
  输入: english_markdown, bbox_metadata
  输出: evidence, arbiter_score, arbiter_feedback, iterations_performed
  ↓
HighlightingStep
  输入: english_markdown, evidence, bbox_metadata
  输出: highlighted_markdown, highlighted_doc_path
  ↓
ReportGenerationStep
  输入: evidence, arbiter_feedback, 其他所有输出
  输出: final_payload, final_structured_path, html_report_path
  ↓
ProcessPDFResponse（最终输出）
```

## 工具服务

### BBoxMetadataManager
```python
from src.infrastructure.utils.pipeline_utils import BBoxMetadataManager

# 保存元数据
BBoxMetadataManager.save_bbox_metadata(bbox_list, "output.json")

# 加载元数据
bbox_data = BBoxMetadataManager.load_bbox_metadata("output.json")

# 查找匹配
bbox = BBoxMetadataManager.find_bbox_for_text("查询文本", bbox_list)
```

### GlossaryExtractor
```python
from src.infrastructure.utils.pipeline_utils import GlossaryExtractor

# 提取术语表
terms = GlossaryExtractor.extract_glossary_terms(text, top_k=12)

# 格式化提示
hint = GlossaryExtractor.format_glossary_hint(terms)
```

### PayloadBuilder
```python
from src.infrastructure.utils.pipeline_utils import PayloadBuilder

# 构建证据部分
evidence_payload = PayloadBuilder.build_evidence_payload(
    evidence, arbiter_feedback, bbox_metadata
)

# 构建路径部分
paths_payload = PayloadBuilder.build_paths_payload(context_dict)

# 构建元数据部分
metadata_payload = PayloadBuilder.build_metadata_payload(
    detected_language, page_count, iterations
)
```

## 错误处理

### 完整的错误处理

```python
try:
    orchestrator = RefactoredPipelineOrchestrator(steps)
    response = orchestrator.process_pdf(request)
except Exception as e:
    # 获取执行摘要中的错误
    summary = orchestrator.get_execution_summary()
    
    if summary['has_errors']:
        for step, error in summary['errors'].items():
            print(f"步骤 {step} 失败: {error}")
    
    # 访问已完成的步骤
    print(f"已完成步骤: {summary['completed_steps']}")
    
    # 获取执行时间（用于调试）
    print(f"执行时间: {summary['step_durations']}")
```

### 步骤级错误处理

```python
def execute(self, context: IPipelineContext) -> None:
    try:
        # 验证前置条件
        if not self.validate_prerequisites(context):
            raise RuntimeError("前置条件不满足")
        
        # 记录开始时间
        context.record_step_start(self.name)
        
        # 执行逻辑
        result = self._do_work()
        
        # 更新上下文
        context.update({"result": result})
        
        # 标记完成
        context.mark_step_complete(self.name)
        
    except Exception as e:
        # 记录错误
        context.record_error(self.name, str(e))
        # 重新抛出以让协调器处理
        raise
```

## 向后兼容

### 使用旧 API（仍然可用）

```python
# ✅ 旧代码仍然工作
from src.domain.interfaces import run_pipeline
result = run_pipeline("input.pdf", "outputs")
```

### 迁移到新 API

```python
# ✅ 推荐的新方式
from src.domain.interfaces import run_pipeline_refactored
result = run_pipeline_refactored("input.pdf", "outputs")
```

## 性能优化建议

1. **缓存译文**：TranslationStep 可缓存翻译结果
2. **并行提取**：HighlightingStep 可与 ReportGenerationStep 并行
3. **增量处理**：支持重新启动从特定步骤
4. **结果缓存**：EvidenceProcessingStep 可缓存知识库索引

## 测试示例

### 单步骤测试

```python
def test_translation_step():
    # Mock 依赖
    translator = Mock()
    translator.translate_to_english.return_value = "Translated text"
    
    # 创建步骤
    step = TranslationStep(translator)
    
    # 创建上下文
    context = PipelineContext()
    context.update({
        "raw_text": "原文本",
        "detected_language": Language.JAPANESE,
        "page_count": 5,
        "translated_doc_path": "/tmp/output.md",
    })
    
    # 执行
    step.execute(context)
    
    # 验证
    assert context.has("english_markdown")
    assert context.is_step_complete("translation")
    assert len(context.get("english_markdown")) > 0
```

### 集成测试

```python
def test_pipeline_integration():
    # 设置所有依赖
    pdf_repo = Mock()
    lang_detector = Mock()
    # ... 其他 mock
    
    # 创建管道
    processor = PipelineFactory.create_processor_with_defaults(
        cfg, pdf_repo, rag_repo, lang_detector,
        translator, evidence_extractor, arbiter
    )
    
    # 执行
    request = ProcessPDFRequest("test.pdf", "/tmp")
    response = processor.process_pdf(request)
    
    # 验证结果
    assert response.detected_language is not None
    assert response.arbiter_score >= 0
    assert response.evidence is not None
    
    # 验证执行统计
    summary = processor.orchestrator.get_execution_summary()
    assert len(summary['completed_steps']) == 5  # 所有5个步骤完成
    assert not summary['has_errors']
```

## 快速决策树

```
需要处理 PDF？
  ├─ 使用默认管道？ 
  │   └─ YES → run_pipeline_refactored()
  │
  ├─ 需要自定义步骤？
  │   ├─ YES → 继承 IPipelineStep 创建自定义类
  │   └─ NO  → 使用现有步骤
  │
  ├─ 需要跳过某些步骤？
  │   └─ YES → 从步骤列表中删除对应步骤
  │
  ├─ 需要改变步骤顺序？
  │   └─ YES → 重新排列步骤列表
  │
  └─ 需要获取执行统计？
      └─ YES → orchestrator.get_execution_summary()
```

## 环境变量

```bash
# 配置应用
export OPENAI_API_KEY=your_key
export OPENAI_API_BASE=your_base
export EMBEDDING_MODEL=text-embedding-3-small
export LLM_MODEL=gpt-4-turbo

# 运行管道
python main.py input.pdf --out-dir outputs
```

