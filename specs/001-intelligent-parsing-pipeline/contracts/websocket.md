# WebSocket Protocol: Real-Time Task Progress

**Feature**: Intelligent Parsing Pipeline System
**Date**: 2026-01-30
**Purpose**: Define WebSocket communication protocol for real-time parsing task progress updates

## Overview

The WebSocket protocol provides server-pushed progress updates for long-running document parsing tasks. Clients connect to a task-specific WebSocket endpoint and receive periodic updates without polling.

## Connection

### Endpoint

```
ws://localhost:8000/ws/task/{task_id}/progress
```

**Production**:
```
wss://api.acmg-system.example.com/ws/task/{task_id}/progress
```

### Authentication

Include JWT token as query parameter:
```
ws://localhost:8000/ws/task/{task_id}/progress?token={jwt_token}
```

### Connection Lifecycle

1. **Client Initiates**: Connect to WebSocket endpoint with valid `task_id`
2. **Server Validates**: Verify task exists and client has access
3. **Server Sends Initial State**: Immediate snapshot of current task status
4. **Server Pushes Updates**: Progress updates sent automatically (every 30s or on stage change)
5. **Task Completion**: Final message sent, connection remains open for 10s then closes
6. **Client Disconnection**: Client may disconnect anytime, buffered messages available on reconnect

## Message Types

### 1. Connection Acknowledged (Server → Client)

Sent immediately after successful WebSocket connection.

```json
{
  "type": "connection_ack",
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2026-01-30T14:23:45.123Z",
  "message": "Connected to task progress stream"
}
```

### 2. Initial Status (Server → Client)

Snapshot of current task state sent right after connection acknowledgment.

```json
{
  "type": "status",
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "PROCESSING",
  "current_stage": "LAYOUT",
  "progress_percentage": 25,
  "started_at": "2026-01-30T14:20:00.000Z",
  "estimated_completion": "2026-01-30T14:28:00.000Z",
  "message": "Sanitizing document layout structure",
  "timestamp": "2026-01-30T14:23:45.456Z"
}
```

### 3. Progress Update (Server → Client)

Periodic updates sent every 30 seconds or when stage transitions occur.

```json
{
  "type": "progress",
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "PROCESSING",
  "current_stage": "EVIDENCE",
  "progress_percentage": 75,
  "stage_details": {
    "evidence_items_extracted": 12,
    "current_acmg_code": "PM2",
    "documents_processed": 1
  },
  "estimated_completion": "2026-01-30T14:26:30.000Z",
  "message": "Extracting ACMG evidence codes",
  "timestamp": "2026-01-30T14:25:15.789Z"
}
```

### 4. Stage Transition (Server → Client)

Sent immediately when Agent workflow transitions between stages.

```json
{
  "type": "stage_transition",
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "from_stage": "TRANSLATION",
  "to_stage": "EVIDENCE",
  "progress_percentage": 60,
  "message": "Translation complete, starting evidence extraction",
  "timestamp": "2026-01-30T14:24:30.123Z"
}
```

### 5. Task Completed (Server → Client)

Sent when task reaches COMPLETED status.

```json
{
  "type": "completed",
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "COMPLETED",
  "progress_percentage": 100,
  "completed_at": "2026-01-30T14:26:45.000Z",
  "duration_seconds": 405,
  "results": {
    "document_id": "doc-uuid-1234",
    "evidence_count": 18,
    "high_confidence_count": 14,
    "needs_review_count": 4
  },
  "message": "Document parsing completed successfully",
  "timestamp": "2026-01-30T14:26:45.012Z"
}
```

### 6. Task Failed (Server → Client)

Sent when task reaches FAILED status.

```json
{
  "type": "failed",
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "FAILED",
  "current_stage": "DECOMPOSITION",
  "progress_percentage": 15,
  "failure_reason": "MinerU parsing timeout after 300 seconds",
  "retry_count": 2,
  "can_retry": true,
  "failed_at": "2026-01-30T14:25:00.000Z",
  "message": "Task failed during PDF decomposition",
  "timestamp": "2026-01-30T14:25:00.123Z"
}
```

### 7. Heartbeat (Server → Client)

Sent every 10 seconds to keep connection alive and detect disconnects.

```json
{
  "type": "heartbeat",
  "timestamp": "2026-01-30T14:23:55.000Z"
}
```

### 8. Ping (Client → Server)

