# DDD 文件结构总览

## 📁 完整的项目文件树

```
src/
├── main.py                                 ⭐ 【更新】FastAPI 主入口
│   └── 更新内容：修改导入路径为 .presentation.routes
│
├── config.py                               ⭐ 配置管理
├── schemas.py                              ⭐ Pydantic 数据模型
│
├── presentation/                           🟦 【表现层】
│   ├── __init__.py
│   ├── api_routes.py                       ⚠️ 旧文件（保留参考）
│   └── routes.py                           ✨ 【新建】10个 RESTful 端点
│       ├─ 10 个 API 端点定义
│       ├─ 请求/响应处理
│       └─ 调用 application layer
│
├── application/                            🟩 【应用层】
│   ├── __init__.py                        (已存在)
│   └── services.py                        ✨ 【新建】业务流程编排
│       ├─ TaskService (任务管理)
│       │  ├─ create_task()                创建任务
│       │  ├─ _process_task()              5阶段处理流水线
│       │  ├─ get_task_status()            获取任务状态
│       │  └─ get_task_result()            获取处理结果
│       ├─ EvidenceQueryService (证据查询)
│       │  └─ query_evidence()             按HGVS查询
│       ├─ MetadataService (元数据)
│       │  ├─ get_supported_languages()
│       │  └─ get_evidence_levels()
│       └─ 存储实例：task_store, evidence_store
│
├── domain/                                 🟨 【领域层】
│   ├── __init__.py                        (已存在)
│   │
│   ├── models.py                          ✨ 【新建】领域实体
│   │   ├─ 【枚举】
│   │   │  ├─ TaskStatus: accepted, processing, success, failed
│   │   │  ├─ ProcessingStage: extraction, translation, evidence, structuring, complete
│   │   │  ├─ EvidenceLevel: PS3, PS3_moderate, BS3, BS3_moderate, BP1
│   │   │  ├─ InputType: pdf, pmid, doi
│   │   │  └─ Language: zh, ja, en, ru, de, fr
│   │   │
│   │   ├─ 【值对象】
│   │   │  └─ HGVS (见 value_objects.py)
│   │   │
│   │   ├─ 【实体 - Entity】
│   │   │  ├─ Task (聚合根)
│   │   │  │  ├─ task_id, input_type, value
│   │   │  │  ├─ status, stage, project_tag
│   │   │  │  ├─ created_at, updated_at, completed_at
│   │   │  │  ├─ is_processing()
│   │   │  │  ├─ is_completed()
│   │   │  │  └─ mark_as_failed(error)
│   │   │  │
│   │   │  ├─ Evidence (证据实体)
│   │   │  │  ├─ variant (HGVS notation)
│   │   │  │  ├─ level, score (0-100), description
│   │   │  │  ├─ source (论文ID)
│   │   │  │  └─ is_strong_evidence()
│   │   │  │
│   │   │  ├─ Document (文档实体)
│   │   │  │  ├─ doc_id, title, authors, year
│   │   │  │  ├─ source_language, content
│   │   │  │  └─ metadata
│   │   │  │
│   │   │  └─ AnalysisModel (分析模型 - 聚合根)
│   │   │     ├─ analysis_id, task_id
│   │   │     ├─ variant, evidence_items
│   │   │     ├─ summary, confidence_score
│   │   │     ├─ get_strongest_evidence()
│   │   │     └─ has_sufficient_evidence(min_score)
│   │
│   ├── value_objects.py                   ✨ 【新建】值对象
│   │   └─ HGVS (基因变异表达式)
│   │      ├─ notation: str
│   │      ├─ _is_valid_hgvs()            验证格式
│   │      ├─ normalize()                 标准化
│   │      ├─ __eq__()                    相等比较
│   │      └─ __hash__()                  可哈希化
│   │
│   ├── services.py                        ✨ 【新建】领域服务
│   │   ├─ DocumentExtractionService
│   │   │  └─ async extract(value)        文献文本提取
│   │   │
│   │   ├─ TranslationService
│   │   │  ├─ async translate(text, target_language)
│   │   │  └─ detect_language(text)
│   │   │
│   │   ├─ EvidenceExtractionService
│   │   │  └─ async extract(text)         从文本提取证据
│   │   │
│   │   ├─ VariantNormalizationService
│   │   │  ├─ normalize_hgvs(variant)
│   │   │  └─ parse_hgvs(variant)
│   │   │
│   │   ├─ EvidenceRankingService
│   │   │  └─ rank_evidence(evidence_items)
│   │   │
│   │   └─ VCFService
│   │      ├─ parse_vcf_variant(vcf_str)
│   │      └─ convert_hgvs_to_vcf(hgvs)
│   │
│   ├── repositories/                      (未来扩展)
│   │   └─ (仓储接口定义)
│   │
│   └── (其他现有领域相关文件)
│
└── infrastructure/                         🟪 【基础设施层】
    ├── __init__.py                        (已存在)
    │
    ├── exceptions.py                      ✨ 【新建】异常定义
    │   ├─ 【异常体系】
    │   │  ├─ APIException (基类)
    │   │  │  ├─ message, error_code, status_code
    │   │  │  ├─ to_dict()
    │   │  │  └─ (属性和方法)
    │   │  │
    │   │  ├─ BadRequestError (400)
    │   │  ├─ ForbiddenError (403)
    │   │  ├─ NotFoundError (404)
    │   │  ├─ InvalidHGVSError
    │   │  ├─ InvalidInputError
    │   │  ├─ ProcessingError (500)
    │   │  └─ ValidationError
    │   │
    │   ├─ 【工具函数】
    │   ├─ create_error_response(exc)
    │   └─ handle_api_exception(exc)
    │
    ├── storage.py                         ✨ 【新建】数据存储
    │   ├─ TaskStore (任务存储)
    │   │  ├─ save_task(task)
    │   │  ├─ get_task(task_id)
    │   │  ├─ list_tasks(project_tag)
    │   │  └─ delete_task(task_id)
    │   │
    │   ├─ EvidenceStore (证据存储)
    │   │  ├─ save_evidence(evidence)
    │   │  ├─ query(variant, evidence_level, min_score)
    │   │  ├─ get_all_variants()
    │   │  └─ delete_evidence(variant)
    │   │
    │   ├─ FileStore (文件存储)
    │   │  ├─ save_json(filename, data)
    │   │  ├─ load_json(filename)
    │   │  ├─ save_html(filename, content)
    │   │  └─ get_file_path(filename, ext)
    │   │
    │   └─ (当前使用内存实现，可替换为数据库)
    │
    └── (其他现有基础设施文件)
```

