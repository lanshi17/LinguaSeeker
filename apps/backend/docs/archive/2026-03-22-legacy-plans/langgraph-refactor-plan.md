# ACMGFlow LangGraph 重构实施方案

> **Plan Status:** `LEGACY (pre-v1.0 baseline)`
> **Conflict Rule:** This plan is historical reference only. Frozen docs (`PRD/APP_FLOW/TECH_STACK/BACKEND_STRUCTURE`) are authoritative.

## 文档信息

- **创建日期**: 2026-03-06
- **版本**: v1.0
- **状态**: Ready for Implementation
- **预计工期**: 1-2周（核心重构）

---

## 一、执行摘要

### 1.1 重构目标

将现有 ACMGFlow 后端从"Celery 驱动的线性 Pipeline"重构为"LangGraph 编排的智能体协作系统"，实现：

1. **智能路由**：基于证据质量/置信度自动决策（人工复核 vs 自动通过）
2. **状态显性化**：全局状态可追溯、可审计、可中断恢复
3. **工具层统一**：消除分散的数据库/外部服务调用逻辑
4. **领域知识外化**：Prompt 模板 YAML 化，支持热更新

### 1.2 关键约束

- **最小改动原则**：保留现有 4 层架构骨架，重构仅聚焦 `domain/` 层
- **共存策略**：Celery 仍负责任务调度，LangGraph 负责智能体编排（两者职责分离）
- **零停机**：通过 Feature Flag（`config.USE_AGENT_WORKFLOW`）控制新旧流程切换
- **向后兼容**：旧 API 契约不变，仅内部实现替换

---

## 二、现状分析

### 2.1 当前架构

```
Presentation (FastAPI)
    ↓
Service (Celery Tasks - 串行编排)
    ↓ (5个节点顺序执行)
    ├─ run_node_acquisition    # 文件验证
    ├─ run_node_parsing        # MinerU PDF解析
    ├─ run_node_translation    # 机器翻译
    ├─ run_node_extraction     # 证据提取（调用 EvidenceAgent）
    └─ run_node_acmg           # 图谱同步
    ↓
Domain (EvidenceAgent 内部用 StateGraph)
    ↓
Infrastructure (Database Clients)
```

### 2.2 痛点识别

| 问题 | 现状 | 影响 |
|------|------|------|
| **编排逻辑分散** | Celery tasks.py 1455行混杂业务+编排 | 难以扩展条件路由（如人工介入） |
| **状态隐式传递** | 节点间通过函数返回值+DB查询传递状态 | 无法统一查看中间状态 |
| **工具调用耦合** | DB 操作分散在 agent/service/database 三层 | 重复代码，测试困难 |
| **Prompt 硬编码** | prompts.py 2000+行 Python 字符串 | 修改需重启服务 |
| **LangGraph 局部化** | 仅 EvidenceAgent.workflow.py 单文件使用 | 未发挥编排潜力 |

### 2.3 保留的优势

- ✅ 4 个存储后端（PostgreSQL/Neo4j/Qdrant/MinIO）已稳定运行
- ✅ 现有 Pydantic 模型（`EvidenceOutput`, `ExtractedEvidenceFields` 等）结构完整
- ✅ ACMG 评级逻辑（`EvidenceClassifier`）已验证正确
- ✅ FastAPI 路由层（`task_api.py`）契约清晰

---

## 三、目标架构

### 3.1 新目录结构

