# APP_FLOW — ACMG Lingua Application Flow

## 1. Navigation & Architecture Overview

ACMG Lingua organizes all user interaction through four fixed tabs in the global topbar:

```
┌─────────────────────────────────────────────────────────────────┐
│  ACMG-Lingua   [AI 助手]  [任务看板]  [知识库查询]  [设置]       │
└─────────────────────────────────────────────────────────────────┘
```

| Tab | Route | Core Flow |
|---|---|---|
| AI Assistant | `/(dashboard)/assistant` | Upload → parse → extract → correct → ingest (chat-driven) |
| Task Board | `/(dashboard)/task-board` | Monitor → filter → batch-operate → enter workspace |
| Knowledge Base | `/(dashboard)/knowledge-base` | Search → explore → trace → compare → export |
| Settings | `/(dashboard)/settings` | View versions → update → configure |

The Evidence Workspace (`/task-board/workspace/[taskId]`) and Variant Detail (`/knowledge-base/variant/[variantId]`) are sub-pages reachable from their parent tabs, with back-navigation preserving parent state.

## 2. Architecture: Orchestrated Vertical Slices at Runtime

```
Entry (Topbar tabs)
  │
  ▼
Page-level orchestration (app/**/page.tsx)
  │  Data composition, routing, state wiring only
  │
  ├──► Feature slice: AI Assistant (chat, evidence cards, sessions)
  ├──► Feature slice: Task Board (list, filters, batch, delta audit)
  ├──► Feature slice: Evidence Workspace (MD view, cards, shortcuts, traceability)
  ├──► Feature slice: Knowledge Base (search, matrix, comparison, export)
  └──► Feature slice: Settings (vocabularies, templates, config)
          │
          ▼
Shared infrastructure: API clients, hooks, types, stores, UI primitives
```

At runtime, the frontend calls FastAPI `/api/v1/*` endpoints. FastAPI owns business logic, orchestration, and persistence. Next.js proxies API calls and renders UI.

## 3. Tab 1: AI Assistant Flow

This is the primary entry point. All literature processing is chat-driven.

### 3.1 Start a Session

```
User opens AI Assistant tab
  │
  ├── New session: empty chat with input box
  │     └── Session sidebar shows previous conversations (collapsible)
  │
  └── Click existing session in sidebar → restore full chat history + context
```

### 3.2 Chat-Driven Extraction (Three-Round Flow)

```
Round 1 — Ingestion & Parse Feedback
─────────────────────────────────────
User action: Drag PDF / Type PMID / NL instruction ("提取 PMID 38000001 的证据")
  │
  ▼
POST /api/v1/chat/stream  (SSE)
  │
  ▼
System message bubble (SSE typewriter):
  "正在解析 PDF...  ✓ 提取到 32 页 Markdown
   识别文献：PMID 38000001 | Zhang et al. 2024 | Nature Genetics
   启动证据提取 Agent...
     → 扫描功能实验段落
     → 发现 Luciferase assay 数据
     → 映射 HPO 词表...
   提取完成，请确认下方证据卡片。"
  │  (On MinerU failure: "解析失败：[原因]" — no complex recovery)
  │
  ▼
Round 2 — Inline Evidence Cards
─────────────────────────────────────
System renders evidence form cards as special message bubbles in chat:
  ┌─────────────────────────────────────┐
  │ 🧬 证据卡片 #1/3 · 功能实验证据      │
  │ 变异: NM_000251.3:c.942+3A>T [只读] │
  │ 基因: MLH1                    [只读] │
  │ 表型: [HP:0001250 ×] [+添加]        │
  │ ACMG: [PS3 ▾]                       │
  │ 原文: "Luciferase activity..."       │
  │         [✓ 确认]  [↺ 重新提取]       │
  └─────────────────────────────────────┘
  │
  ▼
User actions on cards:
  ├── Inline edit fields (HPO autocomplete, ACMG rule dropdown, text fields)
  │     └── Delta silently recorded → no popup
  ├── Click "查看原文上下文" → expand ±3 paragraph context in-card
  ├── Click "✓ 确认入库" → card marked confirmed, evidence persisted
  └── Click "↺ 重新提取此条" → re-extract this evidence item
  │
  ▼
Round 3 — Natural Language Correction
─────────────────────────────────────
User types correction in chat input:
  "第一张卡片的表型应该是 HP:0001250 癫痫发作，不是 HP:0001251"
  │
  ▼
System parses intent → updates card fields → re-renders cards
  │  (All corrections stay in conversation — no separate edit dialogs)
  │
  ▼
User confirms all cards → task moves to "已完成" on Task Board
```

