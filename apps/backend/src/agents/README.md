# Agent 编排层 (Agents Layer)

Agent 编排层基于 LangGraph 实现多 Agent 协作工作流，负责文献获取、PDF 解析、实体抽取、证据推理和 ACMG 评级仲裁。

## 目录结构

```
agents/
├── __init__.py
├── supervisor.py           # Agent 监督器
└── acquisition/            # 获取 Agent
│   ├── __init__.py
│   ├── node.py
│   ├── api_tool.py
│   └── crawl_tool.py
├── parsing/                # 解析 Agent
│   ├── __init__.py
│   ├── node.py
│   ├── mineru_tool.py
│   └── translation_tool.py
├── extraction/             # 抽取 Agent
│   ├── __init__.py
│   ├── node.py
│   ├── extraction_tool.py
│   └── validator_tool.py
├── reasoning/              # 推理 Agent
│   ├── __init__.py
│   └── node.py
├── arbitration/            # 仲裁 Agent
│   ├── __init__.py
│   ├── node.py
│   ├── ps3_bs3_evaluator.py
│   └── rule_checker.py
└── interaction/            # 交互 Agent
    ├── __init__.py
    ├── node.py
    └── prompts.py
```

## 职责

Agent 编排层的主要职责：

1. **工作流编排**: 定义 Agent 执行顺序和条件
2. **状态管理**: 管理 Agent 间共享状态
3. **工具封装**: 封装外部工具供 Agent 调用
4. **决策路由**: 根据状态决定执行路径
5. **人机交互**: 处理需要人工干预的场景

## 架构位置

```
Application Layer (应用层)
    ↓
Agent Layer (Agent 编排)  ← 本层
    ↓
Domain Layer (领域层)
    ↓
Infrastructure Layer (基础设施层)
```

## Agent 工作流

### 完整流程

```
START
  ↓
route_by_source (路由)
  ↓
interaction (交互 Agent) ────→ human_review (人工审查) → END
  ↓ (acquisition_ready)
acquisition (获取 Agent)
  ↓
parsing (解析 Agent) ────────→ finalize_failed (失败处理) → END
  ↓ (parsing_success)
translation (翻译)
  ↓
extraction (抽取 Agent)
  ↓
reasoning (推理 Agent)
  ↓
arbitration (仲裁 Agent) ────→ human_review (人工审查) → END
  ↓ (auto_approve)
finalize (完成)
  ↓
END
```

### 状态图

```python
from src.state.global_state import SupervisorState

class SupervisorState(TypedDict):
    """监督器状态"""
    
    # 输入
    source: str  # "upload", "pubmed", "web"
    input_text: str | None
    pmid: str | None
    url: str | None
    
    # 处理状态
    current_node: str
    workflow_status: str  # "pending", "processing", "completed", "failed"
    
    # 解析结果
    markdown_content: str | None
    translated_markdown: str | None
    image_paths: list[str]
    image_descriptions: list[str]
    
    # 抽取结果
    extracted_entities: list[Entity]
    evidence_records: list[Evidence]
    
    # 推理结果
    reasoning_results: list[Reasoning]
    
    # 仲裁结果
    acmg_result: ACMGRating | None
    arbitration_confidence: float | None
    
    # 人工审查
    requires_human_review: bool
    human_review_comments: str | None
    
    # 内部状态
    _inner_processing_state: ProcessingState
```

## Agent 说明

### 1. 获取 Agent (acquisition/)

负责从外部源获取文献：

| 文件 | 说明 |
|------|------|
| `node.py` | Agent 节点实现 |
| `api_tool.py` | API 调用工具 |
| `crawl_tool.py` | 网页爬取工具 |

**工具**:
```python
class AcquisitionTools:
    """获取工具集"""
    
    def search_pubmed(self, query: str) -> list[PubMedArticle]:
        """搜索 PubMed"""
        pass
    
    def fetch_pubmed_by_pmid(self, pmid: str) -> PubMedArticle:
        """按 PMID 获取"""
        pass
    
    def crawl_url(self, url: str) -> CrawlResult:
        """爬取网页"""
        pass
    
    def search_web(self, query: str) -> list[WebResult]:
        """搜索网页"""
        pass
```

### 2. 解析 Agent (parsing/)

负责 PDF 解析和翻译：

| 文件 | 说明 |
|------|------|
| `node.py` | Agent 节点实现 |
| `mineru_tool.py` | MinerU 解析工具 |
| `translation_tool.py` | 翻译工具 |

