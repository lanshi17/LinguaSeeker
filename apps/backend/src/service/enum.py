from enum import Enum


class TaskStatus(str, Enum):
	pending = "PENDING"
	started = "STARTED"
	success = "SUCCESS"
	failure = "FAILURE"
	retry = "RETRY"
	revoked = "REVOKED"

	@classmethod
	def from_celery(cls, status: str) -> "TaskStatus":
		try:
			return cls(status)
		except ValueError:
			return cls.pending