### 3.3 Batch Mode Flow

```
User toggles "批量模式" near input
  │
  ▼
Upload .txt file with PMID list (one per line)
  │
  ▼
System creates background tasks for each PMID
  │  (User can continue working — no need to wait)
  │
  ▼
Results appear in Task Board "待复核" queue
  │
  ▼
Notification entry in session sidebar: "批量任务完成 (20 篇)"
```

### 3.4 Session Persistence

```
Chat session saved on every message exchange:
  ├── session_id
  ├── task_id (associated literature task)
  ├── messages[] (all message types: text, system, evidence-card)
  └── metadata (PMID, title, created_at, updated_at)

Session sidebar:
  ├── Search by PMID, gene name, date
  ├── Click session → restore full history from POST /api/v1/chat/sessions/:id
  └── Session naming: auto from literature title or PMID
```

## 4. Tab 2: Task Board Flow

### 4.1 Browse & Filter

```
User opens Task Board tab
  │
  ▼
GET /api/v1/tasks?status=all
  │
  ▼
Status filter bar with counts:
  [全部 (142)] [解析中 (3)] [提取中 (7)] [待复核 (28)] [已完成 (98)] [失败 (6)]
  │
  ├── Click status → filter tasks by status
  ├── Search box → fuzzy search by PMID, gene, title
  └── Time range filter → date range selector
```

### 4.2 Task List Interaction

```
Task row:
  ┌───────────────────────────────────────────────────────────────┐
  │ ○ [待复核] PMID 38000001 Zhang et al. 2024 · MLH1            │
  │             已提取 3 条证据    2 小时前    [查看工作台] [···] │
  └───────────────────────────────────────────────────────────────┘
  │
  ├── Click "查看工作台" → navigate to workspace/[taskId]
  │     └── Back button returns to task board, preserving filter + scroll
  │
  ├── Click "···" → delta audit panel slides out
  │     └── GET /api/v1/tasks/:id/delta
  │     └── Shows modification history in diff format:
  │         2024-01-15 14:32  表型字段  HP:0001251 → HP:0001250
  │         2024-01-15 14:35  ACMG规则  PS3 → PS3_moderate
  │
  └── Click "重试" (failed tasks) → POST /api/v1/tasks/:id/retry
```

### 4.3 Batch Operations

```
User checks multiple tasks (checkboxes)
  │
  ▼
Floating action bar:
  已选 12 条  [批量重试]  [批量删除]  [批量导出 CSV]  [×取消]
  │
  ├── 批量重试 → POST /api/v1/tasks/batch/retry
  ├── 批量删除 → DELETE /api/v1/tasks/batch
  ├── 批量导出 CSV → GET /api/v1/tasks/batch/export?ids=...
  └── ×取消 → clear selection
```

### 4.4 Resource Monitoring

```
Collapse/expand panel (top-right):
  ┌────────────────────────────┐
  │  系统状态               ▾  │
  │  队列深度      7 个任务    │  ← GET /api/v1/system/status
  │  当前处理      2 个进程    │
  │  24h 平均耗时  43 s/篇     │
  │  今日处理量    31 篇       │
  └────────────────────────────┘
```

## 5. Evidence Workspace Flow (from Task Board)

Not an independent tab. Entered via "查看工作台" on task board.

### 5.1 Layout & Core Interaction

