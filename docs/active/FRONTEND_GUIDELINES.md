# FRONTEND_GUIDELINES — ACMG Lingua Frontend

## 1. Tech Stack

| Concern | Choice | Notes |
|---|---|---|
| Framework | Next.js 15 App Router | File-based routing, layouts, SSR, tab-based layout group |
| UI Library | React 18 | Concurrent features |
| Language | TypeScript 5.5+ | Strict mode |
| Styling | Tailwind CSS 3.4 | Utility-first, no CSS-in-JS |
| UI Components | shadcn/ui (Radix UI) | Drawer, Dialog, Accordion, Command, Tabs, Badge, Spinner |
| Chat/Streaming | Vercel AI SDK 4.x | `useChat` hook, SSE streaming, `streamUI` for inline evidence cards |
| Markdown Render | react-markdown + remark-gfm | Workspace MD view with custom `data-anchor-id` paragraph components |
| Syntax Highlight | shiki 1.x | SQL/ddl/dml 代码块语法高亮，单例模式，github-dark 主题 |
| Client State | Zustand 4.5 | `chatStore`, `workspaceStore`, `taskBoardStore` |
| Server State | React Query 5.50 | Caching, invalidation |
| HTTP | Axios 1.7 | Calls `/api/v1/*` through Next.js proxy |
| Linting | ESLint 8.57 + Next config | Google TypeScript Style |
| Type Check | TypeScript compiler | Current-stage frontend verification |

FastAPI is authoritative for authentication and API behavior. Next.js proxies requests and renders UI; it does not sign or verify JWTs. In open-source deployment, all tabs and data are visible to all visitors — no user isolation. Transparency is maintained via delta audit logs.

## 2. Product UX Principles

### 2.1 Core Positioning

ACMG Lingua is an "evidence porter" — absolutely loyal to source data. Every piece of extracted information must be 100% traceable to its original location in the literature.

### 2.2 Design Principles

- **Minimal**: Every screen element must justify its existence. No decorative chrome.
- **Transparent**: Every piece of data must be traceable to its source. No black-box summaries that hide extraction provenance.
- **Restrained**: The system collects, structures, and presents — it does not interpret or diagnose.
- **Conversation-driven**: Literature processing is driven through natural conversation in the AI Assistant tab.
- **Tab-organized**: Four fixed tabs provide clear, single-responsibility workspaces. No nested menus or hidden pages.
- **Open by default**: No user isolation. Transparency replaces permission systems — all actions recorded in audit logs.

### 2.3 Evidence-First Framing

- Current UI presents extracted and standardized evidence, not final autonomous medical classification.
- Reports and result pages must describe outputs as evidence summaries and extraction results.
- Low confidence, missing traceability, ambiguous standardization, and extraction disagreement must be visible.
- Biomedical strings (HGVS, rsIDs, transcript IDs, gene symbols) use monospace formatting.

### 2.4 Bi-Directional Traceability

- Every evidence item shown in the UI must link to an original source span.
- Clicking/tapping an evidence item must scroll to and highlight the source text.
- If a result lacks required anchors/bbox-backed spans, the UI displays it as invalid/incomplete.

## 3. Navigation Structure

```
┌─────────────────────────────────────────────────────────────────┐
│  ACMG-Lingua   [AI 助手]  [任务看板]  [知识库查询]  [设置]       │
└─────────────────────────────────────────────────────────────────┘
```

Global topbar fixed. Four tabs with clear, single-responsibility:

| Tab | Route | Core Responsibility | Primary User Actions |
|---|---|---|---|
| AI Assistant | `/(dashboard)/assistant` | Upload literature, trigger extraction, complete evidence forms | Chat with system, drag-drop PDF, input PMID, confirm and correct evidence inline |
| Task Board | `/(dashboard)/task-board` | View all tasks' full lifecycle | Monitor progress, batch operations, enter workspace |
| Knowledge Base | `/(dashboard)/knowledge-base` | Search structured evidence assets | Search variants, trace sources, export reports |
| Settings | `/(dashboard)/settings` | System parameters, vocabulary versions, extraction templates | Admin configuration |

## 4. Directory Structure