```
src/
├── main.py                          # FastAPI 入口（保留）
├── config.py                        # 增强：新增 USE_AGENT_WORKFLOW flag
├── state/                           # 【新增】LangGraph 状态核心
│   ├── __init__.py
│   ├── global_state.py              # GlobalState TypedDict 定义
│   └── schemas.py                   # Pydantic 模型（迁移自 domain/models.py）
├── agents/                          # 【重构】智能体编排层
│   ├── __init__.py
│   ├── supervisor.py                # 【新增】顶层 Supervisor 图（条件路由）
│   ├── interaction/                 # P0 交互澄清
│   │   ├── __init__.py
│   │   ├── node.py
│   │   └── prompts.py
│   ├── acquisition/                 # P1 文献获取
│   │   ├── __init__.py
│   │   ├── node.py
│   │   └── tools.py                 # pubmed_tool, firecrawl_tool
│   ├── parsing/                     # P2-P3 解析+翻译
│   │   ├── __init__.py
│   │   ├── node.py
│   │   ├── mineru_tool.py
│   │   └── translation_tool.py
│   ├── extraction/                  # P4 证据提取
│   │   ├── __init__.py
│   │   ├── node.py
│   │   ├── extraction_tool.py       # 调用 EVIDENCE_MODEL
│   │   └── validator_tool.py        # HGVS/HPO 标准化
│   └── arbitration/                 # P5 ACMG 仲裁
│       ├── __init__.py
│       ├── node.py
│       ├── ps3_bs3_evaluator.py     # 【关键】硬逻辑计算器（非LLM）
│       └── rule_checker.py          # 四步法规则引擎
├── tools/                           # 【新增】统一工具层
│   ├── __init__.py
│   ├── db/                          # 数据库工具
│   │   ├── __init__.py
│   │   ├── postgres_tool.py
│   │   ├── neo4j_tool.py
│   │   └── qdrant_tool.py
│   ├── file/                        # 文件工具
│   │   ├── __init__.py
│   │   ├── minio_tool.py
│   │   └── pdf_parser.py
│   └── external/                    # 外部服务
│       ├── __init__.py
│       ├── clinvar_tool.py
│       └── translation_api.py
├── infrastructure/                  # 【重命名】database/ → infrastructure/
│   ├── __init__.py                  # 保持向后兼容导入
│   ├── postgres.py                  # 简化为连接池管理
│   ├── neo4j.py
│   ├── qdrant.py
│   ├── minio.py
│   └── redis.py
├── knowledge/                       # 【新增】领域知识外化
│   ├── prompts/                     # Prompt 模板（YAML）
│   │   ├── system.yaml
│   │   ├── extraction.yaml
│   │   └── acmg_rules.yaml
│   └── ontologies/                  # 本体映射表
│       └── hpo_mapping.json
├── services/                        # 【精简】仅保留事务性逻辑
│   ├── __init__.py
│   ├── task_manager.py              # Celery 任务入口
│   └── report_generator.py          # 报告生成
├── api/                             # 【重命名】presentation/ → api/
│   ├── __init__.py
│   ├── routes/
│   │   ├── task.py                  # POST /tasks 启动工作流
│   │   └── stream.py                # WebSocket 流式输出
│   └── dependencies.py
├── domain/                          # 【保留】过渡期并存
│   └── ...（旧代码暂时保留）
└── utils/
    ├── logger.py
    ├── exceptions.py
    └── sanitizers.py
```

### 3.2 核心组件设计

#### 3.2.1 GlobalState（`state/global_state.py`）

```python
from typing import TypedDict, Annotated, List, Dict, Any, Optional
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage

class GlobalState(TypedDict):
    """全局工作流状态 - 所有 Agent 节点共享"""
    
    # 会话信息
    task_id: str
    request_id: str
    messages: Annotated[List[BaseMessage], add_messages]  # LangGraph 消息链
    
    # 文档数据
    file_paths: List[str]
    document_id: Optional[str]
    markdown_content: Optional[str]
    translated_md: Optional[str]
    image_paths: List[str]
    image_descriptions: List[str]
    
    # 证据提取
    evidences: List[Dict[str, Any]]  # ExtractedEvidenceFields 列表
    evidence_sources: List[Dict[str, Any]]  # 溯源信息（document_id, chunk_id, page_num）
    
    # ACMG 评级
    acmg_result: Optional[Dict[str, Any]]
    confidence: float  # 整体置信度 0-100
    evidence_strength: Optional[str]  # PS3_very_strong / PS3 / BS3 等
    
    # 控制流
    needs_human_review: bool
    current_step: str  # acquisition/parsing/extraction/arbitration/finished
    iteration_count: int
    max_iterations: int
    status: str  # pending/running/completed/failed/manual_review
```

**设计要点**：
- 继承 LangGraph 的 `add_messages` reducer，保留对话历史
- 与现有 `EvidenceOutput` Pydantic 模型对齐，确保数据结构兼容
- `evidence_sources` 新增字段，强化溯源能力

#### 3.2.2 Supervisor Agent（`agents/supervisor.py`）

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

