from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from src.service.enum import TaskStatus


class ValidationErrorDetail(BaseModel):
    type: str = Field(..., description="Error type")
    loc: List[Union[str, int]] = Field(..., description="Location of the error")
    msg: str = Field(..., description="Error message")
    input: Any = Field(..., description="Input value that caused the error")
    ctx: Optional[Dict[str, Any]] = Field(None, description="Extra context")


class ValidationErrorResponse(BaseModel):
	code: str = Field("VALIDATION_ERROR", description="Error code")
	message: str = Field("Invalid request payload", description="Error message")
	errors: List[ValidationErrorDetail] = Field(..., description="Validation errors")


class TaskCreateRequest(BaseModel):
	file_paths: List[str] = Field(..., description="Local file paths to process")
	output_root: Optional[str] = Field(None, description="Output directory root")


class TaskCreateResponse(BaseModel):
	task_id: str = Field(..., description="Celery task id")
	status: TaskStatus = Field(..., description="Task status")


class TaskStatusResponse(BaseModel):
	task_id: str = Field(..., description="Celery task id")
	status: TaskStatus = Field(..., description="Task status")
	result: Optional[Dict[str, Any]] = Field(None, description="Task result if completed")
	error: Optional[str] = Field(None, description="Error message if failed")


class TaskListItem(BaseModel):
	task_id: str = Field(..., description="Celery task id")
	status: TaskStatus = Field(..., description="Task status")
	date_done: Optional[str] = Field(None, description="Completion timestamp if available")
	result: Optional[Dict[str, Any]] = Field(None, description="Task result if completed")
	error: Optional[str] = Field(None, description="Error message if failed")


class TaskListResponse(BaseModel):
	items: List[TaskListItem] = Field(..., description="Task list items")
	next_cursor: int = Field(..., description="Next Redis scan cursor")
	count: int = Field(..., description="Number of items returned")