```
frontend/
├── app/
│   ├── api/                         # Next.js API routes (proxy, auth callbacks)
│   ├── layout.tsx                   # Root layout with global topbar tabs
│   ├── page.tsx                     # Redirect to AI Assistant
│   └── (dashboard)/
│       ├── layout.tsx               # Dashboard shell with 4 tabs
│       ├── assistant/               # Tab 1: AI Assistant (chat-driven)
│       │   └── page.tsx
│       ├── task-board/              # Tab 2: Task Board
│       │   ├── page.tsx
│       │   └── workspace/
│       │       └── [taskId]/page.tsx  # Evidence Workspace (from task board)
│       ├── knowledge-base/          # Tab 3: Knowledge Base Query
│       │   ├── page.tsx
│       │   └── variant/
│       │       └── [variantId]/page.tsx  # Variant detail page
│       └── settings/                # Tab 4: Settings
│           └── page.tsx
├── components/
│   ├── ui/                          # shadcn/ui primitives
│   ├── layout/
│   │   ├── topbar.tsx               # Global fixed topbar with 4 tabs
│   │   └── dashboard-shell.tsx
│   ├── assistant/                   # AI Assistant feature slice
│   │   ├── chat-panel.tsx           # Main chat area with message bubbles
│   │   ├── chat-input.tsx           # Drag-drop upload + PMID input + send
│   │   ├── session-sidebar.tsx      # Collapsible history session list
│   │   ├── evidence-card.tsx        # Inline evidence form card (editable)
│   │   ├── system-message.tsx       # SSE typewriter system message bubble
│   │   └── batch-mode-toggle.tsx
│   ├── task-board/                  # Task Board feature slice
│   │   ├── task-list.tsx            # Task row cards with status colors
│   │   ├── status-filter-bar.tsx    # Horizontal status tabs with counts
│   │   ├── batch-action-bar.tsx     # Floating multi-select action bar
│   │   ├── resource-panel.tsx       # Collapsible resource monitoring
│   │   └── delta-audit-panel.tsx    # Slide-out delta audit log
│   ├── workspace/                   # Evidence Workspace feature slice
│   │   ├── md-document-view.tsx     # react-markdown rendered document (left pane)
│   │   ├── evidence-card-list.tsx   # Evidence cards (right pane)
│   │   ├── traceability-drawer.tsx  # Source paragraph slide-out drawer
│   │   ├── edit-dialog.tsx          # Modal edit form for evidence card
│   │   └── shortcut-hint.tsx        # Keyboard shortcut reference card
│   ├── knowledge-base/              # Knowledge Base feature slice
│   │   ├── search-bar.tsx           # Multi-mode search (exact / AI / filters)
│   │   ├── evidence-matrix.tsx      # Accordion-grouped evidence matrix
│   │   ├── variant-metadata.tsx     # Variant metadata dashboard
│   │   ├── comparison-view.tsx      # Side-by-side evidence comparison
│   │   └── export-menu.tsx          # CSV / ACMG draft generation
│   └── settings/                    # Settings feature slice
│       ├── vocabulary-manager.tsx   # Ontology version cards
│       ├── template-editor.tsx      # Extraction prompt template cards
│       └── config-panel.tsx         # MinerU / DB connection config
├── lib/
│   ├── api/
│   │   ├── client.ts                # Axios instance
│   │   ├── tasks.ts                 # Task CRUD + batch ops
│   │   ├── chat.ts                  # Chat session + SSE stream
│   │   ├── knowledge-base.ts        # Search, variant detail, NL-to-SQL
│   │   ├── hpo.ts                   # HPO autocomplete search
│   │   ├── delta.ts                 # Delta audit log
│   │   └── settings.ts              # Ontology versions, config
│   ├── hooks/
│   │   ├── use-chat.ts              # Vercel AI SDK useChat wrapper
│   │   ├── use-evidence-cards.ts    # Card state management
│   │   ├── use-task-board.ts        # Task list + filters + selection
│   │   ├── use-workspace.ts         # Workspace state + keyboard shortcuts
│   │   └── use-knowledge-base.ts    # Search + variant detail
│   ├── types/
│   │   ├── chat.ts                  # Message, EvidenceCard, Session
│   │   ├── task.ts                  # Task, TaskStatus, BatchOp
│   │   ├── evidence.ts              # EvidenceItem, EvidenceMatrix, EvidenceDimension
│   │   ├── variant.ts               # Variant, MetadataDashboard
│   │   ├── delta.ts                 # DeltaEntry, AuditLog
│   │   └── api.ts                   # Shared API response wrappers
│   └── utils/
│       ├── format.ts                # HGVS, date, number formatters
│       └── keyboard.ts              # Workspace keyboard shortcut manager
├── stores/
│   ├── chat-store.ts                # Messages, current session, editing card ID
│   ├── workspace-store.ts           # Highlight anchor, reviewed card IDs, scroll position
│   └── task-board-store.ts          # Status filter, search query, selected task IDs
├── styles/
│   └── globals.css                  # Tailwind + breathing-light animation
├── public/
├── tests/
├── next.config.ts
├── package.json
└── tsconfig.json
```

