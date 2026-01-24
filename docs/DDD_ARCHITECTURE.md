# ACMG PS3 DDD 重构文档

## 架构概览

按照领域驱动设计(DDD)原则重构，分为四层清晰的架构：

```
src/
├── domain/                    # 领域层(核心业务逻辑，框架无关)
│   ├── entities/             # 聚合根和实体
│   │   ├── pipeline_state.py # 处理管线状态实体
│   │   ├── evidence.py       # 证据实体 (包含OddsPath计算)
│   │   └── document.py       # 文档实体 (处理高亮)
│   ├── value_objects/        # 值对象(不变的值类型)
│   │   ├── language.py       # 语言值对象 (zh,ja,en,ru,de,fr)
│   │   ├── odds_path.py      # OddsPath计算器 (P1,P2→强度)
│   │   └── evidence_strength.py # 证据强度枚举
│   ├── repositories/         # 仓储接口(抽象)
│   │   ├── pdf_repository.py      # PDF操作接口
│   │   └── rag_repository.py      # RAG检索接口
│   └── services/             # 领域服务接口(业务规则)
│       ├── language_detector.py   # 语言检测服务
│       ├── translator.py          # 翻译服务
│       ├── evidence_extractor.py  # 证据提取服务
│       └── arbiter.py             # 仲裁评分服务
│
├── infrastructure/           # 基础设施层(技术实现)
│   ├── llm/                  # LLM提供者实现
│   │   ├── llm_provider.py        # LLM工厂
│   │   ├── language_detector_impl.py  # 语言检测实现
│   │   ├── translator_impl.py         # 翻译实现
│   │   ├── evidence_extractor_impl.py # 证据提取实现
│   │   └── arbiter_impl.py            # 仲裁实现
│   ├── repositories/        # 仓储实现
│   │   ├── pdf_repository_impl.py     # PDF操作实现
│   │   └── rag_repository_impl.py     # RAG检索实现
│   ├── embeddings/          # 嵌入式向量
│   │   └── embedding_provider.py  # 向量模型工厂
│   └── pdf/                 # PDF处理工具
│
├── application/              # 应用层(用例和编排)
│   ├── dto.py               # 数据传输对象
│   ├── services/            # 应用服务
│   │   └── pipeline_orchestrator.py  # 流程编排服务
│   └── use_cases/           # 用例
│       └── process_pdf.py   # PDF处理用例
│
├── interfaces/              # 接口层(外部API)
│   └── __init__.py          # 公共API入口 (run_pipeline函数)
│
├── simple_acmgAgent.py      # 向后兼容包装
├── config.py                # 全局配置
├── exceptions.py            # 异常定义
└── logger.py                # 日志工具
```

## 核心设计模式

### 1. **值对象 (Value Objects)**
- `Language`: 支持的语言枚举，包含自动转换逻辑
- `OddsPath`: PS3证据强度计算，自动分类为 supporting/moderate/strong/very-strong
- `EvidenceStrength`: 强度等级

### 2. **实体 (Entities)**
- `PipelineState`: 跟踪处理进度的核心实体
- `Evidence`: 聚合根，关联OddsPath值对象
- `Document`: 文档生命周期管理

### 3. **仓储模式 (Repository Pattern)**
- `PDFRepository`: PDF文本提取、语言检测、OCR接口
- `RAGRepository`: 向量索引构建、知识检索接口

### 4. **领域服务 (Domain Services)**
- 业务规则集中，完全独立于框架
- 实现逻辑与基础设施解耦

### 5. **应用编排 (Orchestration)**
- `PipelineOrchestrator`: 协调各个领域服务
- `ProcessPDFUseCase`: 对外用例入口

## 依赖关系

```
用户代码
    ↓
interfaces.run_pipeline()  [公共API]
    ↓
ProcessPDFUseCase
    ↓
PipelineOrchestrator  [应用层]
    ↓
Domain Services  [领域层]  ← Interfaces/Contracts
    ↓
Infrastructure Implementations  [基础设施层]
```

## 向后兼容性

原有API完全保留：

```python
from src.simple_acmgAgent import run_pipeline

result = run_pipeline("paper.pdf", out_dir="outputs")
# 返回相同格式: {
#   "detected_language": "zh",
#   "arbiter_score": 85.0,
#   "evidence": {...},
#   "output_markdown": "...",
#   "highlight_markdown": "..."
# }
```

## 主要优势

1. **关注点分离**: 业务逻辑、技术实现、接口层清晰划分
2. **高内聚，低耦合**: 通过接口和依赖注入解耦
3. **易于测试**: 每层可独立单元测试
4. **易于扩展**: 
   - 添加新的LLM提供商 → 新建 `infrastructure/llm/*_impl.py`
   - 更换向量库 → 新建 `infrastructure/repositories/rag_repository_new.py`
   - 支持新语言 → 在 `Language` 枚举中添加
5. **可读性**: 代码意图清晰，每个类职责单一

## 使用示例

### 编程方式调用

```python
from src.interfaces import run_pipeline

result = run_pipeline("paper.pdf")
print(result["arbiter_score"])
print(result["evidence"]["odds_path"])
```

### 依赖注入扩展

```python
from src.config import AppConfig
from src.infrastructure import PDFRepositoryImpl, RAGRepositoryImpl, LLMProvider
from src.domain.services import LanguageDetectorServiceImpl
from src.application.services import PipelineOrchestrator
from src.application.dto import ProcessPDFRequest

cfg = AppConfig.from_env()
llm_provider = LLMProvider(cfg)
pdf_repo = PDFRepositoryImpl()
rag_repo = RAGRepositoryImpl(embeddings)

lang_detector = LanguageDetectorServiceImpl(pdf_repo)
# 自定义任何服务实现...

orchestrator = PipelineOrchestrator(cfg, pdf_repo, rag_repo, ...)
result = orchestrator.process_pdf(ProcessPDFRequest("paper.pdf"))
```

## 配置流程

```
1. 加载 .env (通过 AppConfig.from_env())
2. 创建 LLM/Embedding 提供者
3. 初始化基础设施实现
4. 初始化领域服务
5. 创建应用编排器
6. 执行用例
```

## 扩展指南

### 添加新的证据提取方法

1. 在 `domain/services/evidence_extractor.py` 中定义新接口方法
2. 在 `infrastructure/llm/evidence_extractor_impl.py` 中实现

### 支持新的文档格式

1. 在 `domain/repositories/pdf_repository.py` 中添加新接口方法
2. 在 `infrastructure/repositories/pdf_repository_impl.py` 中实现处理逻辑

### 集成新的LLM

1. 在 `infrastructure/llm/llm_provider.py` 中注册新提供者
2. 创建新的服务实现类 (如 `new_llm_impl.py`)