```
← 返回看板    PMID 38000001 · Zhang et al. 2024 · MLH1      [导出] [完成复核]

┌──────────────────────────────┬──────────────────────────────┐
│  MD Document View (55%)      │  Evidence Cards (45%)        │
│                              │                              │
│  react-markdown rendering    │  Card list with:             │
│  with data-anchor-id on <p>  │  - Evidence type             │
│                              │  - Editable fields            │
│  Click card →                │  - Source snippet             │
│  scrollIntoView to anchor    │  - Confirm/edit buttons       │
│  Breathing-light highlight   │                              │
│  (1.5s fade in/out)          │  Click card → highlight MD   │
└──────────────────────────────┴──────────────────────────────┘
```

### 5.2 Keyboard Shortcuts

```
J / K       → Navigate cards up/down → auto-highlight source paragraph
E           → Open edit dialog for current card
Enter       → Confirm current card (mark reviewed)
Esc         → Close dialog/drawer
Ctrl+Z      → Undo last modification

First entry → show dismissible shortcut reference card (bottom-right)
```

### 5.3 Edit Flow

```
User presses E (or clicks [编辑] on card)
  │
  ▼
Modal dialog opens:
  ├── Dynamic form based on evidence dimension
  │     ├── HPO field → Command (cmdk) with /api/v1/hpo/search?q=
  │     ├── ACMG rule → Select dropdown
  │     └── Free text → Textarea
  ├── Save → POST /api/v1/evidence/:id (delta recorded silently)
  └── Cancel → close, no changes
```

### 5.4 Traceability Drawer

```
Click [溯源 →] on evidence row (in workspace or knowledge base)
  │
  ▼
Slide-out drawer (right side):
  ├── Literature metadata header
  ├── Original Markdown paragraph
  │     └── Source sentence highlighted with background color
  └── "在工作台中完整审阅" link → full workspace
```

### 5.5 Complete Review

```
User presses "完成复核" button
  │
  ▼
All confirmed cards marked as reviewed
  │
  ▼
Task status: "待复核" → "已完成"
  │
  ▼
Back to task board (filter/scroll preserved)
```

## 6. Tab 3: Knowledge Base Query Flow

### 6.1 Search

```
User opens Knowledge Base tab
  │
  ├── Exact search (default):
  │     Input HGVS / gene / PMID → GET /api/v1/kb/search?q=...
  │     Autocomplete suggestions from known variants
  │
  ├── AI Query mode (toggle):
  │     Input NL description → POST /api/v1/kb/nl-to-sql
  │       → Backend calls Claude API for Text-to-SQL
  │       → Returns SQL string + result set
  │       → User reviews SQL in <code> block (transparency)
  │       → Results rendered in evidence matrix
  │
  └── Advanced filters (collapsible):
        Evidence dimension dropdown
        Year range [2020]–[2024]
        ACMG rule multi-select
        Gene name input
        Data source: machine / expert / all
        → GET /api/v1/kb/search?dimension=...&year_min=...&year_max=...
```

### 6.2 Variant Detail Page

```
Search result clicked → navigate to /knowledge-base/variant/[variantId]
  │
  ▼
GET /api/v1/kb/variant/:id
  │
  ▼
Top: Metadata Dashboard (fixed)
  NM_000251.3:c.942+3A>T (MLH1)  ClinVar: 致病性  ·  gnomAD: 0.00003
  转录本: NM_000251.3 | 蛋白变化: p.Gln315Lys | 收录文献: 7 篇 | 证据条目: 24 条
  │
  ▼
Body: Evidence Matrix (Accordion groups)
  ▼ 功能与生化实验证据 (8 条)
    ┌──────────────────────────────────────────────────────────┐
    │ 2024  Luciferase 活性↓42%  [功能缺失][PS3]  PMID 38xxx  │
    │       [专家校正]  [溯源 →]                                │
    │ 2023  RNA 拼接异常       [异常拼接][PS3]  PMID 37xxx     │
    │       [机器提取]  [溯源 →]                                │
    └──────────────────────────────────────────────────────────┘
  ▶ 人群频率证据 (3 条)
  ▶ 临床表型与家系证据 (9 条)
  ▶ 计算预测证据 (4 条)
  │
  ▼
Interactions:
  ├── Click [溯源 →] → traceability drawer (same as workspace)
  ├── Check rows → "对比" button → side-by-side comparison modal
  │     ┌──────────────────┬──────────────────┐
  │     │ PMID 38000001    │ PMID 36100099    │
  │     │ Luciferase assay │ MMR 活性检测      │
  │     │ 活性 ↓42%        │ 活性完全缺失      │
  │     │ 结论: 功能缺失    │ 结论: 功能缺失    │
  │     └──────────────────┴──────────────────┘
  ├── Export CSV → GET /api/v1/kb/variant/:id/export?format=csv
  └── Generate ACMG draft → POST /api/v1/kb/variant/:id/acmg-draft
        → Opens new AI Assistant session with draft
        → Draft disclaimer: "此文本由 AI 根据已收录证据自动生成，请专家完整审核后使用"
        → Expert modifies in conversation → exports as PDF
```

