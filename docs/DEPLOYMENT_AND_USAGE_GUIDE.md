# 5阶段结构化PDF处理流程 - 部署和使用手册

## 目录
1. [快速开始](#快速开始)
2. [系统要求](#系统要求)
3. [配置](#配置)
4. [使用指南](#使用指南)
5. [API参考](#api参考)
6. [故障排除](#故障排除)
7. [验证清单](#验收清单)

---

## 快速开始

### 最小化设置

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.development .env
# 编辑 .env，填入必需的API密钥和端点

# 3. 运行5阶段流程
python -m src.application.five_stages_main_entry \
    --pdf-path /path/to/paper.pdf \
    --output-dir /path/to/output
```

---

## 系统要求

### 硬件要求
- CPU: 4核或更高
- 内存: 8GB 最小，16GB 推荐
- 存储: 20GB 可用空间（用于缓存和输出）
- 网络: 稳定的互联网连接（用于API调用）

### 软件要求
- Python 3.8+
- 操作系统: Linux, macOS, Windows
- 必需库: BeautifulSoup4, requests, python-dotenv, pytest

### 外部依赖
- **MinerU SDK**: v≥2.4.0
- **Qwen-MT-Plus**: 通过 Dashscope 的 OpenAI 兼容 API
- **Qdrant 向量数据库**: 已配置并可访问
- **Claude LLM**: 通过 Anthropic 或兼容 API
- **DeepSeek-V3**: 通过 SiliconFlow 或兼容 API

---

## 配置

### 环境变量 (.env.development)

```bash
# ==================== 应用配置 ====================
APP_NAME="ACMG-PS3 Intelligence System"
APP_VERSION="2.1.0"
ENVIRONMENT="production"
DEBUG="false"
LOG_LEVEL="INFO"

# ==================== MinerU 配置 ====================
MINERU_MODE="api"
MINERU_API_URL="https://mineru.net/api/v4/extract/task"
MINERU_API_TOKEN="your_mineru_token"
MINERU_TIMEOUT="300"
MINERU_MAX_FILE_SIZE_MB="100"

# ==================== 翻译LLM (Qwen-MT-Plus) ====================
MT_LLM_API_KEY="sk-..."
MT_LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
MT_LLM_MODEL="qwen-mt-plus"
LLM_TEMPERATURE="0"
LLM_MAX_TOKENS="2000"

# ==================== 仲裁LLM (Claude) ====================
CLAUDE_API_KEY="sk-..."
CLAUDE_MODEL="claude-haiku-4-5-20251001"
ANTHROPIC_BASE_URL="https://yunwu.ai/v1"

# ==================== 向量数据库 (Qdrant) ====================
QDRANT_HOST="https://..."
QDRANT_API_KEY="..."
QDRANT_COLLECTION_NAME="acmg_history"
QDRANT_DIMENSION="1536"

# ==================== 任务配置 ====================
MAX_REASONING_ITERATIONS="3"
TASK_TIMEOUT_SECONDS="3600"
```

### 验证配置

```bash
# 测试MinerU连接
python -c "from src.infrastructure.repositories.pdf_repository import PDFRepository; PDFRepository().test_mineru_connection()"

# 测试Qdrant连接
python -c "from src.infrastructure.repositories.rag_repository import RAGRepository; RAGRepository().test_qdrant_connection()"

# 测试LLM连接
python -c "from src.infrastructure.llm import get_llm_client; get_llm_client('claude').test_connection()"
```

---

## 使用指南

### 命令行使用

```bash
python -m src.application.five_stages_main_entry \
    --pdf-path /path/to/paper.pdf \
    --output-dir ./output \
    --language auto
```

**参数说明**:
- `--pdf-path`: PDF文件路径（必需）
- `--output-dir`: 输出目录（必需）
- `--language`: 源语言（可选，默认自动检测）

### Python API使用

```python
from src.application.services.complete_five_stages_pipeline import CompleteFiveStagesPipelineOrchestrator
from src.application.dto import ProcessPDFRequest
from src.infrastructure.repositories import PDFRepository, RAGRepository

# 初始化
pdf_repo = PDFRepository()
rag_repo = RAGRepository()
orchestrator = CompleteFiveStagesPipelineOrchestrator(
    pdf_repository=pdf_repo,
    rag_repository=rag_repo
)

# 处理PDF
request = ProcessPDFRequest(
    pdf_path="/path/to/paper.pdf",
    out_dir="./output"
)

response = orchestrator.process_pdf(request)

if response.success:
    # 访问所有输出变量（保留{{占位符}}格式）
    results = response.results
    print(f"Evidence level: {results['ps3_evidence_result']['ps3_evidence_level']}")
    print(f"Arbiter score: {results['arbiter_score']}")
    print(f"Final JSON: {results['final_evidence_json']}")
else:
    print(f"Error: {response.error_message}")
```

### 输出文件结构

```
output_dir/
├── stage1_mineru_html_extraction/
│   ├── original.html                      # {{original_structured_html}}
│   ├── bbox_metadata.json                 # {{bbox_metadata_path}}
│   ├── figures/
│   │   ├── figure_1.png
│   │   └── ...
│   └── metadata.json
├── stage2_html_translation/
│   ├── translated_english.html            # {{translated_english_html}}
│   └── metadata.json
├── stage3_ps3_extraction/
│   ├── stage3_ps3_evidence.json           # {{ps3_evidence_result}}
│   └── rag_search_log.json
├── stage4_arbiter_review/
│   ├── stage4_arbiter_review.json         # {{arbiter_score}}, {{iterations_performed}}
│   └── iteration_details.json
├── stage5_result_structuring/
│   ├── stage5_final_result.json           # {{final_evidence_json}}
│   ├── stage5_final_annotated_doc.html    # {{final_annotated_doc}}
│   ├── stage5_dual_language_view.html     # {{dual_language_view}}
│   └── metadata.json
├── results_manifest.json                   # 所有{{占位符}}变量总结
└── processing_log.txt                      # 完整执行日志
```

---

## API参考

### CompleteFiveStagesPipelineOrchestrator

```python
class CompleteFiveStagesPipelineOrchestrator:
    """5阶段PDF处理管道编排器"""
    
    def __init__(
        self,
        pdf_repository,
        rag_repository,
        mt_llm_client=None,
        arbiter_llm_client=None
    ):
        """初始化管道"""
        pass
    
    def process_pdf(self, request: ProcessPDFRequest) -> ProcessPDFResponse:
        """处理PDF并返回结果"""
        pass
```

### ProcessPDFRequest

```python
@dataclass
class ProcessPDFRequest:
    pdf_path: str           # PDF文件路径
    out_dir: str           # 输出目录
    language: str = "auto"  # 源语言（可选）
```

### ProcessPDFResponse

```python
@dataclass
class ProcessPDFResponse:
    success: bool                          # 是否成功
    output_dir: str                        # 输出目录
    results: Dict[str, Any] = field(...)   # 所有{{占位符}}变量
    error_message: str = ""                # 错误信息（如有）
```

### 返回的结果字典

```python
results = {
    # Stage 1
    "original_structured_html": "{{original_structured_html}}",
    "detected_language": "{{detected_language}}",
    "bbox_metadata_path": "{{bbox_metadata_path}}",
    
    # Stage 2
    "translated_english_html": "{{translated_english_html}}",
    
    # Stage 3
    "ps3_evidence_result": {...},  # Dict
    
    # Stage 4
    "arbiter_score": <int>,
    "iterations_performed": <int>,
    
    # Stage 5
    "final_evidence_json": {...},  # Dict
    "final_annotated_doc": "{{final_annotated_doc}}",
    "dual_language_view": "{{dual_language_view}}",
}
```

---

## 故障排除

### 常见问题

#### Q1: MinerU API 连接失败
```
错误: "Failed to connect to MinerU API"
```
**解决方案**:
1. 检查网络连接
2. 验证 MINERU_API_TOKEN 是否有效
3. 检查 MINERU_API_URL 是否正确
4. 确保PDF文件大小 < MINERU_MAX_FILE_SIZE_MB

#### Q2: Qdrant 向量检索未命中
```
错误: "No relevant documents found in vector DB"
```
**解决方案**:
1. 检查 QDRANT_COLLECTION_NAME 是否正确
2. 验证向量库是否已初始化并包含PS3相关文档
3. 检查相似度阈值（默认0.65）
4. 运行实时向量化回退（自动执行）

#### Q3: Qwen-MT 翻译超时
```
错误: "Translation request timed out"
```
**解决方案**:
1. 检查网络延迟
2. 考虑分段翻译超长文档
3. 增加 LLM_TIMEOUT 值
4. 检查输入文本的token数量（限制8,192）

#### Q4: 仲裁评分无法达到80分
```
警告: "Max iterations reached with score < 80"
```
**解决方案**:
1. 查看 stage4_arbiter_review.json 中的反馈
2. 检查 P1/P2 数据是否充分报告
3. 检查实验对照和重复设计
4. 增加 MAX_REASONING_ITERATIONS 值

### 调试模式

```bash
# 启用详细日志
export LOG_LEVEL=DEBUG
python -m src.application.five_stages_main_entry --pdf-path ... --output-dir ...

# 输出所有stage执行时间
export TIMER_VERBOSE=true
python -m src.application.five_stages_main_entry --pdf-path ... --output-dir ...
```

### 日志位置

```bash
# 查看实时日志
tail -f logs/pipeline_$(date +%Y%m%d).log

# 查看特定stage的日志
grep "STAGE-3" logs/pipeline_*.log
```

---

## 验收清单

### Stage-1 验收标准
- [ ] ✓ 所有文本块均含准确 data-bbox 坐标属性（像素单位）
- [ ] ✓ 表格保留HTML table结构，图表区域含 <img> 及标题
- [ ] ✓ 后续阶段可直接通过 querySelectorAll('[data-bbox]') 定位内容
- [ ] ✓ 文档可读、排版合理，逻辑顺序与原文一致
- [ ] ✓ 所有图表均有标题文本和对应截图
- [ ] ✓ JSON元数据完整覆盖全文，无大段缺失、乱码或顺序错乱
- [ ] ✓ Bbox坐标为像素单位，整体字符级精度 ≥99.3%
- [ ] ✓ 语言变量 {{detected_language}} 已正确生成
- [ ] ✓ 超长文档（>30页）启用分段处理且术语一致
- [ ] ✓ 所有输出文件已本地持久化，路径可被后续阶段直接引用
- [ ] ✓ MinerU SDK 仅执行PDF→HTML转换，未执行任何翻译操作

### Stage-2 验收标准
- [ ] ✓ {{translated_english_html}} 与 {{original_structured_html}} DOM结构完全一致
- [ ] ✓ 所有 data-bbox 属性保留且未被修改
- [ ] ✓ 仅文本内容被翻译，无额外标签或结构变更
- [ ] ✓ 翻译后文档可读、术语准确，符合学术语境
- [ ] ✓ 文件已本地持久化，路径可被阶段三直接引用

### Stage-3 验收标准
- [ ] ✓ 所有输出字段必须存在且类型正确
- [ ] ✓ 若标注为 PS3/BS3 及其子类，必须提供有效的 P1/P2 坐标或明确说明"not reported"
- [ ] ✓ OddsPath 计算仅在 P1 和 P2 均可量化时执行
- [ ] ✓ 证据等级必须严格匹配 OddsPath 数值区间或支持性条件
- [ ] ✓ reasoning_summary 需引用原文位置（页码 + bbox）或关键词上下文
- [ ] ✓ RAG检索必须优先使用向量知识库，仅在未命中时回退至静态PDF实时向量化

### Stage-4 验收标准
- [ ] ✓ {{arbiter_score}} ≥ 80 或已达最大迭代次数
- [ ] ✓ 每次迭代均有明确修改依据
- [ ] ✓ 溯源信息完整性与评分机制合规性是评分关键维度

### Stage-5 验收标准
- [ ] ✓ JSON 字段完整、类型正确，包含所有必需字段
- [ ] ✓ 高亮内容与证据提取结果严格对应
- [ ] ✓ 高亮位置由 bbox 元数据驱动，确保空间准确性
- [ ] ✓ 所有变量占位符 {{…}} 均保留未替换
- [ ] ✓ 最终呈现形式为 HTML 页面，左侧为原文，右侧为对照英文翻译

---

## 支持和反馈

如有问题或建议，请提交Issue或联系开发团队。

**文档版本**: 2.1.0
**更新日期**: 2026年1月24日
