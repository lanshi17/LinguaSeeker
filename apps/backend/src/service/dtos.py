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

	class Config:
		json_schema_extra = {
			"example": {
				"file_paths": ["/data/uploads/sample.pdf"],
				"output_root": "/data/outputs",
			}
		}


class TaskCreateResponse(BaseModel):
	task_id: str = Field(..., description="Celery task id")
	status: TaskStatus = Field(..., description="Task status")

	class Config:
		json_schema_extra = {
			"example": {"task_id": "1f6a8b7a-1b87-4d75-8c72-6f2f6a1a9c2e", "status": "PENDING"}
		}


class TaskStatusResponse(BaseModel):
	task_id: str = Field(..., description="Celery task id")
	status: TaskStatus = Field(..., description="Task status")
	file_size_bytes: Optional[int] = Field(None, description="Total input file size in bytes")
	processing_duration_seconds: Optional[float] = Field(
		None, description="Processing duration in seconds"
	)
	created_at: Optional[str] = Field(None, description="Task creation timestamp if available")
	updated_at: Optional[str] = Field(None, description="Task update timestamp if available")
	result: Optional[Dict[str, Any]] = Field(None, description="Task result if completed")
	error: Optional[str] = Field(None, description="Error message if failed")

	class Config:
		json_schema_extra = {
			"example": {
				"task_id": "1f6a8b7a-1b87-4d75-8c72-6f2f6a1a9c2e",
				"status": "SUCCESS",
				"file_size_bytes": 1048576,
				"processing_duration_seconds": 12.3,
				"created_at": "2026-02-10T08:00:00+00:00",
				"updated_at": "2026-02-10T08:00:12+00:00",
				"result": {"summary": "task result payload"},
				"error": None,
			}
		}


class TaskListItem(BaseModel):
	task_id: str = Field(..., description="Celery task id")
	status: TaskStatus = Field(..., description="Task status")
	date_done: Optional[str] = Field(None, description="Completion timestamp if available")
	file_size_bytes: Optional[int] = Field(None, description="Total input file size in bytes")
	processing_duration_seconds: Optional[float] = Field(
		None, description="Processing duration in seconds"
	)
	created_at: Optional[str] = Field(None, description="Task creation timestamp if available")
	updated_at: Optional[str] = Field(None, description="Task update timestamp if available")
	result: Optional[Dict[str, Any]] = Field(None, description="Task result if completed")
	error: Optional[str] = Field(None, description="Error message if failed")


class TaskListResponse(BaseModel):
	items: List[TaskListItem] = Field(..., description="Task list items")
	next_cursor: int = Field(..., description="Next Redis scan cursor")
	count: int = Field(..., description="Number of items returned")

	class Config:
		json_schema_extra = {
			"example": {
				"items": [
					{
						"task_id": "1f6a8b7a-1b87-4d75-8c72-6f2f6a1a9c2e",
						"status": "SUCCESS",
						"date_done": "2026-02-10T08:00:00+00:00",
						"file_size_bytes": 1048576,
						"processing_duration_seconds": 12.3,
						"created_at": "2026-02-10T08:00:00+00:00",
						"updated_at": "2026-02-10T08:00:12+00:00",
						"result": {"summary": "task result payload"},
						"error": None,
					}
				],
				"next_cursor": 0,
				"count": 1,
			}
		}
