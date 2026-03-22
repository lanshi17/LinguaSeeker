# 领域层 (Domain Layer)

领域层是六边形架构的核心，包含纯业务逻辑，与技术实现无关。本层遵循领域驱动设计 (DDD) 原则，按子域划分代码。

## 目录结构

```
domain/
├── __init__.py
├── models.py               # 领域模型
├── enums.py                # 枚举定义
├── abc/                    # 抽象接口
│   └── document_parser.py
├── agent/                  # Agent 子域
│   ├── workflow.py
│   ├── rag.py
│   ├── interaction.py
│   └── prompts.py
├── evidence/               # 证据子域
│   ├── aggregator.py
│   ├── classifier.py
│   ├── evaluation_framework.py
│   └── tools.py
├── graph/                  # 图谱子域
│   ├── search.py
│   ├── sync.py
│   └── association_service.py
├── literature/             # 文献子域
│   ├── pubmed_service.py
│   ├── firecrawl_service.py
│   └── acquisition_agent.py
├── variant/                # 变异子域
│   ├── service.py
│   ├── clinvar_client.py
│   └── clingen_client.py
├── mineru/                 # MinerU 子域
│   ├── component.py
│   └── constants.py
└── impl/                   # 领域实现 (应移至 Infrastructure)
    ├── document_storage.py
    └── pdf_parser.py
```

## 职责

领域层的主要职责：

1. **业务逻辑**: 实现核心业务规则
2. **领域模型**: 定义业务实体和值对象
3. **领域服务**: 封装跨实体的业务逻辑
4. **仓储接口**: 定义数据访问接口 (实现在 Infrastructure)
5. **领域事件**: 定义业务事件

## 架构位置

```
Application Layer (应用层)
    ↓
Domain Layer (领域层)  ← 本层 (纯业务逻辑)
    ↓
Infrastructure Layer (基础设施层)
```

## 核心子域

### 1. Agent 子域 (agent/)

负责 Agent 工作流编排和协作（8 个专用 Agent）：

| 文件 | 说明 |
|------|------|
| `workflow.py` | Agent 工作流定义 (基于 LangGraph) |
| `rag.py` | RAG (检索增强生成) 逻辑 |
| `interaction.py` | 用户交互逻辑 |
| `prompts.py` | Agent Prompt 模板 |

**8 个专用 Agent**:
```python
# 1. retrieval: 文献获取 (PubMed/Firecrawl)
# 2. parsing: 文档解析 (PDF 解析与结构提取)
# 3. mt: 多语种翻译 (文档翻译)
# 4. format: 多功能排版 (文档格式化)
# 5. vlm: 图片提取 (图片内容理解)
# 6. evidence: 证据提取 (证据记录抽取)
# 7. classification: ACMG 分类 (证据初步分类)
# 8. arbitration: 专家裁决 (ACMG 最终评级)

class EvidenceAgent:
    """证据分析 Agent"""
    
    def translate_markdown(self, state: ProcessingState) -> ProcessingState:
        """翻译 Markdown 文档"""
        pass
    
    def extract_entities(self, text: str) -> list[Entity]:
        """抽取实体"""
        pass
```

### 2. 证据子域 (evidence/)

负责证据的聚合、分类和评估：

| 文件 | 说明 |
|------|------|
| `aggregator.py` | 证据聚合 |
| `classifier.py` | 证据分类 |
| `evaluation_framework.py` | 评估框架 |
| `tools.py` | 证据工具 |

**关键类**:
```python
class EvidenceAggregator:
    """证据聚合器"""
    
    def aggregate(self, evidence_list: list[Evidence]) -> AggregatedEvidence:
        """聚合多个证据"""
        pass

class EvidenceClassifier:
    """证据分类器"""
    
    def classify(self, evidence: Evidence) -> EvidenceClass:
        """分类证据"""
        pass
```

### 3. 图谱子域 (graph/)

负责知识图谱的构建和查询：

| 文件 | 说明 |
|------|------|
| `search.py` | 图谱搜索 |
| `sync.py` | 图谱同步 |
| `association_service.py` | 关联服务 |