### 4.1 Component Architecture (Orchestrated Vertical Slices)

Frontend modules mirror Orchestrated Vertical Slice Architecture at UI scale:

```
app/<tab>/page.tsx            # Page-level orchestration and data composition only
components/<feature>/         # Vertical UI feature slices
components/ui/                # Shared primitives (no ACMG domain concepts)
lib/api/                      # Backend API providers
lib/hooks/                    # Feature/provider hooks
lib/types/                    # Cross-feature contracts
stores/                       # Global UI/runtime state only
```

Rules:
- `api`/hook layer fetches or mutates backend data.
- Component views render state and emit typed events.
- Shared UI primitives stay generic — no ACMG evidence concepts.
- Page files wire slices together and pass state; they do not contain business rules.

## 5. Tab 1: AI Assistant (Chat-Driven Flow)

The system's main entry point. Replaces traditional forms with conversation — "upload → parse → extract → correct → ingest" completed within one chat window, zero page navigation.

### 5.1 Layout

```
┌──────────────┬──────────────────────────────────────────────────┐
│              │                                                  │
│   History    │                   Main Chat Area                 │
│   Sessions   │                                                  │
│  (collapsible│   [Message Bubble Stream]                        │
│   sidebar)   │                                                  │
│              │                                                  │
│  • PMID xxx  │                                                  │
│  • Zhang 24  │                                                  │
│  • NF2 study │                                                  │
│              ├──────────────────────────────────────────────────┤
│              │  [Drag Upload / PMID Input / NL Instruction] [Send] │
└──────────────┴──────────────────────────────────────────────────┘
```

### 5.2 Key Components

#### Chat Panel (`assistant/chat-panel.tsx`)

- Uses Vercel AI SDK `useChat` hook.
- Renders message bubble stream: user messages, system SSE messages (typewriter effect), and evidence card messages.
- Message types: `text`, `system-progress`, `evidence-card`, `error`.

#### Chat Input (`assistant/chat-input.tsx`)

- Drag-and-drop PDF zone (expands on hover/drag).
- PMID/DOI text input with send button.
- Natural language instruction support ("extract evidence from PMID 38000001").
- Batch mode toggle: upload `.txt` file with multiple PMIDs for background processing.

#### Session Sidebar (`assistant/session-sidebar.tsx`)

- Collapsible left panel.
- Each session named by literature title or PMID.
- Click to restore full conversation context.
- Search by PMID, gene name, date.
- Batch task completion notification entries.

#### System Message (`assistant/system-message.tsx`)

- SSE streaming with typewriter effect.
- Renders parse progress steps with checkmarks:

```
正在解析 PDF...  ✓ 提取到 32 页 Markdown
识别文献：PMID 38000001 | Zhang et al. 2024 | Nature Genetics
启动证据提取 Agent...
  → 扫描功能实验段落
  → 发现 Luciferase assay 数据，结果为 ↓42% 活性
  → 映射 HPO 词表：HP:0001250（癫痫发作）
  → 扫描人群频率数据...gnomAD v4 查询中...
提取完成，请确认下方证据卡片。
```

- On MinerU parse failure: `解析失败：[具体原因]` — no complex recovery flow.