## 📊 文件统计

### 新建文件

| 文件 | 行数 | 说明 |
|------|------|------|
| `presentation/routes.py` | ~400 | 10个RESTful端点 |
| `application/services.py` | ~300 | 3个应用服务 |
| `domain/models.py` | ~250 | 实体和枚举 |
| `domain/value_objects.py` | ~50 | HGVS值对象 |
| `domain/services.py` | ~250 | 6个领域服务 |
| `infrastructure/exceptions.py` | ~150 | 异常体系 |
| `infrastructure/storage.py` | ~250 | 3个存储实现 |
| **合计** | **~1650** | **新增代码** |

### 更新文件

| 文件 | 变更 | 说明 |
|------|------|------|
| `main.py` | 修改第8-11行 | 更新导入路径为相对导入 |

### 文档文件

| 文件 | 说明 |
|------|------|
| `docs/DDD_ARCHITECTURE_FINAL.md` | 完整架构说明 |
| `docs/DDD_QUICK_REFERENCE.md` | 快速参考和FAQ |
| `docs/DDD_RESTRUCTURING_COMPLETE.md` | 重组完成报告 |
| `docs/DDD_IMPORT_GUIDE.md` | 导入规范指南 |
| `docs/DDD_FILE_STRUCTURE.md` | 本文件 |

## 🔄 数据流详解

### API 请求处理流程

```
1. HTTP Request 
   ↓
2. presentation/routes.py
   ├─ 验证 TaskSubmissionRequest (Pydantic)
   ├─ 调用 TaskService.create_task()
   └─ 返回 TaskSubmissionResponse
   ↓
3. application/services.py::TaskService
   ├─ 创建 Task 实体 (domain/models.py)
   ├─ 调用 task_store.save_task() (infrastructure/storage.py)
   ├─ 启动异步处理：asyncio.create_task(...)
   └─ 返回 task_id
   ↓
4. HTTP 202 Accepted Response
   └─ {task_id, status, message}

异步处理流程：
↓
TaskService._process_task(task_id)
├─ Stage 1: EXTRACTION
│  └─ DocumentExtractionService.extract()
│     └─ 返回提取文本
├─ Stage 2: TRANSLATION
│  └─ TranslationService.translate()
│     └─ 返回英文翻译
├─ Stage 3: EVIDENCE
│  └─ EvidenceExtractionService.extract()
│     └─ 返回 Evidence 列表
├─ Stage 4: STRUCTURING
│  └─ _structure_evidence()
│     └─ 返回结构化JSON
└─ Stage 5: COMPLETE
   └─ 更新任务状态为 SUCCESS
      └─ task_store.save_task(task)
```