**关键类**:
```python
class GraphSearchService:
    """图谱搜索服务"""
    
    def search_by_gene(self, gene_symbol: str) -> list[Node]:
        """按基因搜索"""
        pass
    
    def search_by_variant(self, variant: str) -> list[Node]:
        """按变异搜索"""
        pass
    
    def natural_language_query(self, query: str) -> QueryResult:
        """自然语言查询"""
        pass
```

### 4. 文献子域 (literature/)

负责文献获取和解析：

| 文件 | 说明 |
|------|------|
| `pubmed_service.py` | PubMed 服务 |
| `firecrawl_service.py` | Firecrawl 服务 |
| `acquisition_agent.py` | 文献获取 Agent |

**关键类**:
```python
class PubMedService:
    """PubMed 文献服务"""
    
    def search(self, query: str, max_results: int = 100) -> list[PubMedArticle]:
        """搜索 PubMed 文献"""
        pass
    
    def fetch_by_pmid(self, pmid: str) -> PubMedArticle:
        """按 PMID 获取文献"""
        pass

class FirecrawlService:
    """Firecrawl 网页爬取服务"""
    
    async def crawl_url(self, url: str) -> CrawlResult:
        """爬取网页"""
        pass
    
    async def search(self, query: str) -> list[SearchResult]:
        """搜索网页"""
        pass
```

### 5. 变异子域 (variant/)

负责变异信息查询：

| 文件 | 说明 |
|------|------|
| `service.py` | 变异服务 |
| `clinvar_client.py` | ClinVar 客户端 |
| `clingen_client.py` | ClinGen 客户端 |

**关键类**:
```python
class VariantService:
    """变异服务"""
    
    def get_clinvar_info(self, variant: str) -> ClinVarInfo:
        """获取 ClinVar 信息"""
        pass
    
    def get_clingen_info(self, gene: str) -> ClinGenInfo:
        """获取 ClinGen 信息"""
        pass
```

### 6. MinerU 子域 (mineru/)

负责 PDF 解析：

| 文件 | 说明 |
|------|------|
| `component.py` | MinerU 组件 |
| `constants.py` | 常量定义 |

## 领域模型

### 核心实体

```python
from uuid import UUID
from datetime import datetime
from enum import Enum

class DocumentStatus(str, Enum):
    """文档状态"""
    UPLOADED = "uploaded"
    PARSING = "parsing"
    TRANSLATING = "translating"
    EXTRACTING = "extracting"
    COMPLETED = "completed"
    FAILED = "failed"

class Document:
    """文档实体"""
    
    document_id: UUID
    title: str
    original_filename: str
    file_hash: str
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime

class Evidence:
    """证据实体"""
    
    evidence_id: UUID
    document_id: UUID
    gene_symbol: str
    variant: str
    evidence_type: EvidenceType
    ps3_level: PS3Level | None
    confidence: float
    extracted_at: datetime

class Entity:
    """实体"""
    
    entity_id: str
    entity_type: EntityType  # Gene, Variant, Disease, etc.
    text: str
    start_pos: int
    end_pos: int
    metadata: dict
```

## 领域服务

### 证据评估框架

```python
class EvidenceEvaluationFramework:
    """证据评估框架"""
    
    def evaluate_ps3(
        self,
        gene: str,
        variant: str,
        evidence_list: list[Evidence]
    ) -> PS3Evaluation:
        """
        评估 PS3 证据等级
        
        返回:
            PS3Evaluation: 包含证据等级、置信度、支持证据
        """
        pass
    
    def evaluate_bs3(
        self,
        gene: str,
        variant: str,
        evidence_list: list[Evidence]
    ) -> BS3Evaluation:
        """
        评估 BS3 证据等级
        
        返回:
            BS3Evaluation: 包含证据等级、置信度、支持证据
        """
        pass
```

## 抽象接口

### document_parser.py

```python
from abc import ABC, abstractmethod

class DocumentParser(ABC):
    """文档解析器接口"""
    
    @abstractmethod
    async def parse(self, file_path: str) -> ParsedDocument:
        """解析文档"""
        pass
    
    @abstractmethod
    async def extract_text(self, parsed: ParsedDocument) -> str:
        """提取文本"""
        pass
    
    @abstractmethod
    async def extract_images(
        self, 
        parsed: ParsedDocument
    ) -> list[Image]:
        """提取图片"""
        pass
```