def create_supervisor_graph() -> StateGraph:
    """
    顶层 Supervisor 图 - 负责：
    1. 条件路由（基于置信度/状态）
    2. 人工介入点控制
    3. 异常恢复
    """
    
    workflow = StateGraph(GlobalState)
    
    # 添加节点
    workflow.add_node("interaction", interaction_node)      # P0 交互澄清
    workflow.add_node("acquisition", acquisition_node)      # P1 文献获取
    workflow.add_node("parsing", parsing_node)              # P2-P3 解析+翻译
    workflow.add_node("extraction", extraction_node)        # P4 证据提取
    workflow.add_node("arbitration", arbitration_node)      # P5 ACMG 仲裁
    workflow.add_node("human_review", human_review_node)    # 人工复核
    
    # 入口：检查是否需要澄清
    workflow.set_conditional_entry_point(
        route_entry,
        {
            "interaction": "interaction",
            "acquisition": "acquisition"
        }
    )
    
    # 条件边：仲裁后决策
    workflow.add_conditional_edges(
        "arbitration",
        route_after_arbitration,
        {
            "human_review": "human_review",  # confidence < 0.85
            "finished": END                   # confidence >= 0.85
        }
    )
    
    # 人工介入点（interrupt_before）
    workflow.add_edge("human_review", END)
    
    # 编译图
    memory = MemorySaver()  # 支持状态持久化
    return workflow.compile(
        checkpointer=memory,
        interrupt_before=["human_review"]  # 暂停等待人工输入
    )

def route_after_arbitration(state: GlobalState) -> str:
    """仲裁后路由逻辑"""
    if state["confidence"] < 85.0:
        return "human_review"
    if state["acmg_result"] is None:
        return "human_review"
    return "finished"
```

**设计要点**：
- 使用 `interrupt_before` 实现人工介入暂停点
- 路由函数基于 **硬规则**（置信度阈值），非 LLM 决策
- 支持 Checkpointer，可中断恢复

#### 3.2.3 PS3/BS3 硬逻辑评估器（`agents/arbitration/ps3_bs3_evaluator.py`）

```python
from typing import Dict, Any

class PS3BS3Evaluator:
    """
    ACMG PS3/BS3 证据等级计算器
    严格按阈值表计算，禁止 LLM 参与数值判断
    """
    
    # ACMG 2024 Odds Path 阈值表
    THRESHOLDS = {
        "PS3_very_strong": 350.0,
        "PS3_strong": 18.7,
        "PS3": 4.3,
        "PS3_moderate": 2.08,
        "PS3_supporting": 1.0,
        "BS3_supporting": 0.48,
        "BS3_moderate": 0.23,
        "BS3": 0.053,
        "BS3_strong": 0.0029,
        "BS3_very_strong": 0.0,
    }
    
    @staticmethod
    def calculate_evidence_level(experiment_data: Dict[str, Any]) -> str:
        """
        输入：experiment_data = {
            "odds_ratio": 25.3,
            "confidence_interval": [12.1, 48.7],
            "p_value": 0.0001,
            "sample_size": 150
        }
        输出："PS3_strong"
        """
        odds = experiment_data.get("odds_ratio")
        if odds is None:
            raise ValueError("Missing odds_ratio in experiment_data")
        
        # 严格阈值匹配（降序检查）
        if odds > PS3BS3Evaluator.THRESHOLDS["PS3_very_strong"]:
            return "PS3_very_strong"
        elif odds > PS3BS3Evaluator.THRESHOLDS["PS3_strong"]:
            return "PS3_strong"
        elif odds > PS3BS3Evaluator.THRESHOLDS["PS3"]:
            return "PS3"
        elif odds > PS3BS3Evaluator.THRESHOLDS["PS3_moderate"]:
            return "PS3_moderate"
        elif odds > PS3BS3Evaluator.THRESHOLDS["PS3_supporting"]:
            return "PS3_supporting"
        elif odds > PS3BS3Evaluator.THRESHOLDS["BS3_supporting"]:
            return "BS3_supporting"
        elif odds > PS3BS3Evaluator.THRESHOLDS["BS3_moderate"]:
            return "BS3_moderate"
        elif odds > PS3BS3Evaluator.THRESHOLDS["BS3"]:
            return "BS3"
        elif odds > PS3BS3Evaluator.THRESHOLDS["BS3_strong"]:
            return "BS3_strong"
        else:
            return "BS3_very_strong"
    
    @staticmethod
    def validate_experiment_quality(experiment_data: Dict[str, Any]) -> tuple[bool, str]:
        """
        质量检查：样本量、置信区间、对照组
        返回：(is_valid, reason)
        """
        sample_size = experiment_data.get("sample_size", 0)
        has_control = experiment_data.get("has_control", False)
        ci = experiment_data.get("confidence_interval")
        
        if sample_size < 30:
            return False, "Sample size < 30 (underpowered)"
        if not has_control:
            return False, "Missing control group"
        if ci and (ci[1] / ci[0]) > 10:  # CI span > 10x
            return False, "Confidence interval too wide"
        
        return True, "Passed quality check"