#### Evidence Card (`assistant/evidence-card.tsx`)

Rendered as a special message bubble type in chat stream. Structure:

```
┌─────────────────────────────────────────────────────────────┐
│  🧬 证据卡片 #1 / 3  ·  功能实验证据                         │
├─────────────────────────────────────────────────────────────┤
│  变异          NM_000251.3:c.942+3A>T              [只读]    │
│  基因          MLH1                                [只读]    │
│  证据维度      [功能实验 ▾]                                   │
│  实验类型      Luciferase reporter assay           [编辑]    │
│  定量结果      ↓42% 相对活性 (p < 0.001)           [编辑]    │
│  表型          [HP:0001250 癫痫发作 ×] [+ 添加]             │
│  结论标签      [功能缺失 ▾]                                   │
│  ACMG 规则     [PS3 ▾]                                       │
│                                                              │
│  原文支撑片段：                                               │
│  "Luciferase activity was reduced to 58%..."                │
│                                        [查看原文上下文 →]    │
├─────────────────────────────────────────────────────────────┤
│            [✓ 确认入库]          [↺ 重新提取此条]           │
└─────────────────────────────────────────────────────────────┘
```

Key interactions:
- **HPO autocomplete**: Phenotype field uses shadcn/ui `Command` (cmdk) with HPO database integration — real-time fuzzy search, returns `HP:XXXXXXX 术语名` options.
- **View source context**: Click expands original Markdown snippet (±3 paragraphs context) within the card, with highlighted source sentence. No page navigation.
- **Silent delta recording**: Any user modification to card fields is quietly written to delta audit log in background — no popup, preserving flow.

### 5.3 Three-Round Standard Flow

1. **Round 1 — Ingestion & Parse Feedback**: User drags PDF or inputs PMID. System SSE-streams parse progress as system message. On completion, renders evidence cards.
2. **Round 2 — Inline Evidence Cards**: Cards appear in chat as structured editable forms. All fields inline-editable.
3. **Round 3 — Natural Language Correction**: User types corrections like "第一张卡片的表型应该是 HP:0001250 癫痫发作". System updates card fields and re-renders. All corrections stay in conversation — no separate edit dialogs.

### 5.4 Batch Mode

- Toggle switch near chat input.
- User uploads `.txt` file with multiple PMIDs.
- System silently batch-processes all literature.
- Results go to Task Board "pending review" queue.
- Notification entry appears in session sidebar when complete.

### 5.5 Session Persistence

- Every history session stores complete message history + associated task IDs.
- User can return to any literature's extraction conversation anytime.
- Sidebar supports search by PMID, gene name, date.

## 6. Tab 2: Task Board

Global task center. Open-source: no user isolation — all share the same task list. Transparency through audit logs, not permissions.

### 6.1 Top Filter & Action Bar

```
[全部 (142)] [解析中 (3)] [提取中 (7)] [待复核 (28)] [已完成 (98)] [失败 (6)]
                                                    [🔍 Search]  [Time Range ▾]
```

Horizontal status tabs with counts. Right: search box for PMID, gene, title fuzzy search. Time range filter.

### 6.2 Task List (`task-board/task-list.tsx`)