**工具**:
```python
class ParsingTools:
    """解析工具集"""
    
    def parse_pdf(self, file_path: str) -> ParsedDocument:
        """解析 PDF"""
        pass
    
    def translate_markdown(
        self, 
        markdown: str, 
        target_lang: str = "zh"
    ) -> str:
        """翻译 Markdown"""
        pass
    
    def extract_images(self, parsed: ParsedDocument) -> list[Image]:
        """提取图片"""
        pass
```

### 3. 抽取 Agent (extraction/)

负责实体抽取和验证：

| 文件 | 说明 |
|------|------|
| `node.py` | Agent 节点实现 |
| `extraction_tool.py` | 实体抽取工具 |
| `validator_tool.py` | 验证工具 |

**工具**:
```python
class ExtractionTools:
    """抽取工具集"""
    
    def extract_entities(
        self, 
        text: str,
        entity_types: list[str] = ["Gene", "Variant"]
    ) -> list[Entity]:
        """抽取实体"""
        pass
    
    def validate_entity(
        self, 
        entity: Entity
    ) -> ValidationResult:
        """验证实体"""
        pass
    
    def extract_evidence(
        self,
        text: str,
        gene: str,
        variant: str
    ) -> list[Evidence]:
        """抽取证据"""
        pass
```

### 4. 推理 Agent (reasoning/)

负责证据推理：

| 文件 | 说明 |
|------|------|
| `node.py` | Agent 节点实现 |

**推理逻辑**:
```python
class ReasoningNode:
    """推理节点"""
    
    def run(self, state: SupervisorState) -> SupervisorState:
        """
        执行推理
        
        流程:
        1. 获取抽取的证据
        2. 分析证据质量
        3. 评估证据强度
        4. 生成推理结果
        """
        pass
```

### 5. 仲裁 Agent (arbitration/)

负责 ACMG 评级仲裁：

| 文件 | 说明 |
|------|------|
| `node.py` | Agent 节点实现 |
| `ps3_bs3_evaluator.py` | PS3/BS3 评估器 |
| `rule_checker.py` | 规则检查器 |

**评估逻辑**:
```python
class ArbitrationNode:
    """仲裁节点"""
    
    def run(self, state: SupervisorState) -> SupervisorState:
        """
        执行仲裁
        
        流程:
        1. 获取推理结果
        2. 评估 PS3 证据等级
        3. 评估 BS3 证据等级
        4. 生成最终评级
        5. 计算置信度
        6. 判断是否需要人工审查
        """
        pass
```

### 6. 交互 Agent (interaction/)

负责用户交互和澄清：

| 文件 | 说明 |
|------|------|
| `node.py` | Agent 节点实现 |
| `prompts.py` | 交互 Prompt |

**交互逻辑**:
```python
class InteractionNode:
    """交互节点"""
    
    def run(self, state: SupervisorState) -> SupervisorState:
        """
        执行交互
        
        流程:
        1. 分析用户输入
        2. 提取关键信息 (基因、变异)
        3. 判断是否需要澄清
        4. 生成澄清问题或继续流程
        """
        pass
```

## 监督器

### supervisor.py

```python
from langgraph.graph import StateGraph, END, START

def build_supervisor_graph() -> StateGraph[SupervisorState]:
    """构建监督器图"""
    graph = StateGraph(SupervisorState)
    
    # 添加节点
    graph.add_node("route_by_source", route_by_source)
    graph.add_node("interaction", run_interaction_node)
    graph.add_node("acquisition", run_acquisition_node)
    graph.add_node("parsing", run_parsing_node)
    graph.add_node("translation", translation)
    graph.add_node("extraction", run_extraction_node)
    graph.add_node("reasoning", run_reasoning_node)
    graph.add_node("arbitration", run_arbitration_node)
    graph.add_node("finalize", finalize)
    graph.add_node("finalize_failed", finalize_failed)
    graph.add_node("human_review", human_review)
    
    # 添加边
    graph.add_edge(START, "route_by_source")
    graph.add_conditional_edges(
        "route_by_source",
        _route_by_source,
        {"upload": "interaction", "pubmed": "interaction", "web": "interaction"}
    )
    graph.add_conditional_edges(
        "interaction",
        _route_after_interaction,
        {"acquisition": "acquisition", "human_review": "human_review"}
    )
    graph.add_edge("acquisition", "parsing")
    graph.add_conditional_edges(
        "parsing",
        _route_after_parsing,
        {"translation": "translation", "finalize_failed": "finalize_failed"}
    )
    graph.add_edge("translation", "extraction")
    graph.add_edge("extraction", "reasoning")
    graph.add_edge("reasoning", "arbitration")
    graph.add_conditional_edges(
        "arbitration",
        _route_after_arbitration,
        {"finalize": "finalize", "human_review": "human_review"}
    )
    graph.add_edge("finalize", END)
    graph.add_edge("finalize_failed", END)
    graph.add_edge("human_review", END)
    
    return graph

def compile_supervisor(
    *,
    interrupt_before_human_review: bool = False,
    checkpointer: Any | None = None
):
    """编译监督器"""
    interrupt_before_nodes = ["human_review"] if interrupt_before_human_review else None
    return build_supervisor_graph().compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_before_nodes
    )
```