Client may send ping to verify connection health.

```json
{
  "type": "ping",
  "timestamp": "2026-01-30T14:24:10.000Z"
}
```

**Server Response (Pong)**:
```json
{
  "type": "pong",
  "timestamp": "2026-01-30T14:24:10.050Z"
}
```

### 9. Reconnect Replay (Server → Client)

Sent after client reconnects to catch up on missed updates.

```json
{
  "type": "replay",
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "buffered_messages": [
    {
      "type": "progress",
      "progress_percentage": 40,
      "timestamp": "2026-01-30T14:23:00.000Z"
    },
    {
      "type": "stage_transition",
      "to_stage": "TRANSLATION",
      "timestamp": "2026-01-30T14:23:30.000Z"
    }
  ],
  "current_status": {
    "type": "status",
    "status": "PROCESSING",
    "current_stage": "TRANSLATION",
    "progress_percentage": 50,
    "timestamp": "2026-01-30T14:24:00.000Z"
  },
  "message": "Replayed 2 missed updates",
  "timestamp": "2026-01-30T14:24:15.000Z"
}
```

### 10. Error (Server → Client)

Sent when an error occurs in the WebSocket connection or task monitoring.

```json
{
  "type": "error",
  "error_code": "TASK_NOT_FOUND",
  "message": "Task with ID a1b2c3d4-e5f6-7890-abcd-ef1234567890 does not exist",
  "timestamp": "2026-01-30T14:23:45.000Z"
}
```

## Stage Progression

The `current_stage` field follows this sequence:

```
PENDING → INGESTION → DECOMPOSITION → LAYOUT → TRANSLATION → EVIDENCE → ARBITRATION → COMPLETED
```

Each stage has typical progress ranges:
- **INGESTION** (0-10%): Upload validation, MinIO storage
- **DECOMPOSITION** (10-30%): MinerU PDF parsing
- **LAYOUT** (30-45%): Markdown sanitization
- **TRANSLATION** (45-60%): Bilingual text generation
- **EVIDENCE** (60-85%): ACMG code extraction
- **ARBITRATION** (85-95%): Confidence scoring
- **COMPLETED** (100%): Final results ready

## Client Implementation Example (JavaScript)

### Connection with Reconnect Logic

```javascript
class TaskProgressClient {
  constructor(taskId, authToken) {
    this.taskId = taskId;
    this.authToken = authToken;
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000; // Start with 1s
    this.listeners = {};
  }

  connect() {
    const wsUrl = `ws://localhost:8000/ws/task/${this.taskId}/progress?token=${this.authToken}`;
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
      this.reconnectDelay = 1000;
    };

    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      this.handleMessage(message);
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    this.ws.onclose = () => {
      console.log('WebSocket closed');
      this.attemptReconnect();
    };
  }

  handleMessage(message) {
    // Emit to registered listeners
    if (this.listeners[message.type]) {
      this.listeners[message.type].forEach(callback => callback(message));
    }

    // Special handling for completion/failure
    if (message.type === 'completed' || message.type === 'failed') {
      setTimeout(() => this.disconnect(), 10000); // Keep open 10s for final messages
    }
  }

  attemptReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnect attempts reached');
      return;
    }

    this.reconnectAttempts++;
    console.log(`Reconnecting in ${this.reconnectDelay}ms (attempt ${this.reconnectAttempts})`);

    setTimeout(() => {
      this.connect();
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, 8000); // Exponential backoff, max 8s
    }, this.reconnectDelay);
  }

  on(eventType, callback) {
    if (!this.listeners[eventType]) {
      this.listeners[eventType] = [];
    }
    this.listeners[eventType].push(callback);
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  sendPing() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'ping', timestamp: new Date().toISOString() }));
    }
  }
}

// Usage
const client = new TaskProgressClient('task-uuid-1234', 'jwt-token-5678');

client.on('status', (message) => {
  console.log('Initial status:', message.current_stage, message.progress_percentage);
});

client.on('progress', (message) => {
  updateProgressBar(message.progress_percentage);
  updateStatusText(message.message);
});

client.on('stage_transition', (message) => {
  console.log(`Stage changed: ${message.from_stage} → ${message.to_stage}`);
});

client.on('completed', (message) => {
  console.log('Task completed!', message.results);
  showSuccessNotification(message.results);
});