## 使用示例

### 领域服务调用

```python
from src.domain.evidence.aggregator import EvidenceAggregator
from src.domain.evidence.classifier import EvidenceClassifier

# 聚合证据
aggregator = EvidenceAggregator()
aggregated = aggregator.aggregate(evidence_list)

# 分类证据
classifier = EvidenceClassifier()
classification = classifier.classify(aggregated)
```

### 领域模型使用

```python
from src.domain.models import Document, DocumentStatus

# 创建文档
doc = Document(
    document_id=uuid4(),
    title="Test Document",
    original_filename="test.pdf",
    file_hash="abc123",
    status=DocumentStatus.UPLOADED
)

# 更新状态
doc.status = DocumentStatus.PARSING
```

## 最佳实践

### 1. 保持领域层纯净

领域层不应依赖技术实现：

```python
# ✅ 推荐 - 纯业务逻辑
class EvidenceAggregator:
    def aggregate(self, evidence_list: list[Evidence]) -> AggregatedEvidence:
        # 业务逻辑
        pass

# ❌ 不推荐 - 包含技术依赖
class EvidenceAggregator:
    def aggregate(self, evidence_list: list[Evidence]) -> AggregatedEvidence:
        db = get_database()  # 不应在领域层
        result = db.query(...)
        pass
```

### 2. 使用领域事件

```python
class DocumentParsedEvent:
    """文档解析完成事件"""
    
    document_id: UUID
    parsed_content: ParsedDocument
    parsed_at: datetime

# 发布事件
event_bus.publish(DocumentParsedEvent(...))
```

### 3. 仓储模式

```python
# 定义接口 (领域层)
class DocumentRepository(ABC):
    @abstractmethod
    def find_by_id(self, id: UUID) -> Document | None:
        pass
    
    @abstractmethod
    def save(self, document: Document) -> None:
        pass

# 实现 (基础设施层)
class PostgresDocumentRepository(DocumentRepository):
    def find_by_id(self, id: UUID) -> Document | None:
        # PostgreSQL 实现
        pass
    
    def save(self, document: Document) -> None:
        # PostgreSQL 实现
        pass
```

### 4. 值对象

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class GeneSymbol:
    """基因符号值对象"""
    
    symbol: str
    
    def __post_init__(self):
        if not self.symbol:
            raise ValueError("Gene symbol cannot be empty")
        # HGNC 命名规范验证
        if not re.match(r'^[A-Z0-9-]+$', self.symbol):
            raise ValueError("Invalid gene symbol format")
```

## 测试

### 单元测试

```python
import pytest
from src.domain.evidence.aggregator import EvidenceAggregator

def test_aggregate_evidence():
    aggregator = EvidenceAggregator()
    evidence_list = [
        Evidence(...),
        Evidence(...)
    ]
    
    result = aggregator.aggregate(evidence_list)
    
    assert result.total_count == 2
    assert result.ps3_level is not None
```

### 领域逻辑测试

```python
def test_ps3_evaluation_strong_evidence():
    framework = EvidenceEvaluationFramework()
    
    evidence_list = [
        Evidence(confidence=0.95, ...),
        Evidence(confidence=0.92, ...),
        Evidence(confidence=0.88, ...)
    ]
    
    result = framework.evaluate_ps3("BRCA1", "c.123A>G", evidence_list)
    
    assert result.ps3_level == PS3Level.STRONG
    assert result.confidence > 0.9
```

## 架构问题说明

⚠️ **当前架构存在的问题**:

1. **领域实现混杂**: `domain/impl/` 目录包含技术实现细节，应移至 `infrastructure/`
2. **职责边界模糊**: 部分领域服务与基础设施服务职责重叠

**建议重构**:
- 将 `domain/impl/` 移至 `infrastructure/adapters/`
- 明确领域服务与基础设施服务的边界
- 确保领域层只包含纯业务逻辑

## 相关文档

- [后端 README](../../README.md)
- [应用层 README](../application/README.md)
- [基础设施层 README](../infrastructure/README.md)

---

**最后更新**: 2026-03-22 (v3.0)
