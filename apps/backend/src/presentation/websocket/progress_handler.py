"""
WebSocket handler for real-time task progress tracking.

Provides WebSocket endpoints for clients to receive live updates
on document processing tasks with automatic reconnection support.
"""

from typing import Dict, Set, Optional
import asyncio
import json
from datetime import datetime
import redis.asyncio as redis

from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from fastapi.websockets import WebSocketState

from src.application.services.task_management_service import TaskManagementService
from src.utils.logger import Logger
from src.config.database_config import DatabaseConfig


class ProgressHandler:
    """
    WebSocket handler for real-time task progress updates.

    Manages WebSocket connections and broadcasts progress updates
    to connected clients for specific tasks.
    """

    def __init__(self):
        """Initialize progress handler."""
        self.logger = Logger()
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.redis_client = None
        self.pubsub = None
        # Don't initialize task management service here to avoid session issues

    async def initialize_redis(self):
        """Initialize Redis connection with authentication."""
        if self.redis_client is None:
            config = DatabaseConfig.from_env()
            redis_cfg = config.redis

            # Create Redis connection with authentication
            self.redis_client = redis.Redis(
                host=redis_cfg.host,
                port=redis_cfg.port,
                db=redis_cfg.db,
                password=redis_cfg.password,  # This handles authentication
                max_connections=redis_cfg.max_connections,
                decode_responses=False,  # Keep responses as bytes to handle all types
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )

            # Test the connection
            try:
                await self.redis_client.ping()
                self.logger.info("Redis connection established successfully")
            except Exception as e:
                self.logger.error(f"Failed to connect to Redis: {e}")
                raise

    async def connect(self, websocket: WebSocket, task_id: str) -> None:
        """
        Accept WebSocket connection and add to active connections.

        Args:
            websocket: WebSocket connection
            task_id: Task ID to monitor
        """
        await websocket.accept()

        if task_id not in self.active_connections:
            self.active_connections[task_id] = set()

        self.active_connections[task_id].add(websocket)
        self.logger.info(f"WebSocket connected for task {task_id}")

        # Subscribe to Redis channel for this task
        await self.initialize_redis()
        if self.pubsub is None:
            self.pubsub = self.redis_client.pubsub()

        channel_name = f'task:{task_id}:progress'
        await self.pubsub.subscribe(channel_name)
        self.logger.info(f"Subscribed to Redis channel: {channel_name}")

    async def disconnect(self, websocket: WebSocket, task_id: str) -> None:
        """
        Remove WebSocket connection from active connections.

        Args:
            websocket: WebSocket connection to remove
            task_id: Task ID
        """
        if task_id in self.active_connections:
            self.active_connections[task_id].discard(websocket)
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]

        # Unsubscribe from Redis channel if no more connections for this task
        if task_id in self.active_connections and len(self.active_connections[task_id]) == 0:
            channel_name = f'task:{task_id}:progress'
            await self.pubsub.unsubscribe(channel_name)
            self.logger.info(f"Unsubscribed from Redis channel: {channel_name}")

        self.logger.info(f"WebSocket disconnected for task {task_id}")

    async def send_progress_update(self, task_id: str, progress_data: dict) -> None:
        """
        Send progress update to all connected clients for a task.

        Args:
            task_id: Task ID
            progress_data: Progress data to send
        """
        if task_id not in self.active_connections:
            return

        # Prepare message
        message = {
            "task_id": task_id,
            "timestamp": datetime.utcnow().isoformat(),
            "type": "progress_update",
            "data": progress_data
        }

        # Send to all connected clients
        disconnected = set()
        for websocket in self.active_connections[task_id]:
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(message)
            except WebSocketDisconnect:
                disconnected.add(websocket)
            except Exception as e:
                self.logger.error(f"Error sending progress update to WebSocket: {e}")
                disconnected.add(websocket)

        # Clean up disconnected clients
        for websocket in disconnected:
            await self.disconnect(websocket, task_id)

    async def listen_to_redis_channel(self, task_id: str):
        """
        Listen to Redis pub/sub channel for progress updates and forward to WebSocket clients.

        Args:
            task_id: Task ID to monitor
        """
        await self.initialize_redis()
        channel_name = f'task:{task_id}:progress'
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe(channel_name)

        try:
            self.logger.info(f"Listening to Redis channel: {channel_name}")
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        progress_data = json.loads(message['data'].decode('utf-8'))
                        await self.send_progress_update(task_id, progress_data)
                    except json.JSONDecodeError as e:
                        self.logger.error(f"Error decoding Redis message: {e}")
                    except Exception as e:
                        self.logger.error(f"Error processing Redis message: {e}")
        finally:
            await pubsub.close()

    async def start_progress_monitoring(self, task_id: str) -> None:
        """
        Start monitoring task progress and sending updates.

        This method runs in the background and listens to Redis for updates
        from Celery workers, forwarding them via WebSocket.

        Args:
            task_id: Task ID to monitor
        """
        self.logger.info(f"Starting progress monitoring for task {task_id}")

        try:
            # Listen to Redis channel for progress updates from Celery workers
            await self.listen_to_redis_channel(task_id)
        except Exception as e:
            self.logger.error(f"Error in progress monitoring for task {task_id}: {e}")
        finally:
            self.logger.info(f"Progress monitoring stopped for task {task_id}")


# Global progress handler instance
progress_handler = ProgressHandler()

# Create router for WebSocket endpoints
router = APIRouter()


@router.websocket("/ws/task/{task_id}/progress")
async def task_progress_websocket(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for real-time task progress updates.

    Clients connect to this endpoint to receive live progress updates
    for a specific parsing task. Updates are sent via Redis pub/sub
    from Celery workers.

    Args:
        websocket: WebSocket connection
        task_id: Task ID to monitor
    """
    await progress_handler.connect(websocket, task_id)

    try:
        # Start listening for Redis messages in background
        monitoring_task = asyncio.create_task(
            progress_handler.start_progress_monitoring(task_id)
        )

        # Keep connection alive
        while True:
            # Receive any messages from client (for future extensions)
            try:
                data = await websocket.receive_text()
                # For now, we don't process client messages
                # Just keep the connection alive
            except:
                break

    except WebSocketDisconnect:
        await progress_handler.disconnect(websocket, task_id)
    except Exception as e:
        progress_handler.logger.error(f"WebSocket error for task {task_id}: {e}")
        await progress_handler.disconnect(websocket, task_id)