"""Pipeline context implementation for managing execution state."""

from typing import Any, Dict, Optional, Set
from datetime import datetime
import json

from src.domain.interfaces.pipeline_step import IPipelineContext


class PipelineContext(IPipelineContext):
    """Concrete implementation of pipeline execution context.
    
    Manages shared state between pipeline steps with:
    - Type-safe parameter access
    - Step completion tracking
    - Execution metadata
    - Input/output separation
    """

    def __init__(self):
        """Initialize empty pipeline context."""
        self._data: Dict[str, Any] = {}
        self._completed_steps: Set[str] = set()
        self._step_start_times: Dict[str, datetime] = {}
        self._errors: Dict[str, str] = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from context by key.
        
        Args:
            key: Parameter key
            default: Default value if key not found
            
        Returns:
            Stored value or default
        """
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set value in context.
        
        Args:
            key: Parameter key
            value: Value to store
        """
        self._data[key] = value

    def update(self, data: Dict[str, Any]) -> None:
        """Update context with multiple values.
        
        Args:
            data: Dictionary of key-value pairs to merge
        """
        self._data.update(data)

    def has(self, key: str) -> bool:
        """Check if key exists in context.
        
        Args:
            key: Parameter key
            
        Returns:
            True if key exists
        """
        return key in self._data

    def remove(self, key: str) -> None:
        """Remove value from context.
        
        Args:
            key: Parameter key
        """
        if key in self._data:
            del self._data[key]

    def mark_step_complete(self, step_name: str) -> None:
        """Mark a pipeline step as completed.
        
        Args:
            step_name: Name of completed step
        """
        self._completed_steps.add(step_name)

    def is_step_complete(self, step_name: str) -> bool:
        """Check if a step has completed.
        
        Args:
            step_name: Name of step to check
            
        Returns:
            True if step completed
        """
        return step_name in self._completed_steps

    def get_completed_steps(self) -> list:
        """Get list of completed step names.
        
        Returns:
            List of step names that have completed
        """
        return sorted(list(self._completed_steps))

    def record_step_start(self, step_name: str) -> None:
        """Record when a step started executing.
        
        Args:
            step_name: Name of step
        """
        self._step_start_times[step_name] = datetime.now()

    def get_step_duration(self, step_name: str) -> Optional[float]:
        """Get execution duration of a step in seconds.
        
        Args:
            step_name: Name of step
            
        Returns:
            Duration in seconds, or None if not recorded
        """
        if step_name not in self._step_start_times:
            return None
        elapsed = datetime.now() - self._step_start_times[step_name]
        return elapsed.total_seconds()

    def record_error(self, step_name: str, error_message: str) -> None:
        """Record an error from a step.
        
        Args:
            step_name: Name of step that failed
            error_message: Error message
        """
        self._errors[step_name] = error_message

    def has_errors(self) -> bool:
        """Check if any errors have been recorded.
        
        Returns:
            True if errors exist
        """
        return len(self._errors) > 0

    def get_errors(self) -> Dict[str, str]:
        """Get all recorded errors.
        
        Returns:
            Dictionary mapping step names to error messages
        """
        return dict(self._errors)

    def clear_errors(self) -> None:
        """Clear all recorded errors."""
        self._errors.clear()

    def to_dict(self) -> Dict[str, Any]:
        """Export context as dictionary.
        
        Returns:
            Context data dictionary
        """
        return dict(self._data)

    def get_execution_summary(self) -> Dict[str, Any]:
        """Get summary of execution metadata.
        
        Returns:
            Summary including completed steps and errors
        """
        return {
            "completed_steps": self.get_completed_steps(),
            "total_steps": len(self._step_start_times),
            "has_errors": self.has_errors(),
            "errors": self.get_errors(),
            "step_durations": {
                step: self.get_step_duration(step)
                for step in self._step_start_times.keys()
            },
        }

    def clear(self) -> None:
        """Clear all context data."""
        self._data.clear()
        self._completed_steps.clear()
        self._step_start_times.clear()
        self._errors.clear()