## 使用示例

### 运行工作流

```python
from src.agents.supervisor import compile_supervisor

# 编译监督器
supervisor = compile_supervisor()

# 初始状态
initial_state = {
    "source": "upload",
    "input_text": None,
    "pmid": None,
    "url": None,
    "current_node": None,
    "workflow_status": "pending",
    "_inner_processing_state": {}
}

# 运行工作流
result = supervisor.invoke(initial_state)

# 获取结果
acmg_result = result.get("acmg_result")
confidence = result.get("arbitration_confidence")
```

### 流式执行

```python
from src.agents.supervisor import compile_supervisor

supervisor = compile_supervisor()

initial_state = {...}

# 流式执行
for event in supervisor.stream(initial_state, stream_mode="updates"):
    node_name = list(event.keys())[0]
    node_output = event[node_name]
    print(f"Node {node_name} completed: {node_output}")
```

### 人工审查中断

```python
# 配置在人工审查前中断
supervisor = compile_supervisor(interrupt_before_human_review=True)

# 运行
thread_id = "task_123"
config = {"configurable": {"thread_id": thread_id}}

# 执行到人工审查节点前
result = supervisor.invoke(initial_state, config)

# 检查是否需要人工审查
if result.get("requires_human_review"):
    # 等待人工输入
    human_input = await get_human_input()
    
    # 继续执行
    result = supervisor.invoke(
        {"human_review_comments": human_input},
        config
    )
```

## 8 个 LLM Agent 配置

### Agent 与 LLM 映射

系统采用 8 个专用 LLM Agent 架构，每个 Agent 独立配置：

| # | Agent | 职责 | 默认模型 | 配置环境变量 |
|---|-------|------|----------|-------------|
| 1 | **retrieval** (文献获取) | PubMed/Firecrawl 文献检索 | qwen3.5-flash | `RETRIEVAL_API_KEY`, `RETRIEVAL_BASE_URL`, `RETRIEVAL_MODEL` |
| 2 | **parsing** (文档解析) | PDF 解析与结构提取 | qwen3.5-flash | `PARSING_API_KEY`, `PARSING_BASE_URL`, `PARSING_MODEL` |
| 3 | **mt** (多语种翻译) | 多语种文档翻译 | qwen-mt-flash | `MT_API_KEY`, `MT_BASE_URL`, `MT_MODEL` |
| 4 | **format** (多功能排版) | 文档排版与格式化 | qwen3.5-flash | `FORMAT_API_KEY`, `FORMAT_BASE_URL`, `FORMAT_MODEL` |
| 5 | **vlm** (图片提取) | 图片内容理解与描述 | qwen3-vl-flash | `VLM_API_KEY`, `VLM_BASE_URL`, `VLM_MODEL`, `VLM_ENABLE` |
| 6 | **evidence** (证据提取) | 证据记录抽取与验证 | qwen3.5-plus | `EVIDENCE_API_KEY`, `EVIDENCE_BASE_URL`, `EVIDENCE_MODEL` |
| 7 | **classification** (ACMG 分类) | 证据初步分类 | qwen3.5-plus | `CLASSIFICATION_API_KEY`, `CLASSIFICATION_BASE_URL`, `CLASSIFICATION_MODEL` |
| 8 | **arbitration** (专家裁决) | ACMG 最终评级仲裁 | qwen3-max | `ARBITRATION_API_KEY`, `ARBITRATION_BASE_URL`, `ARBITRATION_MODEL` |

### 主力/仲裁 LLM（可选增强）

除了 8 个专用 Agent 外，系统还支持配置主力和仲裁 LLM 用于特定场景：

| 角色 | 默认提供商 | 默认模型 | 配置环境变量 | 用途 |
|------|-----------|----------|-------------|------|
| **主力 LLM** | DeepSeek | deepseek-chat | `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL` | 通用任务、快速响应 |
| **仲裁 LLM** | Claude | claude-3-5-sonnet | `CLAUDE_API_KEY`, `ANTHROPIC_BASE_URL`, `CLAUDE_MODEL` | 复杂推理、最终决策 |

### LLM 配置示例