## 7. Tab 4: Settings Flow

```
User opens Settings tab (admin only)
  │
  ├── Vocabulary Manager:
  │     GET /api/v1/settings/vocabularies
  │     ┌──────────────────────────────┐
  │     │ HPO       v2024-01-16  [更新] │
  │     │ OMIM      2024.01      [更新] │
  │     │ ClinVar   2024-01      [更新] │
  │     │ gnomAD    v4.0.0       [更新] │
  │     └──────────────────────────────┘
  │     Click [更新] → POST /api/v1/settings/vocabularies/:name/check-update
  │
  ├── Template Editor:
  │     GET /api/v1/settings/templates
  │     Cards per evidence dimension showing prompt summary + last modified
  │     Edit → modal with full prompt text
  │     Save → PUT /api/v1/settings/templates/:id
  │     "新增自定义维度" → POST /api/v1/settings/templates
  │
  └── Config Panel:
        MinerU: OCR toggle, table mode, max pages, timeout
        Database: SQLite / PostgreSQL, path, test connection
        → PUT /api/v1/settings/config
```

## 8. Runtime Architecture Flow (Backend)

```
User Action (chat / task board / knowledge base / settings)
  │
  ▼
FastAPI /api/v1/* endpoint
  │
  ├── POST /api/v1/chat/stream          → SSE stream: parse progress + evidence cards
  ├── GET/POST /api/v1/tasks/*          → Task CRUD + batch operations
  ├── GET /api/v1/tasks/:id/delta       → Delta audit log
  ├── GET /api/v1/kb/search             → Knowledge base search
  ├── POST /api/v1/kb/nl-to-sql         → Natural language → SQL
  ├── GET /api/v1/kb/variant/:id        → Variant detail + evidence matrix
  ├── GET /api/v1/hpo/search?q=         → HPO autocomplete
  └── GET/PUT /api/v1/settings/*        → Vocabulary, template, config
  │
  ▼
Orchestrator (src/agents/)
  │  Workflow topology, GraphState, routing
  │
  ├──► Feature: acquisition/upload/parsing
  ├──► Feature: native extraction → translation → translated extraction → fusion
  ├──► Feature: entity standardization → evidence matrix
  └──► Feature: review, feedback, export, delta audit
          │
          ▼
Shared infrastructure: config, DAO, Rust I/O, telemetry, cache
```

## 9. Communication Architecture

```
Frontend                          Backend
────────                          ───────
AI Assistant (useChat)  ──SSE──►  POST /api/v1/chat/stream
                                ◄── SSE events: progress, cards, complete, error

Task Board              ──REST─►  GET/POST/PATCH/DELETE /api/v1/tasks/*
                                ◄── JSON responses

Knowledge Base          ──REST─►  GET /api/v1/kb/*
                                ◄── JSON responses

HPO Autocomplete        ──REST─►  GET /api/v1/hpo/search?q=
                                ◄── JSON: [{code, term}]

Delta Audit             ──REST─►  GET /api/v1/tasks/:id/delta
                                ◄── JSON: [{timestamp, field, old, new}]

Settings                ──REST─►  GET/PUT /api/v1/settings/*
                                ◄── JSON responses
```

---

*Document version v2.0 · 2026-05-25 · Complete restructure for tab-based navigation and chat-driven extraction*
