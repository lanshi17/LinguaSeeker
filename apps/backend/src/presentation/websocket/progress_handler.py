"""
WebSocket handler for real-time task progress tracking.

Provides WebSocket endpoints for clients to receive live updates
on document processing tasks with automatic reconnection support.
"""

from typing import Dict, Set, Optional
import asyncio
import json
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from fastapi.websockets import WebSocketState

from src.application.services.task_management_service import TaskManagementService
from src.utils.logger import Logger


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
        # Don't initialize task management service here to avoid session issues

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

    async def start_progress_monitoring(self, task_id: str) -> None:
        """
        Start monitoring task progress and sending updates.

        This method runs in the background and periodically checks
        task status, sending updates via WebSocket.

        Args:
            task_id: Task ID to monitor
        """
        self.logger.info(f"Starting progress monitoring for task {task_id}")

        # Create task management service instance
        task_management_service = TaskManagementService()

        try:
            while True:
                # Get current task status
                progress_data = await task_management_service.get_task_progress(task_id)

                if not progress_data:
                    # Task no longer exists
                    break

                # Send progress update
                await self.send_progress_update(task_id, progress_data)

                # Check if task is complete
                status = progress_data.get("status", "").lower()
                if status in ["completed", "failed", "cancelled"]:
                    break

                # Wait before next update (30 seconds as per requirements)
                await asyncio.sleep(30)

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
    for a specific parsing task. Updates are sent every 30 seconds
    as specified in the requirements.

    Args:
        websocket: WebSocket connection
        task_id: Task ID to monitor
    """
    await progress_handler.connect(websocket, task_id)

    try:
        # Start progress monitoring in background
        monitoring_task = asyncio.create_task(
            progress_handler.start_progress_monitoring(task_id)
        )

        # Keep connection alive
        while True:
            # Receive any messages from client (for future extensions)
            data = await websocket.receive_text()
            # For now, we don't process client messages
            # Just keep the connection alive

    except WebSocketDisconnect:
        await progress_handler.disconnect(websocket, task_id)
    except Exception as e:
        progress_handler.logger.error(f"WebSocket error for task {task_id}: {e}")
        await progress_handler.disconnect(websocket, task_id)