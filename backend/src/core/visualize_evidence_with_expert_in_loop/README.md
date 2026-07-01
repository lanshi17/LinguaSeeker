# Phase 4 — 证据可视化与专家交互

> 提供证据审查、搜索、纠错和对话式交互的后端服务，支持专家在环（expert-in-the-loop）的证据质量保障流程。

## 概述

Phase 4 是 Lingua Seeker 的人机交互层，为前端提供完整的证据审查和反馈闭环。它接收 Phase 3 标准化后的规范证据，提供以下核心能力：

- **证据搜索**：字段级透视为分组证据行，支持 PMID/基因/变异/疾病/分类多维过滤
- **证据纠错**：PATCH 接口修改证据字段和审查状态，附带字段级审计追踪
- **LLM 对话**：专家可通过自然语言查询或纠正证据，LLM 自动解析意图并执行操作
- **源文本溯源**：证据字段可追溯到原始/翻译文档的具体文本段落和页码
- **文献档案**：每篇文档的聚合证据概览，包含证据分组、统计和审查状态

## 目录结构

```
visualize_evidence_with_expert_in_loop/
├── __init__.py           # 空包声明
├── contracts.py          # Pydantic 模型和类型化契约（API 请求/响应）
├── search_service.py     # SearchService：证据搜索与文档内容加载
├── feedback_service.py   # FeedbackService：证据纠错与审查状态管理
├── delta_audit_service.py # DeltaAuditService：字段级差异计算与审计事件持久化
├── chat_service.py       # ChatService：LLM 对话会话管理与动作解析
├── source_linker.py      # SourceLinker：证据到源文本的溯源链接
└── providers.py          # LLM 提供者：ChatLLMProvider、ReasoningLLMProvider
```

## 核心组件

### SearchService（`search_service.py`）

证据搜索核心，提供：
- **分页搜索** — 按 PMID、基因、变异、疾病、审查状态、置信度过滤证据
- **字段级透视** — 将字段级提取记录分组为结构化证据行
- **文档内容加载** — 从管道输出目录加载原始/翻译文本和结构化区块
- **body 文本过滤** — 剥离文章元数据（标题、作者、摘要等），仅保留正文
- **高亮构建** — 根据源文本偏移量构建可高亮的证据溯源片段

### FeedbackService（`feedback_service.py`）

证据纠错服务：
- `patch_evidence()` — 应用证据字段补丁，记录审计事件
- 字段差异计算 → 审计事件持久化 → 文献档案/搜索索引刷新

### DeltaAuditService（`delta_audit_service.py`）

审计追踪：
- `compute_deltas()` — 计算两个 `EvidenceCardPayload` 之间的字段级差异
- `record_audit_event()` — 持久化审查审计事件（含 reviewer_id、target_type、变更原因）
- `list_audit_events()` — 按条件查询审计历史

### ChatService（`chat_service.py`）

LLM 对话管理：
- **会话管理** — 创建/列表/删除聊天会话，可绑定处理运行
- **流式消息** — SSE 流式输出 LLM 回复，含 keepalive 心跳
- **动作解析** — 从 LLM 输出中提取结构化 `ChatAction`（查询证据、修改字段、更新状态等）
- **意图识别** — 正则模式匹配区分问题型和纠正型用户输入
- **证据上下文注入** — 将关联证据数据注入 LLM 提示词

### SourceLinker（`source_linker.py`）

证据溯源：
- `get_track_span()` — 获取单轨（原始/翻译）的源文本段落
- `get_bilingual_span()` — 获取双轨对照的溯源结果，含对齐置信度

### LLM Providers（`providers.py`）

- **`ChatLLMProvider`** — 轻量对话模型，支持 SSE 流式输出和 `<<<ACTION>>>` 分隔符解析
- **`ReasoningLLMProvider`** — 高精度推理模型，用于复杂证据分析
- **`_BaseLLMProvider`** — 共享 HTTP 客户端管理、SSE 流解析

## 数据流

```
Phase 3 CanonicalEvidenceItem
        │
        ▼
   SearchService.search()
        ├─→ 字段透视 → 分组证据行 → 分页结果
        └─→ 文档内容加载 → 正文过滤 → 高亮构建
        │
        ▼
   ChatService.send_message()
        ├─→ LLM 推理 → ChatAction 解析
        └─→ FeedbackService.patch_evidence()
                ├─→ DeltaAuditService.compute_deltas()
                ├─→ 审计事件持久化
                └─→ 文献档案/搜索索引刷新
        │
        ▼
   SourceLinker.get_bilingual_span()
        └─→ 原始/翻译文本段落溯源
```

## 关键数据契约

| 契约 | 用途 |
|------|------|
| `EvidenceSearchRequest/Response` | 证据搜索 API |
| `EvidencePatchRequest` | 证据纠错请求 |
| `ChatSessionResponse/ChatMessageResponse` | 对话会话 API |
| `EvidenceCardPayload` | 证据卡片字段定义（含 `DIFF_FIELDS`） |
| `ReviewAuditEventResponse` | 审计事件 API |
| `LiteratureProfileSummary/DetailResponse` | 文献档案 API |
| `BilingualSpan` / `TrackSpan` | 溯源结果 |

## 使用方式

```python
# 证据搜索
search_service = SearchService(session)
results = await search_service.search(EvidenceSearchRequest(...))

# 证据纠错
feedback_service = FeedbackService(session)
patch_result = await feedback_service.patch_evidence(
    canonical_evidence_id=evidence_id,
    request=EvidencePatchRequest(review_status="approved", field_patches={...}),
    reviewer_id=user_id,
)

# LLM 对话
chat_service = ChatService(session, llm_provider)
async for chunk in chat_service.send_message_stream(session_id, "这个基因的变异分类是什么？"):
    yield chunk  # SSE 流式输出
```