```

**设计要点**：
- **零 LLM 依赖**：纯 Python 逻辑，确保 ACMG 评级可复现
- 分离计算（`calculate_evidence_level`）和质量检查（`validate_experiment_quality`）
- 阈值表外部化为常量，方便未来更新 ACMG 标准

#### 3.2.4 统一工具层示例（`tools/db/postgres_tool.py`）

```python
from langchain_core.tools import tool
from src.infrastructure.postgres import get_postgres_client
from src.state.schemas import PaperTask

@tool
def get_paper_task_by_id(task_id: str) -> dict:
    """
    Retrieve paper task metadata from PostgreSQL.
    
    Args:
        task_id: Unique task identifier
    
    Returns:
        Task metadata including status, file paths, timestamps
    """
    client = get_postgres_client()
    task = client.query(PaperTask).filter_by(id=task_id).first()
    if not task:
        raise ValueError(f"Task {task_id} not found")
    return task.to_dict()

@tool
def update_task_status(task_id: str, status: str, metadata: dict = None):
    """
    Update task processing status in database.
    
    Args:
        task_id: Task ID
        status: New status (pending/running/completed/failed)
        metadata: Optional additional metadata
    """
    client = get_postgres_client()
    task = client.query(PaperTask).filter_by(id=task_id).first()
    if not task:
        raise ValueError(f"Task {task_id} not found")
    
    task.status = status
    if metadata:
        task.metadata.update(metadata)
    client.commit()
```

**设计要点**：
- 使用 LangChain `@tool` 装饰器，自动生成工具描述
- 业务逻辑封装在工具内，Agent 仅需调用工具名
- 测试友好：可 mock `get_postgres_client()`

#### 3.2.5 Prompt 外化示例（`knowledge/prompts/extraction.yaml`）

```yaml
system_prompt: |
  You are a medical evidence extraction specialist for ACMG variant classification.
  
  Your task: Extract structured fields from scientific literature to support PS3/BS3 evidence.
  
  Required fields:
  - Gene information (symbol, NCBI ID, Ensembl ID)
  - Variant details (HGVS nomenclature, genomic position)
  - Experimental data (assay type, odds ratio, sample size, controls)
  - Disease association (OMIM, HPO terms, inheritance pattern)
  
  Strict rules:
  1. ONLY extract information explicitly stated in the text
  2. Use standard nomenclature (HGVS for variants, HPO for phenotypes)
  3. Always provide evidence quotes verbatim from source
  4. Assign confidence scores (0-100) per field

extraction_prompt_template: |
  Source document (translated to English):
  ```
  {translated_text}
  ```
  
  Images (if any):
  {image_descriptions}
  
  Context from knowledge base:
  {rag_context}
  
  Extract the following fields. For each field, provide:
  1. The extracted value
  2. Verbatim quote from source as evidence
  3. Confidence score (0-100)
  
  Use the provided tools to structure your response.

validation_rules:
  hgvs_patterns:
    - "NM_\\d+\\.\\d+:c\\.\\d+[ACGT]>[ACGT]"
    - "NP_\\d+\\.\\d+:p\\.\\w+\\d+\\w+"
  required_fields:
    - gene_symbol
    - variant_hgvs
    - experiment_type
  confidence_thresholds:
    high: 85.0
    medium: 60.0
    low: 0.0
```

**加载逻辑**（`knowledge/prompts/__init__.py`）：

```python
import yaml
from pathlib import Path
from functools import lru_cache

@lru_cache(maxsize=10)
def load_prompt(name: str) -> dict:
    """
    加载 Prompt 模板（带缓存）
    支持热更新：修改 YAML 后重启服务生效
    """
    prompt_path = Path(__file__).parent / f"{name}.yaml"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt {name}.yaml not found")
    
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def get_extraction_prompt(translated_text: str, image_descriptions: str, rag_context: str) -> str:
    """动态填充 Prompt 模板"""
    template = load_prompt("extraction")
    return template["extraction_prompt_template"].format(
        translated_text=translated_text,
        image_descriptions=image_descriptions,
        rag_context=rag_context
    )
