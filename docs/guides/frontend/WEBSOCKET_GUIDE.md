# WebSocket 功能使用指南

## 概述

已添加 WebSocket 支持用于实时获取任务进度更新。

**WebSocket 端点**: `ws://localhost:8000/ws/task/{task_id}/progress`

## 新增文件

### 服务层
- `src/services/websocket.ts` - WebSocket 客户端类

### Hooks
- `src/hooks/useWebSocket.ts` - WebSocket React Hooks

### 类型定义
WebSocket 相关类型已添加到 `src/services/websocket.ts`:
- `WebSocketMessage` - WebSocket 消息格式
- `WebSocketStatus` - 连接状态
- `WebSocketOptions` - 配置选项

## 使用方法

### 1. 在组件中使用 Hook

```tsx
import { useTaskWebSocket } from './hooks/useWebSocket';

function MyComponent() {
  const { 
    isConnected, 
    progress, 
    currentStage,
    lastMessage 
  } = useTaskWebSocket('task-123', {
    enabled: true,
    onProgress: (progress, stage) => {
      console.log(`进度: ${progress}%, 阶段: ${stage}`);
    },
    onComplete: (data) => {
      console.log('任务完成:', data);
    },
    onError: (error) => {
      console.error('WebSocket 错误:', error);
    }
  });

  return (
    <div>
      {isConnected ? '已连接' : '未连接'}
      进度: {progress}%
    </div>
  );
}
```

### 2. 使用 WebSocket 监控任务（替代轮询）

```tsx
import { useWebSocketTaskPolling } from './hooks/useWebSocket';

function TaskMonitor() {
  const {
    isWatching,
    progress,
    currentStage,
    status,
    startWatching,
    stopWatching
  } = useWebSocketTaskPolling('task-123', 
    (data) => console.log('完成:', data),
    (error) => console.error('错误:', error)
  );

  return (
    <div>
      <button onClick={startWatching}>开始监控</button>
      <div>进度: {progress}%</div>
      <div>阶段: {currentStage}</div>
    </div>
  );
}
```

### 3. 直接使用 WebSocket 客户端

```tsx
import { TaskWebSocketClient } from './services/websocket';

const client = new TaskWebSocketClient('task-123', {
  onProgress: (progress, stage) => {
    console.log(`进度: ${progress}%`);
  },
  onComplete: (data) => {
    console.log('任务完成');
  },
  onError: (error) => {
    console.error('错误:', error);
  }
});

client.connect();

// 稍后断开
client.disconnect();
```

## TaskStatusPage 更新

任务状态页面现在支持 WebSocket 实时更新：

1. **自动连接**: 页面加载时自动尝试 WebSocket 连接
2. **实时进度**: 通过 WebSocket 接收实时进度更新
3. **降级机制**: WebSocket 失败时自动切换到轮询
4. **连接状态显示**: 显示当前连接状态（实时推送/轮询）

## 功能特性

### 自动重连
WebSocket 连接断开会自动重连（最多 5 次，间隔 2 秒）。

### 降级机制
如果 WebSocket 连接失败，自动切换到 HTTP 轮询。

### 消息类型
WebSocket 支持的消息类型：
- `progress` - 进度更新
- `status` - 状态变更
- `completed` - 任务完成
- `error` - 错误信息
- `connected` - 连接成功
- `disconnected` - 连接断开

## 后端要求

后端需要实现 WebSocket 端点：
```
WS /ws/task/{task_id}/progress
```

预期消息格式：
```json
{
  "type": "progress",
  "task_id": "task-123",
  "progress": 50,
  "stage": "PDF解析",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## 浏览器控制台调试

```javascript
// 查看 WebSocket 状态
proxyTest.runProxyTest()

// 检查连接
networkTest.fullNetworkDiagnostic()
```

## 故障排查

### WebSocket 连接失败
1. 检查后端是否支持 WebSocket
2. 检查防火墙设置
3. 查看浏览器控制台错误信息
4. 系统会自动降级到轮询模式

### 连接状态说明
- **● 实时推送已连接** - WebSocket 连接成功
- **○ 正在连接实时推送...** - 正在连接 WebSocket
- **○ 使用轮询模式** - WebSocket 失败，使用 HTTP 轮询
