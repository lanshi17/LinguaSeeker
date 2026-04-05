from __future__ import annotations

from src.services.traceability import build_trace_chain


def test_build_trace_chain_includes_acquisition_detail_and_step_statuses() -> None:
    processing_steps = {
        "acquisition": {"status": "COMPLETED", "message": "acquired", "error_code": None},
        "parsing": {"status": "SKIPPED", "message": "fallback", "error_code": None},
        "translation": {"status": "COMPLETED", "message": None, "error_code": None},
        "extraction": {"status": "COMPLETED", "message": None, "error_code": None},
        "classification": {"status": "COMPLETED", "message": None, "error_code": None},
        "adjudication": {"status": "PENDING", "message": None, "error_code": None},
    }
    node_trace = {
        "acquisition": "success",
        "acquisition_detail": {
            "provider": "pmc",
            "source_trace": [
                {
                    "provider": "pmc",
                    "attempt": 1,
                    "success": True,
                    "items_count": 0,
                    "downloads_count": 1,
                    "warnings": [],
                    "error": None,
                }
            ],
        },
        "parsing": "fallback_metadata_abstract",
        "translation": "success",
        "extraction": "success",
        "acmg": "success",
    }

    trace_chain = build_trace_chain(
        node_trace=node_trace,
        processing_steps=processing_steps,
    )

    assert trace_chain is not None
    assert trace_chain["steps"]["acquisition"]["detail"]["provider"] == "pmc"
    assert (
        trace_chain["steps"]["acquisition"]["detail"]["source_trace"][0]["provider"]
        == "pmc"
    )
    assert trace_chain["steps"]["parsing"]["outcome"] == "fallback_metadata_abstract"
    assert trace_chain["steps"]["classification"]["outcome"] == "success"
    assert trace_chain["steps"]["adjudication"]["status"] == "PENDING"