```

---

## 四、实施路线图

### 4.1 第一周：基建搭建（5天）

#### Day 1-2: 状态层 + 工具层

**目标**：建立新目录结构，迁移核心数据模型

**任务清单**：

1. **创建目录结构**
   ```bash
   mkdir -p src/{state,agents,tools/{db,file,external},knowledge/prompts}
   ```

2. **编写 `state/global_state.py`**
   - 定义 `GlobalState` TypedDict
   - 确保字段与现有 `EvidenceOutput` 对齐
   - 添加单元测试验证序列化/反序列化

3. **迁移 Pydantic 模型**
   ```bash
   # 复制现有模型到新位置（保留旧位置兼容）
   cp src/domain/models.py src/state/schemas.py
   ```
   - 在 `src/domain/models.py` 添加 deprecation 注释
   - 在 `src/state/__init__.py` 中重新导出所有模型

4. **提取数据库工具**
   - 实现 `tools/db/postgres_tool.py`（参考 3.2.4 节示例）
   - 实现 `tools/db/neo4j_tool.py`
   - 实现 `tools/db/qdrant_tool.py`
   - 每个工具添加 `@tool` 装饰器
   - 编写工具单元测试（mock DB 客户端）

5. **重命名 database/ → infrastructure/**
   ```bash
   mv src/database src/infrastructure
   ```
   - 在 `src/infrastructure/__init__.py` 中保持旧导入路径兼容：
     ```python
     # 向后兼容
     import sys
     sys.modules['src.database'] = sys.modules['src.infrastructure']
     ```

**验收标准**：
- ✅ `GlobalState` 通过类型检查（`mypy src/state/`）
- ✅ 工具函数可独立导入并执行（`pytest tests/tools/`）
- ✅ 旧代码导入 `src.database.*` 不报错

#### Day 3-4: Prompt 外化 + 知识层

**目标**：将 `prompts.py` 硬编码迁移为 YAML 配置

**任务清单**：

1. **提取现有 Prompt**
   - 分析 `src/domain/agent/prompts.py`（2000+ 行）
   - 识别静态模板 vs 动态生成逻辑
   - 将静态模板写入 `knowledge/prompts/*.yaml`：
     - `system.yaml` - 系统角色定义
     - `extraction.yaml` - 证据提取模板
     - `acmg_rules.yaml` - PS3/BS3 评估规则

2. **编写 Prompt 加载器**
   - 实现 `knowledge/prompts/__init__.py`（参考 3.2.5 节）
   - 支持模板变量填充（`{translated_text}`, `{rag_context}` 等）
   - 添加 YAML schema 验证（使用 `pydantic`）

3. **迁移动态 Prompt 生成逻辑**
   - 保留 `prompts.py` 中的 Python 函数（如拼接逻辑）
   - 函数内部调用 `load_prompt()` 获取模板
   - 示例：
     ```python
     # 旧代码
     def get_extraction_prompt(text, context):
         return f"Extract from: {text}\nContext: {context}"
     
     # 新代码
     from knowledge.prompts import load_prompt
     def get_extraction_prompt(text, context):
         template = load_prompt("extraction")
         return template["extraction_prompt_template"].format(
             translated_text=text, rag_context=context
         )
     ```

4. **添加本体映射表**
   - 创建 `knowledge/ontologies/hpo_mapping.json`
   - 包含常见表型术语 → HPO ID 映射
   - 供 `validator_tool.py` 使用

**验收标准**：
- ✅ 所有 YAML 通过 schema 验证
- ✅ 修改 YAML 后重启服务，Prompt 生效
- ✅ 原 `prompts.py` 中的函数行为不变（单元测试覆盖）

#### Day 5: PS3/BS3 硬逻辑实现

**目标**：实现 ACMG 评级计算器（非 LLM）

**任务清单**：

1. **实现 `ps3_bs3_evaluator.py`**
   - 按 3.2.3 节设计实现 `PS3BS3Evaluator` 类
   - 阈值表写入 `knowledge/prompts/acmg_rules.yaml`
   - 添加质量检查逻辑（样本量、对照组、置信区间）

2. **编写测试用例**
   ```python
   def test_ps3_strong_threshold():
       data = {"odds_ratio": 25.0, "sample_size": 100, "has_control": True}
       assert PS3BS3Evaluator.calculate_evidence_level(data) == "PS3_strong"
   
   def test_invalid_sample_size():
       data = {"odds_ratio": 25.0, "sample_size": 20, "has_control": True}
       is_valid, reason = PS3BS3Evaluator.validate_experiment_quality(data)
       assert not is_valid
       assert "Sample size" in reason
   ```

3. **集成到现有 `EvidenceClassifier`**
   - 修改 `src/domain/evidence/classifier.py`
   - 替换原有阈值判断逻辑为调用 `PS3BS3Evaluator`
   - 保持 API 接口不变

**验收标准**：
- ✅ 覆盖所有 10 个阈值区间的测试用例
- ✅ 质量检查规则覆盖边界条件
- ✅ 与现有分类器输出一致性测试通过

### 4.2 第二周：智能体重构（5天）

#### Day 6-7: Extraction Agent 重构

**目标**：将现有 `EvidenceAgent.workflow.py` 拆分为模块化节点

**任务清单**：

1. **创建 `agents/extraction/` 目录结构**
   ```
   agents/extraction/
   ├── __init__.py
   ├── node.py              # extraction_node 主函数
   ├── extraction_tool.py   # 证据提取工具
   └── validator_tool.py    # HGVS/HPO 校验工具
   ```

2. **迁移 `extract_ps3_evidence` 逻辑**
   - 将 `workflow.py` 第 500-700 行的提取逻辑移至 `node.py`
   - 函数签名修改为：
     ```python
     async def extraction_node(state: GlobalState) -> GlobalState:
         # 1. 调用 RAGComponent 获取上下文
         # 2. 构建 Prompt（从 knowledge/prompts/ 加载）
         # 3. 调用 evidence_llm.bind_tools(get_evidence_tools())
         # 4. 解析工具调用结果
         # 5. 更新 state["evidences"], state["evidence_sources"]
         return state
     ```

3. **实现校验工具**
   ```python
   @tool
   def validate_hgvs(hgvs_string: str) -> dict:
       """验证 HGVS 命名合法性"""
       import hgvs  # 使用 hgvs 库
       # ... 验证逻辑
       return {"is_valid": True, "normalized": "NM_000xxx.x:c.123A>G"}
   
   @tool
   def validate_hpo(phenotype_text: str) -> list:
       """将表型文本映射到 HPO ID"""
       from knowledge.ontologies import load_hpo_mapping
       # ... 映射逻辑
       return [{"hpo_id": "HP:0001250", "term": "Seizure", "confidence": 0.95}]
   ```

4. **编写单元测试**
   - Mock RAGComponent 返回值
   - Mock LLM 工具调用响应
   - 验证 `state["evidences"]` 结构正确

**验收标准**：
- ✅ 新节点与旧 `extract_ps3_evidence` 输出一致（集成测试）
- ✅ 校验工具通过 10+ 真实 HGVS/HPO 样例测试
- ✅ 提取节点执行时间 < 15秒（与旧版持平）

#### Day 8: Arbitration Agent 重构

**目标**：集成 PS3/BS3 硬逻辑到仲裁节点

**任务清单**：

1. **创建 `agents/arbitration/node.py`**
   ```python
   async def arbitration_node(state: GlobalState) -> GlobalState:
       # 1. 提取 experiment_data from state["evidences"]
       # 2. 调用 PS3BS3Evaluator.calculate_evidence_level()
       # 3. 调用 PS3BS3Evaluator.validate_experiment_quality()
       # 4. 如果质量检查失败 → state["needs_human_review"] = True
       # 5. 调用 arbitration_llm 生成解释性文本（非数值判断）
       # 6. 更新 state["acmg_result"], state["confidence"]
       return state
   ```

2. **分离 LLM 职责**
   - **硬逻辑**（必须）：证据等级计算、质量检查 → Python 代码
   - **LLM**（辅助）：生成解释文本、识别潜在问题 → `arbitration_llm`
   - 示例 LLM Prompt：
     ```yaml
     arbitration_prompt: |
       Evidence level calculated: {evidence_level}
       Experiment data: {experiment_summary}
       
       Your task: Generate a concise explanation (2-3 sentences) for clinicians:
       - Why this evidence level was assigned
       - Any limitations or concerns (sample size, control quality)
       - Recommendations for follow-up validation
     ```

3. **迁移 `route_decision` 逻辑**
   - 将 `workflow.py` 第 901-920 行的路由规则移至 `supervisor.py`
   - 更新路由条件：
     ```python
     def route_after_arbitration(state: GlobalState) -> str:
         if state["needs_human_review"]:
             return "human_review"
         if state["confidence"] < 85.0:
             return "human_review"
         if not state["acmg_result"]:
             return "human_review"
         return "finished"
     ```

**验收标准**：
- ✅ 仲裁结果与旧版 `arbitrate_score` 一致
- ✅ 质量检查触发人工复核的用例覆盖 3+ 场景
- ✅ LLM 生成的解释文本包含关键信息（证据等级、样本量）

#### Day 9: Supervisor Graph 集成

**目标**：构建顶层编排图，连接所有节点

**任务清单**：

1. **实现 `agents/supervisor.py`**
   - 按 3.2.2 节设计实现 `create_supervisor_graph()`
   - 添加所有节点：interaction → acquisition → parsing → extraction → arbitration
   - 配置条件边和人工介入点

2. **实现剩余节点占位符**
   ```python
   # agents/interaction/node.py
   def interaction_node(state: GlobalState) -> GlobalState:
       # TODO: 集成现有 InteractionAgent
       return state
   
   # agents/acquisition/node.py
   def acquisition_node(state: GlobalState) -> GlobalState:
       # TODO: 调用 PubMed/Firecrawl 工具
       return state
   
   # agents/parsing/node.py
   def parsing_node(state: GlobalState) -> GlobalState:
       # TODO: 调用 MinerU + 翻译
       return state
   ```

3. **Celery 集成**
   - 修改 `service/task_manager.py`：
     ```python
     from agents.supervisor import create_supervisor_graph
     
     @celery_app.task
     def process_pdf_with_agents(task_id: str, file_paths: list):
         """新版：使用 LangGraph 编排"""
         graph = create_supervisor_graph()
         initial_state = {
             "task_id": task_id,
             "file_paths": file_paths,
             "messages": [],
             # ... 初始化其他字段
         }
         
         # 同步调用（Celery 任务内）
         final_state = graph.invoke(initial_state)
         
         # 存储结果到 MinIO/PostgreSQL
         _store_results(final_state)
         return final_state
     ```

4. **Feature Flag 控制**
   - 在 `config.py` 添加：
     ```python
     class Settings(BaseSettings):
         # ... 现有配置
         USE_AGENT_WORKFLOW: bool = False  # 默认关闭
     ```
   - 在 `task_manager.py` 添加分支：
     ```python
     if cfg.USE_AGENT_WORKFLOW:
         return process_pdf_with_agents.apply_async(...)
     else:
         return process_pdf_task.apply_async(...)  # 旧流程
     ```

**验收标准**：
- ✅ Supervisor 图可编译（`graph.get_graph().print_ascii()`）
- ✅ 通过 Feature Flag 切换新旧流程，API 输出一致
- ✅ 人工介入点暂停，恢复后继续执行

#### Day 10: 全链路测试

**目标**：端到端验证新流程

**任务清单**：

1. **准备测试数据**
   - 选择 3 篇真实文献 PDF（覆盖 PS3/BS3/边界情况）
   - 准备预期输出（旧流程运行结果作为 baseline）

2. **执行对比测试**
   ```python
   # tests/integration/test_workflow_parity.py
   def test_old_vs_new_workflow():
       # 1. 运行旧流程（USE_AGENT_WORKFLOW=False）
       old_result = trigger_task(pdf_path, use_new=False)
       
       # 2. 运行新流程（USE_AGENT_WORKFLOW=True）
       new_result = trigger_task(pdf_path, use_new=True)
       
       # 3. 对比关键字段
       assert old_result["acmg_result"] == new_result["acmg_result"]
       assert old_result["evidence_strength"] == new_result["evidence_strength"]
       assert abs(old_result["confidence"] - new_result["confidence"]) < 5.0
   ```

3. **性能基准测试**
   - 测量新流程执行时间（目标：不超过旧流程 +20%）
   - 测量内存占用（StateGraph 会增加状态存储）

4. **错误处理测试**
   - 测试文件不存在、解析失败、LLM 超时等异常场景
   - 验证状态回滚和错误日志

**验收标准**：
- ✅ 3 篇测试文献的 ACMG 评级结果与旧流程一致
- ✅ 新流程执行时间 < 旧流程 * 1.2
- ✅ 异常场景不产生脏数据（数据库事务正确回滚）

---

## 五、风险控制

### 5.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| **状态结构不兼容** | 高 | 中 | 第一周完成 GlobalState 单元测试，提前验证与现有模型对齐 |
| **LangGraph 性能劣化** | 中 | 中 | Day 10 性能基准测试，必要时优化 Checkpointer（改用 SQLite） |
| **Prompt 外化遗漏动态逻辑** | 中 | 高 | 保留 `prompts.py` 作为兜底，新旧并存 1 个月后再删除 |
| **工具层迁移破坏现有调用** | 高 | 低 | 通过 `infrastructure/__init__.py` 保持旧导入路径兼容 |

### 5.2 业务风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| **ACMG 评级结果变化** | 极高 | 低 | Day 5 完成 PS3/BS3 单元测试，覆盖 50+ 边界用例 |
| **人工复核流程中断** | 高 | 中 | 优先实现 `interrupt_before`，Day 9 测试恢复机制 |
| **旧流程依赖方受影响** | 中 | 低 | 通过 Feature Flag 控制，默认关闭新流程 |

### 5.3 回滚策略

**触发条件**（任一满足即回滚）：
1. Day 10 对比测试失败率 > 20%
2. 生产环境新流程错误率 > 5%
3. 性能劣化 > 30%

**回滚步骤**：
1. 设置 `config.USE_AGENT_WORKFLOW=False`（重启服务）
2. 回滚数据库迁移（如有）：`alembic downgrade -1`
3. 恢复旧版本代码：`git revert <commit-range>`
4. 通知用户切换回旧 API 端点（如适用）

---

## 六、验收标准

### 6.1 功能完整性

- [ ] 所有 5 个 Pipeline 节点在 LangGraph 中正常运行
- [ ] Supervisor 条件路由正确（置信度/质量检查触发人工复核）
- [ ] 人工介入点可暂停并恢复
- [ ] ACMG 评级结果与旧流程一致（50+ 测试用例）

### 6.2 代码质量

- [ ] 单元测试覆盖率 > 80%（`pytest --cov`）
- [ ] 类型检查通过（`mypy src/`）
- [ ] Linter 无错误（`ruff check src/`）
- [ ] 文档字符串覆盖所有公开函数

### 6.3 性能指标

- [ ] 端到端处理时间 < 旧流程 * 1.2
- [ ] 内存占用 < 2GB（单任务）
- [ ] 数据库查询次数不增加（通过日志验证）

### 6.4 运维就绪

- [ ] Feature Flag 可通过环境变量控制
- [ ] 旧流程保留并可快速切换
- [ ] 错误日志包含 `task_id` 和节点名称
- [ ] 监控大盘新增 LangGraph 节点耗时指标

---

## 七、后续优化（P1 阶段后）

### 7.1 流式输出

**目标**：实时推送中间结果到前端

**实现**：
```python
# api/routes/stream.py
@router.websocket("/ws/tasks/{task_id}")
async def stream_task_progress(websocket: WebSocket, task_id: str):
    await websocket.accept()
    graph = create_supervisor_graph()
    
    async for chunk in graph.astream(initial_state):
        await websocket.send_json({
            "node": chunk["current_step"],
            "status": chunk["status"],
            "confidence": chunk.get("confidence", 0)
        })
```

### 7.2 多模态支持

**目标**：支持直接输入图像（实验图表）

**实现**：
- 在 `GlobalState` 增加 `image_inputs: List[str]` 字段
- 修改 VLM 节点，支持批量图像描述
- 提取实验数据时优先使用图像（Table/Chart OCR）

### 7.3 知识图谱增强

**目标**：利用 Neo4j 图谱进行证据链推理

**实现**：
- 新增 `reasoning` 节点（在 arbitration 前）
- 查询 Neo4j：`MATCH (v:Variant)-[:RELATED_TO]->(d:Disease) WHERE ...`
- 将图谱结果作为额外上下文输入 arbitration

---

## 八、附录

### 8.1 关键依赖版本

```toml
[tool.poetry.dependencies]
python = "^3.10"
fastapi = "^0.110.0"
langgraph = "^0.2.0"         # 核心编排框架
langchain = "^0.2.0"
langchain-openai = "^0.1.0"
celery = "^5.3.0"
redis = "^5.0.0"
psycopg2-binary = "^2.9.9"
neo4j = "^5.18.0"
qdrant-client = "^1.9.0"
pydantic = "^2.6.0"
pyyaml = "^6.0.1"            # Prompt 外化
hgvs = "^1.5.4"              # HGVS 校验
```

### 8.2 术语表

| 术语 | 定义 |
|------|------|
| **GlobalState** | LangGraph 工作流的全局状态 TypedDict，所有节点共享 |
| **Supervisor Graph** | 顶层编排图，负责节点路由和人工介入控制 |
| **PS3/BS3** | ACMG 证据类型，PS3=功能研究支持致病性，BS3=功能研究支持良性 |
| **Odds Path** | ACMG 2024 更新的定量评级方法，基于 Odds Ratio 阈值 |
| **Feature Flag** | 功能开关，通过配置控制新旧流程切换 |
| **Interrupt Point** | LangGraph 中的暂停点，用于人工介入 |

### 8.3 参考资料

- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- [ACMG 2015 指南](https://www.acmg.net/docs/standards_guidelines_for_the_interpretation_of_sequence_variants.pdf)
- [ACMG 2024 更新（PS3/BS3）](https://www.acmg.net/PDFLibrary/Calibrating-ACMG-PS3-BS3-PS4-Functional-Evidence.pdf)
- 内部文档：`docs/architecture/current-pipeline.md`（假设存在）

---

**文档结束** | 如有疑问，联系架构团队 `arch@acmgflow.org`
