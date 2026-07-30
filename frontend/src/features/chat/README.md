# Chat 对话功能

> 基于 SSE 流式传输的 AI 对话系统，支持 ACMG 证据上下文问答

## 概述

Chat 模块实现了与 Lingua Seeker 后端 AI 代理的实时对话功能。支持独立对话和绑定到处理运行（processing run）的上下文对话。使用 Server-Sent Events（SSE）实现流式回复，支持 Markdown 渲染、意图识别、操作确认，以及在聊天内上传 PDF 并提交证据提取任务。

## 文件结构

```
chat/
├── index.ts                          # 模块导出
├── chat.css                          # 对话界面样式
├── components/
│   ├── ChatView.tsx                  # 对话主视图（消息列表 + 输入框）
│   ├── SingleSessionChat.tsx         # 单会话对话包装器
│   ├── WelcomeBlock.tsx              # 欢迎界面/空状态
│   ├── ChatActionBubble.tsx          # 操作确认气泡（流水线启动等）
│   ├── ChatGraphResultCard.tsx       # 知识图谱问答内联结果卡（回答 + 子图）
│   ├── ThinkingIndicator.tsx         # AI 思考中指示器
│   ├── chatConfig.tsx                # 对话配置（操作意图 → 提示词映射）
│   ├── useBubbleItems.tsx            # 消息气泡列表构建 hook
│   ├── useChatProvider.ts            # 聊天 Provider 管理 hook
│   ├── useSessionConversations.tsx   # 会话消息历史管理 hook
│   ├── useSessionUIState.ts          # 会话 UI 状态 hook
│   ├── usePipelineActions.ts         # 流水线操作处理 hook
│   └── forms/                        # 对话内表单组件（确认卡、上传卡、状态卡）
├── hooks/
│   └── useChatSessions.ts           # 会话列表管理 hook
├── providers/
│   └── acmgChatProvider.ts          # 自定义 SSE 聊天 Provider
├── services/
│   └── chat.ts                      # API 服务层
├── types/
│   ├── chat.ts                      # 会话/消息类型定义
│   └── actions.ts                   # 操作意图类型定义
├── utils/
│   ├── markdown.tsx                 # 轻量 Markdown 渲染器
│   ├── localSessions.ts            # 本地会话持久化（localStorage）
│   ├── messageHistory.ts           # 消息历史转换工具
│   ├── messageRequests.ts          # 消息请求体构建
│   ├── messageStore.ts             # SDK 消息缓存管理
│   └── sse.ts                      # SSE 事件解析与处理
└── README.md
```

## 关键组件

### `ChatView`

对话主视图，集成 `@ant-design/x` 聊天组件。

- 消息列表展示（用户/助手气泡）
- 流式 AI 回复（SSE）
- 操作意图处理（确认流水线、搜索证据等）
- 输入框 PDF 上传按钮与 paste-file handler
- 本地 PDF 上传任务卡（文件 + gene/disease/variant 目标）
- Markdown 渲染（支持加粗、代码块、列表、数学公式）

### `AcmgChatProvider`

自定义 `AbstractChatProvider` 实现，绑定后端 SSE 流。

- **SSE 事件格式**: `text`（文本块）、`action`（操作意图）、`done`（完成）、`keepalive`（心跳）、`error`（错误）
- **后端意图检测**: question → LLM 回复、correction → 确认、note → 无回复

### `ChatMarkdown`

轻量级、无依赖的 Markdown 渲染器，支持 `**bold**`、`*italic*`、`` `code` ``、代码块、列表。不使用 `dangerouslySetInnerHTML`，流式安全。

### `ChatUploadTaskCard`

对话内 PDF 上传任务卡，位于 `components/forms/ChatUploadTaskCard.tsx`。

- 接收 `PipelineSummarySlots`，预填 `gene_symbol`、`disease_name`、`variant_hgvs_p`。
- 使用 Antd `Upload.Dragger` 选择单个 PDF；非 PDF 文件会被拒绝。
- 允许用户在提交前编辑提取目标。
- 提交时把 `slots` 和浏览器 `File` 交给 `usePipelineActions.handleLocalUploadSubmit()`。

## Hooks

### `useChatSessions(processingRunId?)`

管理会话列表。

- 独立模式：使用 localStorage 持久化（最多 20 个会话）
- 绑定模式：从后端获取特定运行的会话列表
- **返回**: `{ sessions, createSession, removeSession, isLoading }`

### `useSessionUIState(activeConversationKey)`

管理每个会话的临时 UI 状态。

- `activeForm`：当前对话内表单，包含 `confirm-pipeline` 与 `upload-pdf`。
- `activeFormSlots`：后端 action slots 或前端上传入口预置 slots。
- `activeUploadFile`：当前会话内待提交的浏览器 `File`，不会持久化。
- `openUploadFormForSession()`：输入框文件上传入口在无活动会话时创建会话后打开上传卡；欢迎快捷按钮不调用它，统一由交互智能体智能路由。

### `usePipelineActions(...)`

处理流水线相关动作。

- 在线任务：`confirm-pipeline` 确认后组装 `PipelineRunRequest` 并调用 `startPipelineRun()`。
- 本地 PDF：`confirm-pipeline` 的 `source_type="local"` 分支打开聊天内上传卡，不跳转页面。
- 上传提交：`readFileAsBase64()` 读取浏览器 `File`，调用 `/pipeline/run`，然后展示 `PipelineStatusCard`。

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/chat/sessions` | 创建会话 |
| GET | `/chat/sessions/{runId}` | 列出会话 |
| GET | `/chat/session-details/{id}` | 获取单个会话与 ChatLLM 生成标题 |
| GET | `/chat/sessions/{id}/messages` | 获取消息历史 |
| POST | `/chat/sessions/{id}/messages` | 发送用户消息 |
| GET | `/chat/sessions/{id}/stream` | SSE 流式回复 |

## 操作意图（ChatActionIntent）

后端 AI 代理可发出的操作信号：
- `confirm-pipeline` — 确认启动流水线
- `upload-pdf` — 兼容旧消息；新流程作为前端内部上传表单状态使用，后端不应再主动发出
- `search-evidence` — 搜索证据
- `classify-variant` — 变异分类
- `interpret-evidence` — 解读证据
- `review-changes` — 审阅变更
- `check-pipeline-status` — 检查流水线状态
- `graph-qa` — 知识图谱问答（**只读**，到达即自动分发）。前端调用 `queryGraphRag()`，
  在对话内联渲染有据回答 + 子图（`ChatGraphResultCard`），并提供「在图谱中查看」深链
  跳转到 `/graphrag`。此意图不走确认门，也不渲染点击式操作气泡。

## 上传任务数据流

```text
用户点击输入框上传按钮或粘贴 PDF
  -> ChatView.openUploadFormForSession()
  -> useBubbleItems 渲染 ChatUploadTaskCard
  -> 用户选择 PDF 并确认目标字段
  -> usePipelineActions.handleLocalUploadSubmit()
  -> readFileAsBase64(file)
  -> startPipelineRun({ source_type: "local", content_base64, filename, target })
  -> PipelineStatusCard 轮询并显示任务状态

WelcomeBlock 快捷按钮
  -> 发送预置自然语言消息
  -> 后端交互智能体收集槽位并要求最终确认
  -> confirm-pipeline action
  -> source_type="local" 时打开 ChatUploadTaskCard
```

## 验证

```bash
cd frontend
bun run test tests/features/chat/WelcomeBlock.test.tsx tests/features/chat/ChatUploadTaskCard.test.tsx
bun run type-check
bun run lint
bun run build
```