client.on('failed', (message) => {
  console.error('Task failed:', message.failure_reason);
  if (message.can_retry) {
    showRetryOption();
  }
});

client.connect();

// Send periodic pings to keep connection alive
setInterval(() => client.sendPing(), 30000);
```

## Server-Side Implementation Notes

### Redis Pub/Sub Architecture

```python
# Celery worker publishes progress
redis_client.publish(
    f'task:{task_id}:progress',
    json.dumps({
        'type': 'progress',
        'task_id': task_id,
        'progress_percentage': 50,
        'current_stage': 'TRANSLATION',
        'timestamp': datetime.utcnow().isoformat()
    })
)

# FastAPI WebSocket handler subscribes
pubsub = redis_client.pubsub()
pubsub.subscribe(f'task:{task_id}:progress')

for message in pubsub.listen():
    if message['type'] == 'message':
        await websocket.send_text(message['data'])
```

### Message Buffering

Buffer last 10 progress messages in Redis with 1-hour TTL:

```python
redis_client.lpush(f'task:{task_id}:message_buffer', message_json)
redis_client.ltrim(f'task:{task_id}:message_buffer', 0, 9)  # Keep only last 10
redis_client.expire(f'task:{task_id}:message_buffer', 3600)  # 1 hour TTL
```

### Heartbeat Implementation

```python
async def heartbeat_loop(websocket, task_id):
    try:
        while True:
            await asyncio.sleep(10)
            await websocket.send_json({
                'type': 'heartbeat',
                'timestamp': datetime.utcnow().isoformat()
            })
    except WebSocketDisconnect:
        pass
```

## Error Codes

| Code | Description |
|------|-------------|
| `TASK_NOT_FOUND` | Task ID does not exist |
| `UNAUTHORIZED` | Invalid or missing authentication token |
| `TASK_EXPIRED` | Task completed more than 1 hour ago (no buffered messages) |
| `INTERNAL_ERROR` | Server-side error in WebSocket handler |

## Best Practices

### Client-Side

1. **Exponential Backoff**: Reconnect with exponential delays (1s, 2s, 4s, 8s max)
2. **Connection Timeout**: Set 30s timeout for initial connection
3. **Ping Interval**: Send ping every 30s to detect stale connections
4. **UI Updates**: Debounce progress updates to avoid excessive re-renders (max 1 update/second)
5. **Offline Handling**: Detect network offline, pause reconnect attempts, resume when online

### Server-Side

1. **Connection Limits**: Max 1000 concurrent WebSocket connections per server instance
2. **Task Cleanup**: Close WebSocket 10s after task completion/failure
3. **Message Buffering**: Keep last 10 messages for reconnect replay
4. **Heartbeat**: Send every 10s, close connection if client doesn't respond to 3 consecutive heartbeats
5. **Authentication**: Validate JWT on connection, reject if expired

## Testing

### Manual Testing

```bash
# Using websocat CLI tool
websocat "ws://localhost:8000/ws/task/a1b2c3d4-e5f6-7890-abcd-ef1234567890/progress?token=your-jwt-token"
```

### Automated Testing

```python
import pytest
from fastapi.testclient import TestClient

def test_websocket_progress_updates(client: TestClient, task_id: str):
    with client.websocket_connect(f"/ws/task/{task_id}/progress?token=test-token") as websocket:
        # Receive connection ack
        data = websocket.receive_json()
        assert data['type'] == 'connection_ack'

        # Receive initial status
        data = websocket.receive_json()
        assert data['type'] == 'status'
        assert 'progress_percentage' in data

        # Simulate progress update from Celery
        redis_client.publish(f'task:{task_id}:progress', json.dumps({
            'type': 'progress',
            'progress_percentage': 50
        }))

        # Verify client receives it
        data = websocket.receive_json()
        assert data['progress_percentage'] == 50
```

## Performance Considerations

- **Latency**: Expect 50-200ms delay between Celery publish and client receive
- **Throughput**: Each WebSocket connection consumes ~10KB memory
- **Scaling**: Use Redis pub/sub for horizontal scaling across FastAPI instances
- **Message Size**: Keep messages <1KB for optimal performance

## Security

- **Authentication**: JWT token required, validated on connection
- **Authorization**: Verify user owns the task before streaming updates
- **Rate Limiting**: Max 1 connection per task per user
- **Message Validation**: Sanitize all messages to prevent XSS in client rendering
