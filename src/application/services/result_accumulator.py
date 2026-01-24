"""Result accumulator for collecting and organizing pipeline outputs."""

from typing import Any, Dict, Optional
from collections import defaultdict

from src.domain.interfaces.pipeline_step import IResultAccumulator


class ResultAccumulator(IResultAccumulator):
    """Concrete implementation of result accumulation.
    
    Collects results from pipeline steps and combines them into
    a structured final output format.
    """

    def __init__(self):
        """Initialize empty result accumulator."""
        self._step_results: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self._metadata: Dict[str, Any] = {}
        self._result_order: list = []

    def accumulate(self, step_name: str, results: Dict[str, Any]) -> None:
        """Accumulate results from a pipeline step.
        
        Args:
            step_name: Name of step providing results
            results: Step results as dictionary
        """
        self._step_results[step_name].update(results)
        if step_name not in self._result_order:
            self._result_order.append(step_name)

    def get_accumulated(self) -> Dict[str, Any]:
        """Get all accumulated results.
        
        Returns:
            Dictionary of accumulated results organized by step
        """
        # Return in order of accumulation
        ordered_results = {}
        for step_name in self._result_order:
            if step_name in self._step_results:
                ordered_results[step_name] = self._step_results[step_name]
        return ordered_results

    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata that applies to final payload.
        
        Args:
            key: Metadata key
            value: Metadata value
        """
        self._metadata[key] = value

    def build_final_payload(self) -> Dict[str, Any]:
        """Build final output payload from accumulated results.
        
        Returns:
            Final structured output ready for return or persistence
        """
        payload = {
            "metadata": self._metadata,
            "stages": {},
        }
        
        # Add accumulated results from each step
        for step_name in self._result_order:
            if step_name in self._step_results:
                payload["stages"][step_name] = self._step_results[step_name]
        
        # Merge critical values to top level for backward compatibility
        payload.update(self._extract_critical_values())
        
        return payload

    def _extract_critical_values(self) -> Dict[str, Any]:
        """Extract critical values from step results for top-level access.
        
        Returns:
            Dictionary with top-level critical values
        """
        critical = {}
        
        # Extract commonly accessed values
        if "pdf_processing" in self._step_results:
            pdf_data = self._step_results["pdf_processing"]
            critical.update({
                "detected_language": pdf_data.get("detected_language"),
                "bbox_metadata_path": pdf_data.get("bbox_metadata_path"),
            })
        
        if "evidence_processing" in self._step_results:
            evidence_data = self._step_results["evidence_processing"]
            critical.update({
                "arbiter_score": evidence_data.get("arbiter_score"),
                "evidence": evidence_data.get("evidence"),
                "evidence_json_path": evidence_data.get("evidence_json_path"),
            })
        
        if "report_generation" in self._step_results:
            report_data = self._step_results["report_generation"]
            critical.update({
                "final_structured_path": report_data.get("structured_json_path"),
                "output_html": report_data.get("html_report_path"),
                "html_report_path": report_data.get("html_report_path"),
            })
        
        return critical

    def clear(self) -> None:
        """Clear all accumulated results."""
        self._step_results.clear()
        self._metadata.clear()
        self._result_order.clear()

    def get_step_result(self, step_name: str) -> Optional[Dict[str, Any]]:
        """Get results from a specific step.
        
        Args:
            step_name: Name of step
            
        Returns:
            Step results or None if not found
        """
        return self._step_results.get(step_name)

    def has_step_results(self, step_name: str) -> bool:
        """Check if a step has results.
        
        Args:
            step_name: Name of step
            
        Returns:
            True if step has results
        """
        return step_name in self._step_results

    def merge_results(self, other: 'ResultAccumulator') -> None:
        """Merge results from another accumulator.
        
        Args:
            other: Another ResultAccumulator to merge from
        """
        for step_name, results in other.get_accumulated().items():
            self.accumulate(step_name, results)
        
        # Merge metadata
        self._metadata.update(other._metadata)