Each task as horizontal card row, restrained information density:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ ○ [待复核]  PMID 38000001  Zhang et al. 2024 · MLH1 c.942+3A>T             │
│             已提取 3 条证据    2 小时前                  [查看工作台] [···] │
├─────────────────────────────────────────────────────────────────────────────┤
│ ● [提取中]  PMID 37500022  Li et al. 2023 · BRCA2                          │
│             正在映射词表...  ████████░░ 80%              [—]          [···] │
├─────────────────────────────────────────────────────────────────────────────┤
│ ✗ [失败]    PMID 36100099  Chen et al. 2022                                 │
│             MinerU 解析失败：扫描版 PDF 无法提取文本      [重试]       [···] │
└─────────────────────────────────────────────────────────────────────────────┘
```

Status color coding: Blue (parsing/extracting) · Orange (pending review) · Green (completed) · Red (failed).

### 6.3 Batch Operations (`task-board/batch-action-bar.tsx`)

Multi-select tasks → floating action bar appears at top:

```
已选 12 条  [批量重试]  [批量删除]  [批量导出 CSV]  [×取消]
```

### 6.4 Resource Monitoring (`task-board/resource-panel.tsx`)

Collapsible panel (top-right), valuable for self-hosted users:

```
┌────────────────────────────┐
│  系统状态               ▾  │
│  队列深度      7 个任务    │
│  当前处理      2 个进程    │
│  24h 平均耗时  43 s/篇     │
│  今日处理量    31 篇       │
└────────────────────────────┘
```

### 6.5 Delta Audit Log (`task-board/delta-audit-panel.tsx`)

Click `···` on task row → slide-out panel showing full modification history:

```
2024-01-15 14:32  表型字段  HP:0001251 → HP:0001250 (癫痫发作)
2024-01-15 14:35  ACMG规则  PS3 → PS3_moderate
2024-01-15 14:40  实验结论  confirmed  (确认入库)
```

Replaces user permission systems in open-source context — transparency mechanism showing what changed and when.

## 7. Evidence Workspace (From Task Board)

Not an independent navigation tab. Entered via "查看工作台" button from task board. Back button returns to task board preserving state.

### 7.1 Layout (Left/Right Split)

```
← 返回看板    PMID 38000001 · Zhang et al. 2024 · MLH1               [导出] [完成复核]

┌──────────────────────────────┬──────────────────────────────────────────┐
│  Markdown Document (55%)     │  Evidence Cards (45%)                    │
│                              │                                          │
│  ## Introduction             │  ┌──────────────────────────────────┐   │
│                              │  │ #1 功能实验证据         [编辑]   │   │
│  MLH1 是 DNA 错配修复...     │  │ 实体: HP:0001250 癫痫发作        │   │
│                              │  │ 原文: "Luciferase activity..."   │   │
│  ## Methods                  │  │ 规则: PS3                        │   │
│                              │  └──────────────────────────────────┘   │
│  ██████████████████████      │                                          │
│  (highlighted — breathing)   │  ┌──────────────────────────────────┐   │
│  ██████████████████████      │  │ #2 人群频率证据         [编辑]   │   │
│                              │  │ 实体: gnomAD AF=0.00003          │   │
│  ## Results                  │  │ 原文: "The variant was found..." │   │
│                              │  │ 规则: PM2                        │   │
│                              │  └──────────────────────────────────┘   │
└──────────────────────────────┴──────────────────────────────────────────┘
```

### 7.2 Key Components

#### MD Document View (`workspace/md-document-view.tsx`)

- Uses `react-markdown` + `remark-gfm`.
- Custom paragraph component with unique `data-anchor-id` attribute for each `<p>`.
- On card click → `scrollIntoView({ behavior: 'smooth' })` to target anchor.
- Breathing-light highlight: background color fades in/out over ~1.5s, then auto-clears.
- 60fps smooth scrolling.
- 自定义 `code` 组件委托给 `CodeBlock`（见下文），实现 SQL 代码块的语法高亮和复制功能。

#### Code Block 组件 (`components/ui/code-block.tsx`)

通用代码块渲染组件，作为 `react-markdown` 的 `code` 组件覆盖，同时支持独立使用。

**SQL 语言检测（`lib/utils/sql-language.ts`）：**

从 markdown 围栏代码块的 `className`（如 `language-sql`）提取语言标签，匹配以下集合时触发 SQL 渲染路径：

```
SQL_LANGUAGE_TAGS = { sql, ddl, dml, mysql, postgresql, plsql, tsql }
```

- `sql` / `ddl` / `dml`：主要匹配目标
- `mysql` / `postgresql` / `plsql` / `tsql`：常见 SQL 方言，向前兼容

**渲染逻辑：**

| 场景 | 渲染方式 |
|---|---|
| 语言标签匹配 SQL 集合 | Shiki 语法高亮 + 语言标签栏 + 中文复制按钮 |
| 其他语言或无语言标签 | 普通 `<pre><code>` 样式 |

**Shiki 集成：**

- 使用 `shiki` 1.x 的 `createHighlighter` 单例模式，仅加载 `sql` 语言和 `github-dark` 主题
- 异步初始化（WASM 加载），首次渲染显示纯文本，高亮就绪后切换
- 组件结构：

```
┌─────────────────────────────────────────┐
│  sql                          [复制]     │  ← 语言标签栏（深色背景）
├─────────────────────────────────────────┤
│  SELECT * FROM evidence                 │  ← Shiki 高亮代码
│  WHERE gene = 'BRCA1'                   │
│    AND year >= 2022                     │
└─────────────────────────────────────────┘
```

**组件接口：**

```typescript
// components/ui/code-block.tsx
interface CodeBlockProps {
  className?: string;    // react-markdown 传入 "language-xxx"
  children?: React.ReactNode;
}