```python
from src.config import Settings

settings = Settings()

# 8 个 Agent 配置
agent_configs = {
    "retrieval": {
        "api_key": settings.retrieval_api_key,
        "base_url": settings.retrieval_base_url,
        "model": settings.retrieval_model,  # qwen3.5-flash
    },
    "parsing": {
        "api_key": settings.parsing_api_key,
        "base_url": settings.parsing_base_url,
        "model": settings.parsing_model,  # qwen3.5-flash
    },
    "mt": {
        "api_key": settings.mt_api_key,
        "base_url": settings.mt_base_url,
        "model": settings.mt_model,  # qwen-mt-flash (翻译专用)
    },
    "format": {
        "api_key": settings.format_api_key,
        "base_url": settings.format_base_url,
        "model": settings.format_model,  # qwen3.5-flash
    },
    "vlm": {
        "api_key": settings.vlm_api_key,
        "base_url": settings.vlm_base_url,
        "model": settings.vlm_model,  # qwen3-vl-flash
        "enabled": settings.vlm_enable,
    },
    "evidence": {
        "api_key": settings.evidence_api_key,
        "base_url": settings.evidence_base_url,
        "model": settings.evidence_model,  # qwen3.5-plus
    },
    "classification": {
        "api_key": settings.classification_api_key,
        "base_url": settings.classification_base_url,
        "model": settings.classification_model,  # qwen3.5-plus
    },
    "arbitration": {
        "api_key": settings.arbitration_api_key,
        "base_url": settings.arbitration_base_url,
        "model": settings.arbitration_model,  # qwen3-max
    },
}

# 主力/仲裁 LLM 配置（可选）
primary_llm_config = {
    "api_key": settings.deepseek_api_key,
    "base_url": settings.deepseek_base_url,
    "model": settings.deepseek_model,
}

arbiter_llm_config = {
    "api_key": settings.claude_api_key,
    "base_url": settings.anthropic_base_url,
    "model": settings.claude_model,
}
```

## 最佳实践

### 1. 状态管理

```python
# ✅ 推荐 - 使用 TypedDict 定义状态
class SupervisorState(TypedDict):
    source: str
    workflow_status: str
    # ...

# ❌ 不推荐 - 使用 dict
state = {}
```

### 2. 节点设计

```python
# ✅ 推荐 - 纯函数式节点
def run_extraction_node(state: SupervisorState) -> SupervisorState:
    updated = dict(state)
    updated["current_node"] = "extraction"
    # 处理逻辑
    updated["extracted_entities"] = entities
    return updated

# ❌ 不推荐 - 修改原状态
def run_extraction_node(state: SupervisorState):
    state["current_node"] = "extraction"  # 直接修改
```

### 3. 错误处理

```python
# ✅ 推荐 - 捕获并记录异常
def run_parsing_node(state: SupervisorState) -> SupervisorState:
    try:
        result = await parse_pdf(file_path)
        return {"parsing_result": result}
    except Exception as e:
        logger.exception("Parsing failed: {}", e)
        return {"workflow_status": "failed"}

# ❌ 不推荐 - 不处理异常
def run_parsing_node(state: SupervisorState):
    result = await parse_pdf(file_path)  # 可能抛出异常
    return {"parsing_result": result}
```

### 4. 条件路由

```python
# ✅ 推荐 - 明确的路由函数
def _route_after_arbitration(state: SupervisorState) -> str:
    if state.get("requires_human_review"):
        return "human_review"
    if not state.get("acmg_result"):
        return "human_review"
    if _is_low_confidence(state.get("arbitration_confidence")):
        return "human_review"
    return "finalize"

# ❌ 不推荐 - 硬编码路由
graph.add_edge("arbitration", "finalize")  # 无条件
```

## 测试

### 单元测试

```python
import pytest
from src.agents.extraction.node import run_extraction_node

@pytest.mark.asyncio
async def test_extraction_node():
    state = {
        "translated_markdown": "测试文本",
        "current_node": None
    }
    
    result = await run_extraction_node(state)
    
    assert result["current_node"] == "extraction"
    assert result["extracted_entities"] is not None
```

### 集成测试

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_workflow():
    supervisor = compile_supervisor()
    
    initial_state = {
        "source": "upload",
        "markdown_content": test_markdown,
        "workflow_status": "pending"
    }
    
    result = await supervisor.ainvoke(initial_state)
    
    assert result["workflow_status"] == "completed"
    assert result["acmg_result"] is not None
```

## 相关文档

- [后端 README](../../README.md)
- [领域层 README](../domain/README.md)
- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)

---

**最后更新**: 2026-03-22 (v3.0)
