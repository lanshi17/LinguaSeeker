# Chat 对话功能

> 基于 SSE 流式传输的 AI 对话系统，支持 ACMG 证据上下文问答

## 概述

Chat 模块实现了与 Lingua Seeker 后端 AI 代理的实时对话功能。支持独立对话和绑定到处理运行（processing run）的上下文对话。使用 Server-Sent Events（SSE）实现流式回复，支持 Markdown 渲染、意图识别和操作确认。

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
│   ├── ThinkingIndicator.tsx         # AI 思考中指示器
│   ├── chatConfig.tsx                # 对话配置（操作意图 → 提示词映射）
│   ├── useBubbleItems.tsx            # 消息气泡列表构建 hook
│   ├── useChatProvider.ts            # 聊天 Provider 管理 hook
│   ├── useSessionConversations.tsx   # 会话消息历史管理 hook
│   ├── useSessionUIState.ts          # 会话 UI 状态 hook
│   ├── usePipelineActions.ts         # 流水线操作处理 hook
│   └── forms/                        # 对话内表单组件
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
- Markdown 渲染（支持加粗、代码块、列表、数学公式）

### `AcmgChatProvider`

自定义 `AbstractChatProvider` 实现，绑定后端 SSE 流。

- **SSE 事件格式**: `text`（文本块）、`action`（操作意图）、`done`（完成）、`keepalive`（心跳）、`error`（错误）
- **后端意图检测**: question → LLM 回复、correction → 确认、note → 无回复

### `ChatMarkdown`

轻量级、无依赖的 Markdown 渲染器，支持 `**bold**`、`*italic*`、`` `code` ``、代码块、列表。不使用 `dangerouslySetInnerHTML`，流式安全。

## Hooks

### `useChatSessions(processingRunId?)`

管理会话列表。

- 独立模式：使用 localStorage 持久化（最多 20 个会话）
- 绑定模式：从后端获取特定运行的会话列表
- **返回**: `{ sessions, createSession, removeSession, isLoading }`

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/chat/sessions` | 创建会话 |
| GET | `/chat/sessions/{runId}` | 列出会话 |
| GET | `/chat/sessions/{id}/messages` | 获取消息历史 |
| POST | `/chat/sessions/{id}/messages` | 发送用户消息 |
| GET | `/chat/sessions/{id}/stream` | SSE 流式回复 |

## 操作意图（ChatActionIntent）

后端 AI 代理可发出的操作信号：
- `confirm-pipeline` — 确认启动流水线
- `search-evidence` — 搜索证据
- `classify-variant` — 变异分类
- `interpret-evidence` — 解读证据
- `review-changes` — 审阅变更
- `check-pipeline-status` — 检查流水线状态