// lib/utils/sql-language.ts
function isSqlLanguage(lang: string | undefined): boolean;
```

**共享机制：** 通过 `lib/utils/markdown-components.tsx` 的 `createMarkdownComponents()` 工厂函数，所有使用 `react-markdown` 的上下文（工作台文档视图、AI 助手消息、知识库查询结果）共享同一套代码块组件。

#### Evidence Card List (`workspace/evidence-card-list.tsx`)

- Vertical list of evidence cards on right side.
- Click card → highlight source paragraph in left MD view.
- Edit button → modal dialog (see below).
- Card states: unconfirmed, confirmed (checkmark), edited (pencil icon).
- "完成复核" button marks all confirmed cards as reviewed.

#### Edit Dialog (`workspace/edit-dialog.tsx`)

- Modal popup triggered by card "编辑" button.
- Dynamic form fields based on evidence type:
  - HPO field: `Command` component with fuzzy search.
  - ACMG rule: `Select` dropdown.
  - Free text: `Textarea`.
- Save → close modal, delta silently recorded, card re-renders.
- Cancel → close, no changes.

#### Traceability Drawer (`workspace/traceability-drawer.tsx`)

- Slide-out panel from right edge.
- Shows original Markdown paragraph with highlighted source sentence.
- Top: literature metadata (PMID, authors, year).
- Bottom: "在工作台中完整审阅" link to full workspace.

### 7.3 Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `J` / `K` | Navigate evidence cards up/down, auto-highlight corresponding source |
| `E` | Open current card's edit dialog |
| `Enter` | Confirm current card (mark as reviewed) |
| `Esc` | Close dialog/drawer |
| `Ctrl+Z` | Undo last modification |

First entry into workspace shows dismissible shortcut reference card (bottom-right).

### 7.4 State Management (`workspace-store.ts`)

```typescript
interface WorkspaceState {
  highlightAnchorId: string | null;      // Current highlighted paragraph
  reviewedCardIds: Set<string>;          // Confirmed card IDs
  scrollPosition: number;                // MD view scroll position
  isDirty: boolean;                      // Unsaved changes exist
  undoStack: DeltaEntry[];               // For Ctrl+Z
}
```

## 8. Tab 3: Knowledge Base Query

Data asset retrieval entry point. Designed for PC widescreen, high information density.

### 8.1 Search Bar (`knowledge-base/search-bar.tsx`)

Three query modes:

#### Exact Search (Default)

```
┌──────────────────────────────────────────────────────┐
│  🔍 输入变异位点或基因名...                            │
│     NM_000251.3:c.942+3A>T  /  MLH1  /  PMID 380... │
└──────────────────────────────────────────────────────┘
```

Supports HGVS notation, gene symbol, PMID. Real-time autocomplete for known variants.

#### AI Query Mode (Toggle)

```
┌──────────────────────────────────────────────────────────────┐
│  [AI 查询 ✓]  用自然语言描述你的检索需求...                    │
│  "找所有 2022 年后、关于 BRCA1 功能实验、结论为功能缺失的证据" │
└──────────────────────────────────────────────────────────────┘
  ↓ 生成 SQL（可展开审查）：
  SELECT * FROM evidence WHERE gene='BRCA1' AND year>=2022
    AND dimension='functional' AND conclusion='loss_of_function'