## 🎯 分层职责总结

### 表现层 (presentation/)
- **职责**：HTTP处理，请求验证
- **输入**：HTTP JSON
- **输出**：HTTP JSON/HTML
- **关键文件**：routes.py

### 应用层 (application/)
- **职责**：业务流程编排，用例实现
- **输入**：来自表现层的请求参数
- **输出**：领域对象和结果数据
- **关键文件**：services.py

### 领域层 (domain/)
- **职责**：业务规则，核心逻辑
- **输入**：参数（原始类型或值对象）
- **输出**：实体和计算结果
- **关键文件**：models.py, value_objects.py, services.py

### 基础设施层 (infrastructure/)
- **职责**：技术实现，外部依赖
- **输入**：来自应用层的数据
- **输出**：持久化数据或异常
- **关键文件**：storage.py, exceptions.py

## 🔌 导入依赖图

```
    presentation/
         ↓
    application/
       ↙   ↘
   domain/   infrastructure/
      ↓        ↓
    (独立)   (实现domain)
```

**正向依赖**（允许）：
```
presentation → application → domain
                ↓
            infrastructure (实现)
```

**反向依赖**（禁止）：
```
❌ domain → application
❌ domain → presentation
❌ infrastructure → application
❌ infrastructure → presentation
```

## ✨ 新增文件的功能概览

### routes.py（400行）
```
✓ 10个 REST 端点
✓ 请求参数验证
✓ 异常处理
✓ 响应格式化
✓ 调用应用层服务
```

### services.py (application)（300行）
```
✓ TaskService：任务管理和5阶段处理
✓ EvidenceQueryService：证据查询
✓ MetadataService：元数据服务
✓ 业务规则实现
✓ 存储和缓存管理
```

### models.py（250行）
```
✓ 4个枚举（TaskStatus, ProcessingStage, EvidenceLevel, InputType）
✓ 4个实体（Task, Evidence, Document, AnalysisModel）
✓ 业务方法（is_processing, mark_as_completed等）
✓ 类型安全定义
```

### value_objects.py（50行）
```
✓ HGVS 值对象
✓ 格式验证
✓ 标准化
✓ 相等比较和哈希
```

### services.py (domain)（250行）
```
✓ 6个领域服务
✓ DocumentExtractionService
✓ TranslationService
✓ EvidenceExtractionService
✓ VariantNormalizationService
✓ EvidenceRankingService
✓ VCFService
```

### exceptions.py（150行）
```
✓ 异常基类 APIException
✓ 7种具体异常
✓ HTTP状态码映射
✓ 错误响应生成
```

### storage.py（250行）
```
✓ TaskStore：任务内存存储
✓ EvidenceStore：证据存储+示例数据
✓ FileStore：文件I/O操作
✓ 可替换为数据库实现
```

## 📚 快速导航

要找到特定功能，查看这个表：

| 我要... | 去这个文件 | 类/方法 |
|--------|-----------|--------|
| **创建新端点** | `presentation/routes.py` | @router.post/get |
| **修改任务处理** | `application/services.py` | TaskService._process_task |
| **添加验证** | `domain/models.py` | Task.__init__ |
| **修改文献提取** | `domain/services.py` | DocumentExtractionService |
| **处理异常** | `infrastructure/exceptions.py` | APIException |
| **保存数据** | `infrastructure/storage.py` | TaskStore/EvidenceStore |
| **定义数据模型** | `schemas.py` | 各Pydantic类 |
| **配置应用** | `config.py` | BaseSettings |
| **启动应用** | `main.py` | create_app() |

---

## 🚀 后续开发指南

### 集成数据库
1. 修改 `infrastructure/storage.py`
2. 添加 SQLAlchemy ORM 模型
3. 应用层无需改动

### 添加新处理阶段
1. 更新 `domain/models.py` 中的 ProcessingStage 枚举
2. 创建新的领域服务
3. 修改 `application/services.py` 中的 _process_task
4. 无需修改表现层

### 扩展异常处理
1. 添加新异常类到 `infrastructure/exceptions.py`
2. 在表现层路由中捕获处理
3. 返回标准化错误响应

### 实现事件驱动
1. 创建 `domain/events.py` 定义领域事件
2. 在 `application/services.py` 中发布事件
3. 创建事件处理器订阅事件

---

**项目已按 DDD 原则完整组织！** ✨

总代码行数：~1900 行（源代码）+ ~1000 行（文档）
