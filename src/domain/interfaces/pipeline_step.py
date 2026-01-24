"""Pipeline step interface - defines contract for each processing stage."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class IPipelineStep(ABC):
    """Abstract interface for a pipeline processing step.
    
    Each step is responsible for a single, well-defined responsibility:
    - Receives input data through context
    - Performs its specific operation
    - Updates context with results
    - Handles and reports its own errors
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Get the step name for logging and debugging."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Get human-readable step description."""

    @abstractmethod
    def execute(self, context: 'IPipelineContext') -> None:
        """Execute this pipeline step.
        
        Args:
            context: Pipeline execution context containing shared data
            
        Raises:
            PipelineStepError: If step execution fails
        """

    @abstractmethod
    def validate_prerequisites(self, context: 'IPipelineContext') -> bool:
        """Validate that required prerequisites are met.
        
        Args:
            context: Pipeline execution context
            
        Returns:
            True if step can execute, False otherwise
        """

    @abstractmethod
    def rollback(self, context: 'IPipelineContext') -> None:
        """Rollback any state changes made by this step.
        
        Args:
            context: Pipeline execution context
        """


class IPipelineContext(ABC):
    """Interface for pipeline execution context.
    
    Manages state shared between pipeline steps, providing:
    - Type-safe access to shared data
    - Input/output parameter management
    - Error tracking
    - Step execution metadata
    """

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from context by key.
        
        Args:
            key: Parameter key
            default: Default value if key not found
            
        Returns:
            Stored value or default
        """

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Set value in context.
        
        Args:
            key: Parameter key
            value: Value to store
        """

    @abstractmethod
    def update(self, data: Dict[str, Any]) -> None:
        """Update context with multiple values.
        
        Args:
            data: Dictionary of key-value pairs to merge
        """

    @abstractmethod
    def has(self, key: str) -> bool:
        """Check if key exists in context.
        
        Args:
            key: Parameter key
            
        Returns:
            True if key exists
        """

    @abstractmethod
    def remove(self, key: str) -> None:
        """Remove value from context.
        
        Args:
            key: Parameter key
        """

    @abstractmethod
    def mark_step_complete(self, step_name: str) -> None:
        """Mark a pipeline step as completed.
        
        Args:
            step_name: Name of completed step
        """

    @abstractmethod
    def is_step_complete(self, step_name: str) -> bool:
        """Check if a step has completed.
        
        Args:
            step_name: Name of step to check
            
        Returns:
            True if step completed
        """

    @abstractmethod
    def get_completed_steps(self) -> list:
        """Get list of completed step names.
        
        Returns:
            List of step names that have completed
        """


class IResultAccumulator(ABC):
    """Interface for accumulating pipeline results.
    
    Responsible for:
    - Collecting results from various pipeline steps
    - Combining and organizing results
    - Preparing final output format
    - Handling result serialization
    """

    @abstractmethod
    def accumulate(self, step_name: str, results: Dict[str, Any]) -> None:
        """Accumulate results from a pipeline step.
        
        Args:
            step_name: Name of step providing results
            results: Step results as dictionary
        """

    @abstractmethod
    def get_accumulated(self) -> Dict[str, Any]:
        """Get all accumulated results.
        
        Returns:
            Dictionary of accumulated results organized by step
        """

    @abstractmethod
    def build_final_payload(self) -> Dict[str, Any]:
        """Build final output payload from accumulated results.
        
        Returns:
            Final structured output ready for return or persistence
        """

    @abstractmethod
    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata that applies to final payload.
        
        Args:
            key: Metadata key
            value: Metadata value
        """

    @abstractmethod
    def clear(self) -> None:
        """Clear all accumulated results."""