```

System uses Text-to-SQL (calls Claude API from backend). Generated SQL shown in `<code>` block for user review before execution. Full transparency.

**SQL 展示组件（`knowledge-base/sql-display.tsx`）：**

NL-to-SQL 结果使用 `SqlDisplay` 组件渲染，内部复用 `CodeBlock`：

```typescript
interface SqlDisplayProps {
  sql: string;       // 后端返回的 SQL 字符串
  title?: string;    // 可选标题，如 "生成的 SQL"
}
```

- 自动触发 Shiki SQL 语法高亮（通过 `className="language-sql"`）
- 右上角显示中文复制按钮（"复制" / "已复制"）
- 带可选标题栏的卡片式布局

**中文复制按钮设计（`components/ui/copy-button.tsx`）：**

- 默认状态显示 "复制"，点击后切换为 "已复制 ✓"，2 秒后恢复
- 使用 `navigator.clipboard.writeText()` API，降级方案为 `document.execCommand('copy')`
- 定位在代码块右上角（`absolute top-2 right-2`），半透明深色背景
- 无障碍：`aria-label="复制代码"`
- 所有 SQL 类代码块（ddl/dml/sql 及方言标签）均显示复制按钮

```
┌─────────────────────────────────────────────────┐
│  生成的 SQL                                      │  ← 可选标题
├─────────────────────────────────────────────────┤
│  sql                                [复制]       │  ← 语言标签 + 复制按钮
├─────────────────────────────────────────────────┤
│  SELECT * FROM evidence                          │  ← Shiki 高亮
│  WHERE gene = 'BRCA1'                            │
│    AND dimension = 'functional'                  │
│    AND conclusion = 'loss_of_function'           │
└─────────────────────────────────────────────────┘
```

#### Advanced Filters (Collapsible Panel)

```
证据维度   [全部 ▾]       发表年份  [2020] 至 [2024]
ACMG 规则  [PS / BS ...]  基因       [输入基因名]
数据来源   [机器提取 / 专家校正 / 全部]
```

### 8.2 Variant Detail Page (`knowledge-base/variant/[variantId]/page.tsx`)

#### Metadata Dashboard (`knowledge-base/variant-metadata.tsx`)

Fixed at top, key statistics:

```
NM_000251.3:c.942+3A>T  (MLH1)      ClinVar: 致病性  ·  gnomAD: 0.00003
转录本: NM_000251.3  |  蛋白变化: p.Gln315Lys  |  收录文献: 7 篇  |  证据条目: 24 条
```

#### Evidence Matrix (`knowledge-base/evidence-matrix.tsx`)

Outer grouping by ACMG/ClinGen evidence dimension (`Accordion`), inner rows flat (no AI summarization):

```
▼ 功能与生化实验证据  (8 条)
─────────────────────────────────────────────────────────────────────────────
  年份  核心证据描述                           标签         来源         质量
  2024  Luciferase 活性降至野生型 58%，        [功能缺失]   PMID 38xxx  [专家校正]
        p<0.001                                [PS3]        [溯源 →]
  2023  RNA 拼接分析显示外显子跳跃             [异常拼接]   PMID 37xxx  [机器提取]
                                               [PS3]        [溯源 →]
  2022  患者成纤维细胞 MMR 活性缺失           [功能缺失]   PMID 36xxx  [专家校正]
                                               [PS3]        [溯源 →]
─────────────────────────────────────────────────────────────────────────────
▶ 人群频率证据  (3 条)
▶ 临床表型与家系证据  (9 条)
▶ 计算预测证据  (4 条)
```

Quality labels: "机器提取" (gray) vs "专家校正" (blue) — readers judge credibility at a glance.

#### Comparison View (`knowledge-base/comparison-view.tsx`)

Check multiple evidence rows → "对比" button → side-by-side modal:

```
┌───────────────────────────────────┬───────────────────────────────────┐
│  PMID 38000001 (2024)             │  PMID 36100099 (2022)             │
│  Luciferase assay                 │  MMR 活性检测                     │
│  活性 ↓42%，p<0.001               │  活性完全缺失                     │
│  结论：功能缺失 [PS3]             │  结论：功能缺失 [PS3]             │
└───────────────────────────────────┴───────────────────────────────────┘
```

#### Traceability Drawer

Click `[溯源 →]` on any evidence row → right-side drawer with:
- Literature metadata header.
- Original Markdown paragraph with highlighted source sentence.
- "在工作台中完整审阅" link.

No page navigation required for cross-validation.

### 8.3 Export Menu (`knowledge-base/export-menu.tsx`)

Detail page top-right:

- **Export CSV**: All evidence as structured table, fields match matrix columns.
- **Generate ACMG Classification Draft**: Calls AI to draft ACMG/AMP five-tier classification based on collected evidence. Opens in new AI Assistant session. Draft header shows: "此文本由 AI 根据已收录证据自动生成，请专家完整审核后使用". Expert modifies in conversation, exports as PDF.

## 9. Tab 4: Settings

Restrained — only system admin configuration. Regular users need not visit.

### 9.1 Vocabulary Manager (`settings/vocabulary-manager.tsx`)

Card-based display of loaded ontology versions with update triggers:

```
HPO         v2024-01-16    [检查更新]
OMIM        2024.01        [检查更新]
ClinVar     2024-01        [检查更新]
gnomAD      v4.0.0         [检查更新]
```

### 9.2 Template Editor (`settings/template-editor.tsx`)

Cards per evidence dimension showing current extraction prompt config:
- Dimension name, prompt summary, last modified timestamp.
- Edit opens modal with full prompt text.
- "新增自定义维度" button for custom evidence types.

### 9.3 Config Panel (`settings/config-panel.tsx`)

MinerU parameters:
- OCR engine toggle (on/off).
- Table parsing mode (native / image recognition).
- Max pages, timeout.

Database connection:
```
模式        SQLite（本地单机）  /  PostgreSQL（生产部署）
文件路径    /data/acmg_lingua.db                [测试连接]
```

## 10. State Management

### 10.1 chatStore

```typescript
interface ChatState {
  sessions: ChatSession[];
  currentSessionId: string | null;
  messages: Message[];                  // Includes text, system-progress, evidence-card types
  editingCardId: string | null;         // Card currently being edited
  isStreaming: boolean;                 // SSE active
  batchMode: boolean;
}
```

### 10.2 workspaceStore

```typescript
interface WorkspaceState {
  highlightAnchorId: string | null;
  reviewedCardIds: Set<string>;
  scrollPosition: number;
  isDirty: boolean;
  undoStack: DeltaEntry[];
}
```

### 10.3 taskBoardStore

```typescript
interface TaskBoardState {
  statusFilter: TaskStatus | 'all';
  searchQuery: string;
  selectedTaskIds: Set<string>;
  timeRange: { start: Date; end: Date } | null;
}
```

## 11. API Client Organization

```
lib/api/
├── client.ts          # Axios instance, base URL, interceptors
├── tasks.ts           # GET /tasks, GET /tasks/:id, POST /tasks, PATCH /tasks/:id, batch ops
├── chat.ts            # POST /chat/stream (SSE), GET /chat/sessions, GET /chat/sessions/:id
├── knowledge-base.ts  # GET /kb/search, GET /kb/variant/:id, POST /kb/nl-to-sql
├── hpo.ts             # GET /hpo/search?q=<query>
├── delta.ts           # GET /tasks/:id/delta
└── settings.ts        # GET/PUT /settings/vocabularies, /settings/templates, /settings/config
```

## 12. Communication Protocol

### SSE for Chat & Processing Status

Replaces WebSocket. Lighter weight, perfect fit for Vercel AI SDK streaming:

```
POST /api/v1/chat/stream
  → SSE event stream:
    data: {"type": "progress", "step": "parsing", "message": "正在解析 PDF..."}
    data: {"type": "progress", "step": "parsing", "message": "✓ 提取到 32 页 Markdown"}
    data: {"type": "card", "card": {...evidenceCard}}
    data: {"type": "complete", "task_id": "xxx"}
    data: {"type": "error", "step": "parsing", "message": "MinerU 解析失败：扫描版 PDF"}
```

### REST for CRUD

Standard JSON REST for tasks, knowledge base, settings, delta audit.

---

*Document version v2.0 · 2026-05-25 · Complete restructure for tab-based UI, chat-driven flow, and open-source transparency model*
