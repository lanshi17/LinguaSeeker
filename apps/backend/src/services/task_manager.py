# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportDeprecated=false, reportUnusedCallResult=false, reportUnnecessaryIsInstance=false, reportUntypedFunctionDecorator=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnusedParameter=false, reportUnusedFunction=false, reportUnnecessaryCast=false

import asyncio
import hashlib
import json
import mimetypes
import os
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    TypedDict,
    cast,
)
from uuid import UUID, uuid4

import httpx
from langchain_core.runnables.config import RunnableConfig
from langgraph.errors import EmptyInputError
from loguru import logger

import src.utils.exceptions as exc
import src.utils.file_utils as file_utils
from src.api.dependencies import map_error_code
from src.celery_app import celery_app
from src.config import settings
from src.domain.agent.document_parsing import (
    collect_parsing_assets,
    get_document_parsing_agent,
)
from src.domain.agent.workflow import EvidenceAgent
from src.domain.graph.sync import SchemaSyncError, get_graph_sync_service
from src.domain.literature import (
    get_firecrawl_service,
    get_pubmed_service,
    literature_unified_workflow,
)
from src.domain.models import (
    DocumentParsingArtifact,
    DocumentParsingResult,
    EvidenceOutput,
    PipelineFiles,
    PipelineResult,
)
from src.infrastructure.minio import MinIOClient
from src.infrastructure.postgres import get_postgres_client
from src.services.kg_events import get_kg_event_service
from src.infrastructure.redis import cache_pdf_result
from src.services.enum import (
    PROCESSING_NODE_TO_STEP,
    STEP_TO_WORKFLOW_STATUS,
    ProcessingStepStatus,
    WorkflowStatus,
    calculate_progress_percentage,
    default_processing_steps,
    merge_processing_step_update,
    normalize_processing_steps,
)
from src.services.traceability import build_trace_chain, normalize_warning_codes
from src.tools.db.qdrant_tool import QdrantManager, initialize_knowledge_base
from src.utils.timer import Timer

cfg = settings

_agents = EvidenceAgent()
_qdrant_manager = QdrantManager()
_REBUILD_EMPTY_KB = getattr(cfg, "rebuild_empty_knowledge_base", True)
_RELEASE_NO = "v1.0"
_HGVS_TOKEN_PATTERN = re.compile(
    r"(?:[A-Z]{2}_\d+\.\d+:)?[cgp]\.[A-Za-z0-9_+\-*><=()\[\];:]+"
)

# ---------------------------------------------------------------------------
# Pipeline exception handling: structured outcome schema
# ---------------------------------------------------------------------------


class PipelineIssue(TypedDict):
    """Structured representation of a non-fatal pipeline issue (warning or error).

    Attributes:
        kind: Issue severity - 'warning' for non-critical issues, 'error' for failures
        step: Pipeline step where issue occurred (e.g. 'init_kb', 'cache_result')
        message: Human-readable description
        exception_type: Optional exception class name (e.g. 'RuntimeError')
    """

    kind: Literal["warning", "error"]
    step: str
    message: str
    exception_type: Optional[str]


class PipelineOutcome(TypedDict):
    """Accumulator for non-fatal issues during pipeline execution.

    Attributes:
        errors: List of non-fatal errors encountered
        warnings: List of warnings encountered
    """

    errors: List[PipelineIssue]
    warnings: List[PipelineIssue]


def _make_empty_outcome() -> PipelineOutcome:
    """Create an empty pipeline outcome accumulator."""
    return {"errors": [], "warnings": []}


def _record_issue(
    outcome: PipelineOutcome,
    *,
    kind: Literal["warning", "error"],
    step: str,
    message: str,
    exception: Optional[Exception] = None,
) -> None:
    """Record a non-fatal issue in the pipeline outcome.

    Args:
        outcome: Pipeline outcome accumulator to update
        kind: 'warning' or 'error'
        step: Pipeline step identifier
        message: Human-readable issue description
        exception: Optional exception instance for type extraction
    """
    issue: PipelineIssue = {
        "kind": kind,
        "step": step,
        "message": message,
        "exception_type": type(exception).__name__ if exception else None,
    }
    if kind == "warning":
        outcome["warnings"].append(issue)
    else:
        outcome["errors"].append(issue)


# ---------------------------------------------------------------------------
# M1 utility helpers
# ---------------------------------------------------------------------------

_DOCX_EXTENSIONS = {".docx", ".doc"}


def _detect_language(text: str, *, sample_size: int = 2000) -> str:
    """Heuristic language detection based on ASCII ratio.

    Medical/scientific English is overwhelmingly Latin-character based.
    Returns ``"en"`` when the sample text is predominantly ASCII
    (threshold ≥ 0.85), otherwise ``"unknown"``.
    """
    if not text or not text.strip():
        return "unknown"
    sample = text[:sample_size]
    ascii_chars = sum(1 for ch in sample if ord(ch) < 128)
    ratio = ascii_chars / len(sample)
    return "en" if ratio >= 0.85 else "unknown"


def _is_docx(file_path: str) -> bool:
    """Return *True* when *file_path* has a DOCX/DOC extension."""
    return Path(file_path).suffix.lower() in _DOCX_EXTENSIONS


def _attempt_hgvs_correction(
    source_text: str,
    translated_text: str,
) -> Tuple[str, bool]:
    """Try to restore HGVS tokens that were corrupted during translation.

    Strategy: find HGVS tokens present in *source_text* but absent from
    *translated_text*.  For each missing token, attempt to locate a
    corrupted near-match in the translation and replace it.  Falls back to
    appending a ``[HGVS]`` reference block at the end when no near-match is
    found.

    Returns ``(corrected_text, all_restored)`` where *all_restored* is
    ``True`` when every missing token was successfully injected.
    """
    source_tokens = {
        tok.strip()
        for tok in _HGVS_TOKEN_PATTERN.findall(source_text or "")
        if tok and len(tok.strip()) > 2
    }
    if not source_tokens:
        return translated_text, True

    en_lower = (translated_text or "").lower()
    missing = [tok for tok in source_tokens if tok.lower() not in en_lower]
    if not missing:
        return translated_text, True

    corrected = translated_text
    still_missing: List[str] = []
    for token in missing:
        # Prefix match (first 6 chars) handles truncation during translation
        prefix = token[:6].lower()
        if prefix and prefix in corrected.lower():
            idx = corrected.lower().index(prefix)
            end = idx
            while end < len(corrected) and corrected[end] not in (
                " ",
                "\n",
                "\t",
                ",",
                ".",
                ";",
            ):
                end += 1
            corrected = corrected[:idx] + token + corrected[end:]
        else:
            still_missing.append(token)

    if still_missing:
        block = "\n\n[HGVS Reference]\n" + "\n".join(
            f"- {tok}" for tok in still_missing
        )
        corrected += block

    all_restored = len(still_missing) == 0
    return corrected, all_restored


_DEFAULT_NODE_POLICY: Dict[str, Dict[str, int]] = {
    "acquisition": {"max_retries": 2, "delay": 300, "timeout": 900},
    "parsing": {"max_retries": 1, "delay": 600, "timeout": 1800},
    "translation": {"max_retries": 2, "delay": 120, "timeout": 1200},
    "extraction": {"max_retries": 2, "delay": 300, "timeout": 1800},
    "acmg": {"max_retries": 1, "delay": 180, "timeout": 900},
}

_supervisor_memory_checkpointer: Any | None = None


def _get_node_policy(node: str) -> Dict[str, int]:
    base = _DEFAULT_NODE_POLICY.get(node, {"max_retries": 0, "delay": 0, "timeout": 60})
    return {
        "max_retries": max(
            0,
            int(getattr(cfg, f"node_{node}_max_retries", base["max_retries"])),
        ),
        "delay": max(
            0,
            int(getattr(cfg, f"node_{node}_delay_seconds", base["delay"])),
        ),
        "timeout": max(
            1,
            int(getattr(cfg, f"node_{node}_timeout_seconds", base["timeout"])),
        ),
    }


def _build_node_policy_snapshot() -> Dict[str, Dict[str, int]]:
    return {node: _get_node_policy(node) for node in _DEFAULT_NODE_POLICY.keys()}


def _emit_kg_event_for_success(
    postgres: Any,
    *,
    request_id: Optional[str],
    paper_task_id: Optional[str],
    document_id: Optional[str],
) -> None:
    task_id = str(paper_task_id or "").strip()
    doc_id = str(document_id or "").strip()
    if not task_id or not doc_id:
        return

    idempotency_key = f"kg:{_RELEASE_NO}:paper_completed:{task_id}"
    try:
        event = get_kg_event_service().create_kg_event(
            request_id=request_id or None,
            paper_task_id=task_id,
            document_id=doc_id,
            event_type="paper_completed",
            idempotency_key=idempotency_key,
            payload={"release_no": _RELEASE_NO},
        )
        postgres.append_paper_task_log(
            task_id,
            status="success",
            node="kg",
            message=f"KG event enqueued: {getattr(event, 'event_id', 'unknown')}",
            payload={
                "event_type": "paper_completed",
                "idempotency_key": idempotency_key,
                "release_no": _RELEASE_NO,
            },
        )
    except Exception as kg_exc:
        logger.warning("KG event enqueue failed for paper task {}: {}", task_id, kg_exc)
        postgres.append_paper_task_log(
            task_id,
            status="success",
            node="kg",
            message=f"KG event enqueue failed: {kg_exc}",
            payload={
                "event_type": "paper_completed",
                "idempotency_key": idempotency_key,
                "release_no": _RELEASE_NO,
            },
        )


def _update_processing_step_status(
    postgres: Any,
    paper_task_id: str,
    *,
    step: str,
    status: ProcessingStepStatus,
    message: Optional[str] = None,
    error_code: Optional[str] = None,
    workflow_status: Optional[WorkflowStatus] = None,
) -> None:
    task_id = str(paper_task_id or "").strip()
    if not task_id:
        return

    try:
        if not hasattr(postgres, "update_paper_task") or not hasattr(
            postgres, "get_paper_task"
        ):
            return

        paper_entry = postgres.get_paper_task(task_id)
        node_trace = (
            getattr(paper_entry, "node_trace", None)
            if paper_entry is not None
            else None
        )
        processing_steps = normalize_processing_steps(
            getattr(paper_entry, "processing_steps", None)
            if paper_entry is not None
            else None,
            node_trace=node_trace,
        )

        canonical_step = PROCESSING_NODE_TO_STEP.get(step.lower(), step.lower())
        processing_steps = merge_processing_step_update(
            processing_steps,
            step=canonical_step,
            status=status,
            message=message,
            error_code=error_code,
        )

        target_workflow_status = workflow_status
        if target_workflow_status is None:
            if status == ProcessingStepStatus.failed:
                target_workflow_status = WorkflowStatus.failed
            else:
                target_workflow_status = STEP_TO_WORKFLOW_STATUS.get(
                    canonical_step,
                    WorkflowStatus.pending,
                )

        postgres.update_paper_task(
            task_id,
            workflow_status=target_workflow_status.value,
            processing_steps=processing_steps,
        )
    except Exception as status_exc:
        logger.warning(
            "Failed to update processing step {} for {}: {}",
            step,
            paper_task_id,
            status_exc,
        )


def _get_paper_task_processing_steps(
    postgres: Any,
    paper_task_id: str,
    *,
    node_trace: Optional[Dict[str, str]] = None,
) -> Dict[str, Dict[str, Any]]:
    task_id = str(paper_task_id or "").strip()
    if not task_id:
        return normalize_processing_steps(None, node_trace=node_trace)

    try:
        if not hasattr(postgres, "get_paper_task"):
            return normalize_processing_steps(None, node_trace=node_trace)
        paper_entry = postgres.get_paper_task(task_id)
        if paper_entry is None:
            return normalize_processing_steps(None, node_trace=node_trace)
        return normalize_processing_steps(
            getattr(paper_entry, "processing_steps", None),
            node_trace=node_trace or getattr(paper_entry, "node_trace", None),
        )
    except Exception:
        return normalize_processing_steps(None, node_trace=node_trace)


async def _run_async_with_node_policy(
    node: str,
    operation: str,
    runner: Callable[[], Awaitable[Any]],
    policy_override: Optional[Dict[str, int]] = None,
) -> Tuple[Any, int]:
    policy = policy_override or _get_node_policy(node)
    max_attempts = policy["max_retries"] + 1
    last_exc: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            result = await asyncio.wait_for(runner(), timeout=policy["timeout"])
            return result, attempt
        except Exception as exc:
            last_exc = exc
            if attempt >= max_attempts:
                break
            logger.warning(
                "Node {} operation {} failed at attempt {}/{}: {}. Retry after {}s",
                node,
                operation,
                attempt,
                max_attempts,
                exc,
                policy["delay"],
            )
            if policy["delay"] > 0:
                await asyncio.sleep(policy["delay"])

    assert last_exc is not None
    raise last_exc


def _run_sync_with_node_policy(
    node: str,
    operation: str,
    func: Callable[..., Any],
    *args: Any,
    policy_override: Optional[Dict[str, int]] = None,
    **kwargs: Any,
) -> Tuple[Any, int]:
    async def _runner() -> Any:
        return await asyncio.to_thread(func, *args, **kwargs)

    return asyncio.run(
        _run_async_with_node_policy(
            node,
            operation,
            _runner,
            policy_override=policy_override,
        )
    )


def _sync_evidence_to_graph(
    document_id: str, evidence_output: Any | None
) -> Optional[Dict[str, Any]]:
    """Push extracted evidence into PostgreSQL + Neo4j via GraphSyncService."""
    if not evidence_output:
        logger.debug(
            "Graph sync skipped for document {}: empty evidence payload", document_id
        )
        return None

    payload: Any = evidence_output
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()
    elif hasattr(payload, "dict"):
        payload = payload.dict()

    if not isinstance(payload, dict):
        logger.warning(
            "Graph sync skipped for document {}: payload is not a dict (type={})",
            document_id,
            type(payload),
        )
        return None

    svc = get_graph_sync_service()
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            result = svc.sync_evidence(document_id, payload)
            if not result:
                return None
            if result.get("skipped"):
                reason = result.get("reason", "data_quality")
                logger.warning(
                    "Graph sync skipped for document {} due to {} (context={})",
                    document_id,
                    reason,
                    result.get("context"),
                )
                result.setdefault("error_category", "data")
                if result.get("retryable"):
                    _schedule_evidence_retry(document_id, payload, reason)
            else:
                logger.info(
                    "Graph sync finished for document {}: {}", document_id, result
                )
            return result
        except SchemaSyncError as schema_exc:
            logger.error(
                "Graph sync schema error for document {}: {} | context={}",
                document_id,
                schema_exc,
                getattr(schema_exc, "context", {}),
            )
            return {
                "pg_evidence_id": None,
                "neo4j_synced": False,
                "error_category": "schema",
                "error": str(schema_exc),
                "context": getattr(schema_exc, "context", {}),
            }
        except exc.ValidationException as validation_exc:
            logger.warning(
                "Graph sync validation error for document {}: {}",
                document_id,
                validation_exc,
            )
            return {
                "pg_evidence_id": None,
                "neo4j_synced": False,
                "error_category": "data",
                "error": str(validation_exc),
            }
        except Exception as general_exc:
            logger.error(
                "Graph sync attempt {}/{} failed for document {}: {}",
                attempt,
                max_attempts,
                document_id,
                general_exc,
            )
            if attempt == max_attempts:
                return None
            time.sleep(min(3, attempt))


def _materialize_retry_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    def _default(obj: Any) -> Any:
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "dict"):
            return obj.dict()
        if isinstance(obj, set):
            return list(obj)
        return str(obj)

    try:
        return json.loads(json.dumps(payload, default=_default))
    except Exception:
        # 如果 JSON 序列化失败，则退化为浅拷贝
        return dict(payload)


def _schedule_evidence_retry(
    document_id: str, payload: Dict[str, Any], reason: str
) -> None:
    max_retries = getattr(cfg, "evidence_retry_limit", 0)
    if max_retries <= 0:
        logger.debug("Quality retry disabled, skip scheduling for {}", document_id)
        return
    attempts = int(payload.get("_quality_retry_attempts", 0))
    if attempts >= max_retries:
        logger.info(
            "Quality retry limit reached for document {} (attempts={} reason={})",
            document_id,
            attempts,
            reason,
        )
        return
    delay_seconds = max(30, getattr(cfg, "evidence_retry_delay_seconds", 600))
    retry_payload = _materialize_retry_payload(payload)
    retry_payload["_quality_retry_attempts"] = attempts + 1
    logger.info(
        "Scheduling quality retry for document {} in {}s (attempt {}/{}) reason={}",
        document_id,
        delay_seconds,
        attempts + 1,
        max_retries,
        reason,
    )
    celery_app.send_task(
        "tasks.retry_graph_sync",
        args=[document_id, retry_payload],
        countdown=delay_seconds,
        queue="retry",
    )


def _line_spans(text: str) -> List[Dict[str, Any]]:
    spans: List[Dict[str, Any]] = []
    cursor = 0
    for raw_line in text.splitlines():
        start = cursor
        end = start + len(raw_line)
        spans.append({"text": raw_line, "start": start, "end": end})
        cursor = end + 1
    return spans


def _build_sentence_alignments(
    source_text: str,
    en_text: str,
    max_items: int = 200,
) -> List[Dict[str, Any]]:
    source_lines = [row for row in _line_spans(source_text) if row["text"].strip()]
    en_lines = [row for row in _line_spans(en_text) if row["text"].strip()]
    count = min(len(source_lines), len(en_lines), max_items)
    alignments: List[Dict[str, Any]] = []
    for idx in range(count):
        src = source_lines[idx]
        eng = en_lines[idx]
        alignments.append(
            {
                "source_sentence": src["text"],
                "en_sentence": eng["text"],
                "source_start": src["start"],
                "source_end": src["end"],
                "en_start": eng["start"],
                "en_end": eng["end"],
            }
        )
    return alignments


def _detect_warning_codes(source_text: str, en_text: str) -> List[str]:
    warnings: List[str] = []
    source_hgvs_tokens = {
        token.strip()
        for token in _HGVS_TOKEN_PATTERN.findall(source_text or "")
        if token and len(token.strip()) > 2
    }
    if source_hgvs_tokens:
        en_text_lower = (en_text or "").lower()
        missing_count = sum(
            1 for token in source_hgvs_tokens if token.lower() not in en_text_lower
        )
        if missing_count == len(source_hgvs_tokens):
            warnings.append("HGVS_AUTOCORRECT_FAILED")
    return warnings


def _persist_alignments_and_warnings(
    postgres: Any,
    paper_task_id: str,
    source_text: str,
    en_text: str,
    base_warnings: Optional[List[str]] = None,
) -> List[str]:
    alignments = _build_sentence_alignments(source_text, en_text)
    alignment_persist_failed = False
    for item in alignments:
        try:
            postgres.create_sentence_alignment(
                paper_task_id=paper_task_id,
                source_sentence=item["source_sentence"],
                en_sentence=item["en_sentence"],
                source_start=item["source_start"],
                source_end=item["source_end"],
                en_start=item["en_start"],
                en_end=item["en_end"],
            )
        except Exception as exc:
            alignment_persist_failed = True
            logger.warning(
                "Failed to persist sentence alignment for paper {}: {}",
                paper_task_id,
                exc,
            )

    merged = list(base_warnings or [])
    if alignment_persist_failed:
        merged.append("ALIGNMENT_PERSIST_FAILED")
    merged.extend(_detect_warning_codes(source_text, en_text))
    deduped = list(dict.fromkeys([code for code in merged if code]))
    return deduped


def _disable_proxies() -> None:
    os.environ.pop("http_proxy", None)
    os.environ.pop("https_proxy", None)
    os.environ.pop("all_proxy", None)


@Timer("init_knowledge_base")
async def init_knowledge_base_if_needed() -> bool:
    try:
        exists = await _qdrant_manager.check_collection_exists(
            cfg.qdrant_collection_name
        )
    except Exception as e:
        logger.warning("Qdrant not reachable, skip knowledge base init: {}", e)
        return False

    if not exists:
        logger.info(
            "Collection {} missing, initializing knowledge base...",
            cfg.qdrant_collection_name,
        )
        try:
            await initialize_knowledge_base(cfg.knowledge_docs_dir)
        except Exception as e:
            logger.warning("Knowledge base init failed, continue without it: {}", e)
            return False
        return True

    if not _REBUILD_EMPTY_KB:
        logger.info("Collection {} exists, skipping init.", cfg.qdrant_collection_name)
        return True

    try:
        info = await _qdrant_manager.get_collection_info()
    except Exception as e:
        logger.warning("Unable to read collection info, skip init: {}", e)
        return True

    if info.vectors_count == 0:
        logger.warning(
            "Collection {} exists but is empty, initializing knowledge base...",
            cfg.qdrant_collection_name,
        )
        try:
            await initialize_knowledge_base(cfg.knowledge_docs_dir)
        except Exception as e:
            logger.warning("Knowledge base init failed, continue without it: {}", e)
            return False
    else:
        logger.info(
            "Collection {} has {} vectors, skipping init.",
            cfg.qdrant_collection_name,
            info.vectors_count,
        )
    return True


def _collect_mineru_assets(folder_path: str) -> tuple[str, List[str]]:
    return collect_parsing_assets(folder_path)


def _cleanup_managed_upload_paths(file_paths: List[str]) -> None:
    for file_path in file_paths:
        temp_file = Path(file_path)
        parent = temp_file.parent
        if parent.name.startswith("run_upload_"):
            try:
                if parent.exists():
                    shutil.rmtree(parent)
            except OSError as exc:
                logger.warning(
                    "Failed to cleanup managed upload dir {}: {}", parent, exc
                )


async def _store_outputs_in_minio(
    agent_response: EvidenceOutput,
    origin_image_paths: List[str],
    document_id: str,
) -> PipelineFiles:
    minio_client = MinIOClient()
    await minio_client.ensure_buckets()

    origin_md_key = minio_client.build_processed_object_key(
        document_id, "original_format.md"
    )
    en_md_key = minio_client.build_processed_object_key(document_id, "en_format.md")
    image_desc_key = minio_client.build_processed_object_key(
        document_id, "image_descriptions.txt"
    )
    ps3_evidence_key = minio_client.build_processed_object_key(
        document_id, "ps3_evidence.json"
    )
    image_dir_key = minio_client.build_processed_object_key(document_id, "images")

    await minio_client.upload_processed_result_bytes(
        document_id=document_id,
        object_name="original_format.md",
        payload=(agent_response.origin_format_md or "").encode("utf-8"),
        content_type="text/markdown; charset=utf-8",
    )
    await minio_client.upload_processed_result_bytes(
        document_id=document_id,
        object_name="en_format.md",
        payload=(agent_response.en_format_md or "").encode("utf-8"),
        content_type="text/markdown; charset=utf-8",
    )

    image_desc_content = "\n".join(agent_response.image_descriptions or []) + "\n"
    await minio_client.upload_processed_result_bytes(
        document_id=document_id,
        object_name="image_descriptions.txt",
        payload=image_desc_content.encode("utf-8"),
        content_type="text/plain; charset=utf-8",
    )

    await minio_client.upload_processed_result_json(
        document_id, agent_response.ps3_evidence
    )

    image_urls: List[str] = []
    for img_path in origin_image_paths:
        img_file = Path(img_path)
        filename = img_file.name
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        await minio_client.upload_processed_image(
            document_id=document_id,
            filename=filename,
            payload=img_file.read_bytes(),
            content_type=content_type,
        )
        image_urls.append(f"{cfg.api_prefix}/results/{document_id}/images/{filename}")

    return PipelineFiles(
        origin_md_path=origin_md_key,
        en_md_path=en_md_key,
        image_desc_path=image_desc_key,
        ps3_evidence_path=ps3_evidence_key,
        image_dir=image_dir_key,
        origin_md_url=f"{cfg.api_prefix}/results/{document_id}/original_format.md",
        en_md_url=f"{cfg.api_prefix}/results/{document_id}/en_format.md",
        image_desc_url=f"{cfg.api_prefix}/results/{document_id}/image_descriptions.txt",
        ps3_evidence_url=f"{cfg.api_prefix}/results/{document_id}/ps3_evidence.json",
        image_urls=image_urls,
    )


async def _store_parsing_artifacts_in_minio(
    parsing_result: DocumentParsingResult,
    document_id: str,
) -> DocumentParsingArtifact:
    minio_client = MinIOClient()
    await minio_client.ensure_buckets()

    markdown_ref = await minio_client.upload_processed_result_bytes(
        document_id=document_id,
        object_name="parsing/parsed_markdown.md",
        payload=parsing_result.markdown_content.encode("utf-8"),
        content_type="text/markdown; charset=utf-8",
    )

    image_object_keys: List[str] = []
    image_urls: List[str] = []
    for image_path in parsing_result.image_paths:
        image_file = Path(image_path)
        content_type = (
            mimetypes.guess_type(image_file.name)[0] or "application/octet-stream"
        )
        image_ref = await minio_client.upload_processed_result_bytes(
            document_id=document_id,
            object_name=f"parsing/images/{image_file.name}",
            payload=image_file.read_bytes(),
            content_type=content_type,
        )
        image_object_keys.append(image_ref.object_key)
        image_urls.append(
            f"{cfg.api_prefix}/results/{document_id}/{image_ref.object_key}"
        )

    return DocumentParsingArtifact(
        markdown_object_key=markdown_ref.object_key,
        markdown_url=f"{cfg.api_prefix}/results/{document_id}/{markdown_ref.object_key}",
        image_object_keys=image_object_keys,
        image_urls=image_urls,
    )


async def _store_acquired_web_content(
    document_id: str,
    url: str,
    markdown_content: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    minio_client = MinIOClient()
    await minio_client.ensure_buckets()

    url_hash = hashlib.sha256(f"url:{url}".encode("utf-8")).hexdigest()
    raw_name = Path(str(url).split("?", 1)[0].rstrip("/")).name or "web-source"
    safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", raw_name).strip("-.") or "web-source"
    filename = f"{Path(safe_name).stem}.md"
    storage_key = minio_client.build_literature_object_key(url_hash, filename)

    upload_ref = await minio_client.upload_literature_upload(
        payload=markdown_content.encode("utf-8"),
        content_type="text/markdown; charset=utf-8",
        storage_key=storage_key,
        filename=filename,
        metadata={
            "source": "web",
            "source_url": str(url),
            "provider": str((metadata or {}).get("provider") or "firecrawl"),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return upload_ref.object_key


def _resolve_download_path(downloads: List[Dict[str, Any]]) -> Optional[Path]:
    for item in downloads:
        if not isinstance(item, dict):
            continue
        candidate = str(
            item.get("file_path") or item.get("path") or item.get("saved_path") or ""
        ).strip()
        if not candidate:
            continue
        file_path = Path(candidate)
        if file_path.is_file():
            return file_path
    return None


def _resolve_download_url(downloads: List[Dict[str, Any]]) -> Optional[str]:
    for item in downloads:
        if not isinstance(item, dict):
            continue
        for key in ("pdf_url", "doc_url", "url"):
            candidate = str(item.get(key) or "").strip()
            if candidate.startswith("http://") or candidate.startswith("https://"):
                return candidate
    return None


def _is_pdf_file(path: Path) -> bool:
    try:
        return path.is_file() and path.read_bytes().startswith(b"%PDF-")
    except Exception:
        return False


def _safe_pdf_filename(source: str, stem: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(stem or "").strip()).strip("-.")
    if not normalized:
        normalized = f"{source}-paper"
    if not normalized.lower().endswith(".pdf"):
        normalized = f"{normalized}.pdf"
    return normalized


async def _download_url_to_file(url: str, target: Path) -> Tuple[bool, Optional[str]]:
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                with target.open("wb") as output:
                    async for chunk in response.aiter_bytes(1024 * 1024):
                        if chunk:
                            output.write(chunk)
        return True, None
    except Exception as exc:
        return False, str(exc)


async def _try_download_and_store_literature_pdf(
    *,
    document_id: str,
    source: Literal["pubmed", "web"],
    query: str,
    identifiers: List[str],
    detail_link: Optional[str] = None,
    selected_title: Optional[str] = None,
) -> Dict[str, Any]:
    if not document_id:
        return {"downloaded": False, "reason": "document_id_missing"}

    download_dir = Path("/tmp/literature-downloads") / document_id
    download_dir.mkdir(parents=True, exist_ok=True)

    payload: Dict[str, Any] = {
        "action": "download",
        "query": str(query or ""),
        "identifiers": [str(item).strip() for item in identifiers if str(item).strip()],
        "prefer": "auto",
        "download_path": str(download_dir),
        "selected_index": 0,
        "raw": True,
    }
    if detail_link:
        payload["detail_link"] = str(detail_link)
    if selected_title:
        payload["selected_title"] = str(selected_title)

    try:
        response = await literature_unified_workflow(payload)
    except Exception as exc:
        shutil.rmtree(download_dir, ignore_errors=True)
        return {
            "downloaded": False,
            "reason": "unified_workflow_error",
            "error": str(exc),
        }

    route = response.get("route") if isinstance(response, dict) else {}
    warnings = list(
        (response.get("warnings") if isinstance(response, dict) else []) or []
    )
    downloads = list(
        (response.get("downloads") if isinstance(response, dict) else []) or []
    )
    raw_payload = response.get("raw") if isinstance(response, dict) else None
    api_payload = raw_payload.get("api") if isinstance(raw_payload, dict) else None
    web_payload = raw_payload.get("web") if isinstance(raw_payload, dict) else None
    source_trace = []
    if isinstance(api_payload, dict):
        trace_value = api_payload.get("source_trace")
        if isinstance(trace_value, list):
            source_trace = trace_value
    elif isinstance(web_payload, dict):
        trace_value = web_payload.get("source_trace")
        if isinstance(trace_value, list):
            source_trace = trace_value

    file_path = _resolve_download_path(downloads)
    if file_path is None:
        fallback_url = _resolve_download_url(downloads)
        if fallback_url:
            fallback_name = _safe_pdf_filename(source, selected_title or document_id)
            candidate = download_dir / fallback_name
            ok, error = await _download_url_to_file(fallback_url, candidate)
            if not ok:
                warnings.append(f"download_url_failed:{error}")
            elif candidate.is_file():
                file_path = candidate

    if file_path is None or not file_path.is_file():
        shutil.rmtree(download_dir, ignore_errors=True)
        return {
            "downloaded": False,
            "reason": "pdf_not_found",
            "route": route,
            "warnings": warnings,
            "downloads_count": len(downloads),
        }

    if not _is_pdf_file(file_path):
        shutil.rmtree(download_dir, ignore_errors=True)
        return {
            "downloaded": False,
            "reason": "invalid_pdf_signature",
            "route": route,
            "warnings": warnings,
            "downloads_count": len(downloads),
            "local_file_path": str(file_path),
        }

    payload_bytes = file_path.read_bytes()
    file_hash = hashlib.sha256(payload_bytes).hexdigest()
    filename = _safe_pdf_filename(source, file_path.name)
    storage_key = MinIOClient.build_literature_object_key(file_hash, filename)
    provider = None
    if isinstance(route, dict):
        used = route.get("used")
        if used == "api":
            provider = route.get("api_provider")
        elif used == "web":
            provider = route.get("web_provider")

    upload_ref = None
    try:
        minio_client = MinIOClient()
        await minio_client.ensure_buckets()
        upload_ref = await minio_client.upload_literature_upload(
            payload=payload_bytes,
            content_type="application/pdf",
            storage_key=storage_key,
            filename=filename,
            metadata={
                "source": source,
                "provider": str(provider or ""),
                "route_used": str(route.get("used") if isinstance(route, dict) else ""),
                "route_reason": str(
                    route.get("reason") if isinstance(route, dict) else ""
                ),
                "source_trace": json.dumps(source_trace, ensure_ascii=False),
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as exc:
        shutil.rmtree(download_dir, ignore_errors=True)
        return {
            "downloaded": False,
            "reason": "minio_upload_failed",
            "error": str(exc),
            "route": route,
            "warnings": warnings,
            "local_file_path": str(file_path),
        }
    finally:
        shutil.rmtree(download_dir, ignore_errors=True)

    return {
        "downloaded": True,
        "route": route,
        "provider": provider,
        "warnings": warnings,
        "downloads_count": len(downloads),
        "source_trace": source_trace,
        "local_file_name": filename,
        "sha256": file_hash,
        "size_bytes": len(payload_bytes),
        "object_key": upload_ref.object_key if upload_ref else None,
        "bucket": str(getattr(upload_ref.bucket, "value", upload_ref.bucket))
        if upload_ref
        else None,
    }


# ---------------------------------------------------------------------------
# 5-node pipeline runners  (acquisition → parsing → translation → extraction → acmg)
# ---------------------------------------------------------------------------


def _log_node_start(
    postgres: Any, paper_task_id: str, node: str, extra: Optional[Dict[str, Any]] = None
) -> None:
    task_id = str(paper_task_id or "").strip()
    if not task_id:
        logger.debug("Skip node {} start log: empty paper_task_id", node)
        return

    try:
        payload: Dict[str, Any] = {"node_retry_policy": _get_node_policy(node)}
        if extra:
            payload.update(extra)
        postgres.append_paper_task_log(
            task_id,
            status="running",
            node=node,
            message=f"Node {node} started",
            payload=payload,
        )
        _update_processing_step_status(
            postgres,
            task_id,
            step=node,
            status=ProcessingStepStatus.running,
            message=f"Node {node} started",
        )
    except Exception as log_exc:
        logger.warning(
            "Failed to log node {} start for {}: {}", node, paper_task_id, log_exc
        )


def _log_node_end(
    postgres: Any,
    paper_task_id: str,
    node: str,
    *,
    success: bool,
    attempt: int = 1,
    error_code: Optional[str] = None,
    message: Optional[str] = None,
) -> None:
    task_id = str(paper_task_id or "").strip()
    if not task_id:
        logger.debug("Skip node {} end log: empty paper_task_id", node)
        return

    try:
        status = "running" if success else "failed"
        postgres.append_paper_task_log(
            task_id,
            status=status,
            node=node,
            error_code=error_code,
            message=message
            or (f"Node {node} completed" if success else f"Node {node} failed"),
            payload={"attempt": attempt},
        )
        _update_processing_step_status(
            postgres,
            task_id,
            step=node,
            status=(
                ProcessingStepStatus.completed
                if success
                else ProcessingStepStatus.failed
            ),
            error_code=error_code,
            message=message
            or (f"Node {node} completed" if success else f"Node {node} failed"),
        )
    except Exception as log_exc:
        logger.warning(
            "Failed to log node {} end for {}: {}", node, paper_task_id, log_exc
        )


def _update_node_trace(
    node_trace: Dict[str, Any], node: str, outcome: str
) -> Dict[str, Any]:
    node_trace[node] = outcome
    return node_trace


def run_node_acquisition(
    postgres: Any,
    paper_task_id: str,
    file_paths: List[str],
    node_trace: Dict[str, str],
) -> Tuple[List[str], Dict[str, str]]:
    _log_node_start(postgres, paper_task_id, "acquisition")
    missing = [fp for fp in file_paths if not Path(fp).is_file()]
    if missing:
        _log_node_end(
            postgres,
            paper_task_id,
            "acquisition",
            success=False,
            error_code="INPUT_INVALID",
            message=f"Files not found: {missing}",
        )
        raise exc.ValidationException(f"Files not found: {missing}")

    _log_node_end(postgres, paper_task_id, "acquisition", success=True)
    return file_paths, _update_node_trace(node_trace, "acquisition", "success")


async def run_node_parsing(
    postgres: Any,
    paper_task_id: str,
    file_paths: List[str],
    node_trace: Dict[str, str],
) -> Tuple[DocumentParsingResult, Dict[str, str]]:
    _log_node_start(postgres, paper_task_id, "parsing")

    has_docx = any(_is_docx(fp) for fp in file_paths)
    if has_docx:
        _log_node_end(
            postgres,
            paper_task_id,
            "parsing",
            success=False,
            error_code="PARSE_FAILED",
            message="DOCX parsing is not supported — terminal failure",
        )
        raise exc.ParsingException("DOCX parsing is not supported — terminal failure")

    try:
        parsing_result, attempt = await _run_async_with_node_policy(
            "parsing",
            "parse_documents",
            lambda: asyncio.to_thread(
                get_document_parsing_agent().parse_documents, file_paths
            ),
        )
    except Exception as parsing_exc:
        _log_node_end(
            postgres,
            paper_task_id,
            "parsing",
            success=False,
            error_code="PARSE_FAILED",
            message=str(parsing_exc),
        )
        raise exc.ParsingException(str(parsing_exc)) from parsing_exc

    if not parsing_result or not parsing_result.mineru_folder:
        _log_node_end(
            postgres,
            paper_task_id,
            "parsing",
            success=False,
            error_code="PARSE_FAILED",
            message="Parser returned no folder",
        )
        raise exc.ParsingException("Parser returned no folder")

    _log_node_end(
        postgres,
        paper_task_id,
        "parsing",
        success=True,
        attempt=attempt,
        message=(
            f"Parsed with {parsing_result.parser_backend}; "
            f"images={parsing_result.image_count}; task_id={parsing_result.parser_task_id or 'n/a'}"
        ),
    )
    return parsing_result, _update_node_trace(node_trace, "parsing", "success")


def run_node_translation(
    postgres: Any,
    paper_task_id: str,
    md_content: str,
    node_trace: Dict[str, str],
) -> Tuple[str, str, Dict[str, str], List[str]]:
    """Returns (source_text, en_text, node_trace, warning_codes)."""
    _log_node_start(postgres, paper_task_id, "translation")

    lang = _detect_language(md_content)
    if lang == "en":
        logger.info("Source text detected as English — skipping translation")
        _log_node_end(
            postgres,
            paper_task_id,
            "translation",
            success=True,
            message="Skipped: source is English",
        )
        return (
            md_content,
            md_content,
            _update_node_trace(node_trace, "translation", "skipped_english"),
            [],
        )

    from src.domain.enums import ProcessingState

    state: ProcessingState = {
        "markdown_content": md_content,
        "image_paths": [],
        "translated_md": "",
        "image_descriptions": [],
        "enable_vlm": False,
        "vlm_results": [],
        "ps3_evidence": {},
        "extracted_fields": {},
        "evidence_sources": [],
        "knowledge_context": "",
        "field_confidence_scores": {},
        "overall_confidence": 0.0,
        "evidence_classification": "",
        "acmg_evidence_levels": [],
        "arbitration_confidence": 0.0,
        "arbitration_score": 0.0,
        "arbitration_feedback": "",
        "iteration_count": 0,
        "max_iterations": 1,
        "needs_manual_review": False,
        "status": "pending",
        "output": None,
    }

    try:
        result_state, attempt = _run_sync_with_node_policy(
            "translation",
            "translate_markdown",
            _agents.translate_markdown,
            state,
        )
    except Exception as trans_exc:
        _log_node_end(
            postgres,
            paper_task_id,
            "translation",
            success=False,
            error_code="TRANSLATION_FAILED",
            message=str(trans_exc),
        )
        raise

    en_text = result_state.get("translated_md", "")
    if not en_text.strip():
        _log_node_end(
            postgres,
            paper_task_id,
            "translation",
            success=False,
            error_code="TRANSLATION_EMPTY",
            message="Translation produced empty output",
        )
        raise exc.TranslationError("Translation produced empty output")

    warning_codes: List[str] = []
    corrected_text, all_restored = _attempt_hgvs_correction(md_content, en_text)
    if not all_restored:
        warning_codes.append("HGVS_AUTOCORRECT_FAILED")
    en_text = corrected_text

    _log_node_end(postgres, paper_task_id, "translation", success=True, attempt=attempt)
    return (
        md_content,
        en_text,
        _update_node_trace(node_trace, "translation", "success"),
        warning_codes,
    )


def run_node_extraction(
    postgres: Any,
    paper_task_id: str,
    source_text: str,
    en_text: str,
    image_paths: List[str],
    node_trace: Dict[str, str],
) -> Tuple[EvidenceOutput, Dict[str, str]]:
    _log_node_start(postgres, paper_task_id, "extraction")

    try:
        agent_response, attempt = _run_sync_with_node_policy(
            "extraction",
            "process_medical_evidence",
            _agents.process_medical_evidence,
            markdown_content=source_text or en_text,
            image_paths=image_paths,
            translated_md=en_text,
        )
    except Exception as ext_exc:
        _log_node_end(
            postgres,
            paper_task_id,
            "extraction",
            success=False,
            error_code="EVIDENCE_EXTRACTION_FAILED",
            message=str(ext_exc),
        )
        raise

    if not agent_response or getattr(agent_response, "status", None) == "failed":
        _log_node_end(
            postgres,
            paper_task_id,
            "extraction",
            success=False,
            error_code="EVIDENCE_EXTRACTION_FAILED",
            message="Evidence processing returned failed status",
        )
        raise exc.ReasoningException("Evidence processing failed")

    _log_node_end(postgres, paper_task_id, "extraction", success=True, attempt=attempt)
    _update_processing_step_status(
        postgres,
        paper_task_id,
        step="adjudication",
        status=ProcessingStepStatus.completed,
        workflow_status=WorkflowStatus.adjudicating,
        message=f"Adjudication completed with status: {getattr(agent_response, 'status', 'unknown')}",
    )
    return agent_response, _update_node_trace(node_trace, "extraction", "success")


def run_node_acmg(
    postgres: Any,
    paper_task_id: str,
    document_id: str,
    agent_response: EvidenceOutput,
    node_trace: Dict[str, str],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, str]]:
    _log_node_start(postgres, paper_task_id, "acmg")

    try:
        graph_sync_result = _sync_evidence_to_graph(document_id, agent_response)
    except Exception as acmg_exc:
        _log_node_end(
            postgres,
            paper_task_id,
            "acmg",
            success=False,
            error_code="GRAPH_SYNC_FAILED",
            message=str(acmg_exc),
        )
        raise

    _log_node_end(postgres, paper_task_id, "acmg", success=True)
    return graph_sync_result, _update_node_trace(node_trace, "acmg", "success")


def _build_supervisor_checkpointer(enable_interrupt: bool) -> Any | None:
    if not enable_interrupt:
        return None
    global _supervisor_memory_checkpointer
    if _supervisor_memory_checkpointer is not None:
        return _supervisor_memory_checkpointer

    from langgraph.checkpoint.memory import MemorySaver

    _supervisor_memory_checkpointer = MemorySaver()
    return _supervisor_memory_checkpointer


def _resolve_supervisor_thread_id(
    request_id: str,
    paper_task_id: str,
    document_id: str,
) -> str:
    for candidate in (request_id, paper_task_id, document_id):
        normalized = str(candidate or "").strip()
        if normalized:
            return normalized
    return "supervisor-thread"


def _build_supervisor_payload(
    *,
    final_state: Dict[str, Any],
    source: str,
    document_id: str,
    paper_task_id: str,
    request_id: str,
    file_hash: Optional[str] = None,
    file_size_bytes: Optional[int] = None,
) -> Dict[str, Any]:
    evidence_output = final_state.get("evidence_output")
    requires_human_review = bool(final_state.get("requires_human_review"))
    workflow_status = str(final_state.get("workflow_status") or "")
    status = "failed" if workflow_status == WorkflowStatus.failed.value else "success"
    if status == "success" and requires_human_review:
        status = "pending_review"

    payload: Dict[str, Any] = {
        "document_id": document_id,
        "paper_task_id": paper_task_id,
        "request_id": request_id,
        "status": status,
        "workflow_status": workflow_status,
        "requires_human_review": requires_human_review,
        "node_trace": final_state.get("node_trace", {}),
        "graph_sync_result": final_state.get("graph_sync_result", {}),
    }
    if source == "upload":
        payload["file_hash"] = file_hash
        payload["file_size_bytes"] = file_size_bytes
    if isinstance(evidence_output, EvidenceOutput):
        payload["evidence"] = evidence_output.model_dump(mode="json")
    elif isinstance(evidence_output, dict):
        payload["evidence"] = evidence_output

    if status == "failed":
        payload["error_code"] = str(final_state.get("error_code") or "INTERNAL_ERROR")
        payload["error_message"] = str(final_state.get("error_message") or "")

    return payload


_SUPERVISOR_PROGRESS_NODES: set[str] = {
    "acquisition",
    "parsing",
    "translation",
    "extraction",
    "reasoning",
    "arbitration",
}
"""Supervisor graph nodes that map to user-visible processing steps."""


async def _stream_supervisor_graph(
    graph: Any,
    initial_state: Any | None,
    config: RunnableConfig,
    postgres: Any,
    paper_task_id: str,
) -> Dict[str, Any]:
    """Run a compiled supervisor graph with streaming, persisting node
    progress to the database so the WebSocket polling endpoint picks up
    real-time updates.

    Uses ``stream_mode="updates"`` which yields
    ``{node_name: state_update}`` after each node completes.
    The final accumulated state is returned.
    """
    final_state: Dict[str, Any] = {}
    prev_node: str | None = None

    try:
        async for chunk in graph.astream(
            initial_state, config=config, stream_mode="updates"
        ):
            for node_name, node_output in chunk.items():
                if prev_node in _SUPERVISOR_PROGRESS_NODES:
                    _log_node_end(postgres, paper_task_id, prev_node, success=True)

                if node_name in _SUPERVISOR_PROGRESS_NODES:
                    _log_node_start(postgres, paper_task_id, node_name)

                if isinstance(node_output, dict):
                    final_state.update(node_output)
                prev_node = node_name

        if prev_node in _SUPERVISOR_PROGRESS_NODES:
            _log_node_end(postgres, paper_task_id, prev_node, success=True)
    except Exception:
        if prev_node in _SUPERVISOR_PROGRESS_NODES:
            _log_node_end(
                postgres,
                paper_task_id,
                prev_node,
                success=False,
                error_code="NODE_FAILURE",
                message=f"Node '{prev_node}' raised an exception",
            )
        raise

    return final_state


def _run_supervisor_pipeline(
    *,
    source: str,
    document_id: str,
    paper_task_id: str,
    request_id: str,
    postgres: Any,
    file_paths: Optional[List[str]] = None,
    pmids: Optional[List[str]] = None,
    urls: Optional[List[str]] = None,
    file_hash: Optional[str] = None,
    file_size_bytes: Optional[int] = None,
) -> Dict[str, Any]:
    async def _invoke() -> Dict[str, Any]:
        from src.agents.supervisor import compile_supervisor
        from src.state.global_state import SupervisorState

        checkpointer = _build_supervisor_checkpointer(
            cfg.agent_workflow_interrupt_before_human_review
        )
        graph = compile_supervisor(
            interrupt_before_human_review=cfg.agent_workflow_interrupt_before_human_review,
            checkpointer=checkpointer,
        )
        invoke_config: RunnableConfig = {
            "configurable": {
                "thread_id": _resolve_supervisor_thread_id(
                    request_id=request_id,
                    paper_task_id=paper_task_id,
                    document_id=document_id,
                )
            }
        }
        initial_state: SupervisorState = cast(
            SupervisorState,
            cast(
                object,
                {
                    "request_id": request_id or "",
                    "paper_task_id": int(paper_task_id)
                    if str(paper_task_id).isdigit()
                    else 0,
                    "document_id": int(document_id)
                    if str(document_id).isdigit()
                    else 0,
                    "celery_task_id": "",
                    "source": source,
                    "file_paths": file_paths or [],
                    "urls": urls or [],
                    "pmids": pmids or [],
                    "current_node": "route_by_source",
                    "workflow_status": WorkflowStatus.pending.value,
                    "processing_steps": default_processing_steps(),
                    "node_trace": {},
                    "retries": {},
                    "warnings": [],
                    "errors": [],
                    "requires_human_review": False,
                    "parsing_result": None,
                    "parser_backend": None,
                    "markdown_content": None,
                    "image_paths": [],
                    "sentence_alignments": None,
                    "translated_markdown": None,
                    "image_descriptions": None,
                    "evidence_output": None,
                    "extracted_fields": None,
                    "arbitration_confidence": None,
                    "final_evidence_strength": None,
                    "acmg_result": None,
                    "evidence_sources": [],
                    "output_files": None,
                    "final_result": None,
                    "_inner_processing_state": None,
                },
            ),
        )
        final_state = await _stream_supervisor_graph(
            graph, initial_state, invoke_config, postgres, paper_task_id
        )
        return _build_supervisor_payload(
            final_state=cast(Dict[str, Any], final_state),
            source=source,
            document_id=document_id,
            paper_task_id=paper_task_id,
            request_id=request_id,
            file_hash=file_hash,
            file_size_bytes=file_size_bytes,
        )

    return asyncio.run(_invoke())


def _resume_supervisor_pipeline(
    *,
    source: str,
    document_id: str,
    paper_task_id: str,
    request_id: str,
    postgres: Any,
) -> Dict[str, Any]:
    async def _resume() -> Dict[str, Any]:
        from src.agents.supervisor import compile_supervisor

        checkpointer = _build_supervisor_checkpointer(True)
        graph = compile_supervisor(
            interrupt_before_human_review=True,
            checkpointer=checkpointer,
        )
        invoke_config: RunnableConfig = {
            "configurable": {
                "thread_id": _resolve_supervisor_thread_id(
                    request_id=request_id,
                    paper_task_id=paper_task_id,
                    document_id=document_id,
                )
            }
        }
        try:
            final_state = await _stream_supervisor_graph(
                graph, None, invoke_config, postgres, paper_task_id
            )
        except EmptyInputError:
            return {
                "document_id": document_id,
                "paper_task_id": paper_task_id,
                "request_id": request_id,
                "status": "failed",
                "workflow_status": WorkflowStatus.failed.value,
                "requires_human_review": False,
                "node_trace": {},
                "graph_sync_result": {},
                "error_code": "RESOURCE_NOT_FOUND",
                "error_message": "No paused workflow state found for resume",
            }
        except Exception as resume_exc:
            logger.exception(
                "Failed to resume supervisor workflow for paper_task_id={}",
                paper_task_id,
            )
            return {
                "document_id": document_id,
                "paper_task_id": paper_task_id,
                "request_id": request_id,
                "status": "failed",
                "workflow_status": WorkflowStatus.failed.value,
                "requires_human_review": False,
                "node_trace": {},
                "graph_sync_result": {},
                "error_code": "INTERNAL_ERROR",
                "error_message": str(resume_exc),
            }

        return _build_supervisor_payload(
            final_state=cast(Dict[str, Any], final_state),
            source=source,
            document_id=document_id,
            paper_task_id=paper_task_id,
            request_id=request_id,
        )

    return asyncio.run(_resume())


@celery_app.task(
    name="tasks.resume_supervisor",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 30, "queue": "retry"},
    retry_jitter=True,
)
def resume_supervisor_task(self, paper_task_id: str) -> Dict[str, Any]:
    del self

    postgres = get_postgres_client()
    paper_task = postgres.get_paper_task(paper_task_id)
    if paper_task is None:
        raise ValueError(f"Paper task not found: {paper_task_id}")

    request_id = str(getattr(paper_task, "request_id", "") or "")
    document_value = getattr(paper_task, "document_id", None)
    document_id = str(document_value) if document_value is not None else ""
    source = "upload" if document_id else "pubmed"

    postgres.update_paper_task(
        paper_task_id,
        status="running",
        workflow_status=WorkflowStatus.pending.value,
        error_details=None,
    )
    postgres.append_paper_task_log(
        paper_task_id,
        status="running",
        node="resume",
        message="Supervisor resume requested",
    )

    result = _resume_supervisor_pipeline(
        source=source,
        document_id=document_id,
        paper_task_id=paper_task_id,
        request_id=request_id,
        postgres=postgres,
    )
    status = str(result.get("status") or "").lower()

    if status == "failed":
        error_code = str(result.get("error_code") or "INTERNAL_ERROR")
        error_message = str(result.get("error_message") or "Supervisor resume failed")
        postgres.update_paper_task(
            paper_task_id,
            status="failed",
            workflow_status=WorkflowStatus.failed.value,
            error_code=error_code,
            error_details={"error_code": error_code, "message": error_message},
            node_trace=result.get("node_trace") or {},
        )
        postgres.append_paper_task_log(
            paper_task_id,
            status="failed",
            node="resume",
            error_code=error_code,
            message=error_message,
        )
    elif status == "pending_review":
        postgres.update_paper_task(
            paper_task_id,
            status="running",
            workflow_status=WorkflowStatus.pending.value,
            error_code=None,
            error_details=None,
            node_trace=result.get("node_trace") or {},
        )
        postgres.append_paper_task_log(
            paper_task_id,
            status="running",
            node="resume",
            message="Supervisor resumed and waiting for human review",
            payload={"workflow_status": result.get("workflow_status")},
        )
    else:
        postgres.update_paper_task(
            paper_task_id,
            status="success",
            workflow_status=WorkflowStatus.completed.value,
            error_code=None,
            error_details=None,
            node_trace=result.get("node_trace") or {},
        )
        postgres.append_paper_task_log(
            paper_task_id,
            status="success",
            node="resume",
            message="Supervisor resume completed",
            payload={"workflow_status": result.get("workflow_status")},
        )

    if request_id:
        postgres.refresh_task_request_status(request_id)
    return result


@celery_app.task(
    name="tasks.process_pdf",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 30, "queue": "retry"},
    retry_jitter=True,
)
def process_pdf_task(
    self,
    file_paths: List[str],
    output_root: Optional[str] = None,
    file_hash: Optional[str] = None,
    document_id: Optional[str] = None,
    paper_task_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    logger.debug(
        "Celery task start file_paths: {} output_root: {} file_hash: {}",
        file_paths,
        output_root,
        file_hash,
    )
    start_time = datetime.now(timezone.utc)
    file_size_bytes: Optional[int] = 0
    sized_files = 0
    for file_path in file_paths:
        try:
            file_size_bytes += os.path.getsize(file_path)
            sized_files += 1
        except OSError as size_exc:
            logger.warning("Unable to read file size for {}: {}", file_path, size_exc)
    if sized_files == 0:
        file_size_bytes = None

    document_id = document_id or str(uuid4())
    postgres = None
    node_trace: Dict[str, str] = {}
    pipeline_outcome = _make_empty_outcome()

    if paper_task_id:
        try:
            postgres = get_postgres_client()
            postgres.update_paper_task(
                paper_task_id,
                status="running",
                workflow_status=WorkflowStatus.pending.value,
                processing_steps=default_processing_steps(),
                file_size_bytes=file_size_bytes,
                processing_duration_seconds=None,
                error_details=None,
            )
            postgres.append_paper_task_log(
                paper_task_id,
                status="running",
                node="pipeline",
                message="Paper task started",
                payload={"node_retry_policy": _build_node_policy_snapshot()},
            )
            if request_id:
                postgres.update_task_request(request_id, status="running")
        except Exception as init_exc:
            logger.exception(
                "Unable to mark paper task {} running: {}", paper_task_id, init_exc
            )
            _record_issue(
                pipeline_outcome,
                kind="warning",
                step="init_db_status",
                message=f"Failed to update initial task status: {init_exc}",
                exception=init_exc,
            )

    try:
        _disable_proxies()

        try:
            asyncio.run(init_knowledge_base_if_needed())
        except Exception as kb_exc:
            logger.exception("Knowledge base init failed, continue: {}", kb_exc)
            _record_issue(
                pipeline_outcome,
                kind="warning",
                step="init_kb",
                message=f"Knowledge base initialization failed: {kb_exc}",
                exception=kb_exc,
            )

        if postgres is None and paper_task_id:
            postgres = get_postgres_client()

        if cfg.use_agent_workflow("pdf"):
            return _run_supervisor_pipeline(
                source="upload",
                document_id=document_id,
                paper_task_id=paper_task_id or "",
                request_id=request_id or "",
                postgres=postgres,
                file_paths=file_paths,
                file_hash=file_hash,
                file_size_bytes=file_size_bytes,
            )

        # --- Node 1: Acquisition ---
        validated_paths, node_trace = run_node_acquisition(
            postgres,
            paper_task_id or "",
            file_paths,
            node_trace,
        )

        # --- Node 2: Parsing ---
        parsing_result, node_trace = asyncio.run(
            run_node_parsing(postgres, paper_task_id or "", validated_paths, node_trace)
        )
        parsing_artifacts = asyncio.run(
            _store_parsing_artifacts_in_minio(parsing_result, document_id)
        )
        parsing_result.artifacts = parsing_artifacts
        parsing_metadata = {
            "parser_backend": parsing_result.parser_backend,
            "parser_task_id": parsing_result.parser_task_id,
            "mineru_folder": parsing_result.mineru_folder,
            "image_count": parsing_result.image_count,
            "markdown_object_key": parsing_artifacts.markdown_object_key,
            "markdown_url": parsing_artifacts.markdown_url,
            "image_object_keys": parsing_artifacts.image_object_keys,
            "image_urls": parsing_artifacts.image_urls,
        }
        if paper_task_id and postgres is not None:
            postgres.append_paper_task_log(
                paper_task_id,
                status="success",
                node="parsing",
                message="Parsing artifacts stored",
                payload=parsing_metadata,
            )

        # --- Node 3: Translation ---
        source_text, en_text, node_trace, translation_warnings = run_node_translation(
            postgres,
            paper_task_id or "",
            parsing_result.markdown_content,
            node_trace,
        )

        # --- Node 4: Extraction ---
        agent_response, node_trace = run_node_extraction(
            postgres,
            paper_task_id or "",
            source_text,
            en_text,
            parsing_result.image_paths,
            node_trace,
        )

        # Store outputs in MinIO
        saved_files = asyncio.run(
            _store_outputs_in_minio(
                agent_response, parsing_result.image_paths, document_id
            )
        )

        # --- Node 5: ACMG / Graph Sync ---
        graph_sync_result, node_trace = run_node_acmg(
            postgres,
            paper_task_id or "",
            document_id,
            agent_response,
            node_trace,
        )

        end_time = datetime.now(timezone.utc)
        processing_duration_seconds = (end_time - start_time).total_seconds()
        alignment_count = len(_build_sentence_alignments(source_text, en_text))

        payload: Dict[str, Any]
        result = PipelineResult(
            document_id=document_id,
            output_dir=f"{cfg.minio_results_bucket}/{document_id}",
            mineru_folder=parsing_result.mineru_folder,
            parsing_metadata=parsing_metadata,
            files=saved_files,
            evidence=agent_response,
            warning_codes=list(translation_warnings),
            alignment_count=alignment_count,
        )
        if hasattr(result, "model_dump"):
            payload = result.model_dump()
        else:
            payload = {}
        if isinstance(payload, dict):
            if file_size_bytes is not None:
                payload.setdefault("file_size_bytes", file_size_bytes)
            payload.setdefault(
                "processing_duration_seconds", processing_duration_seconds
            )
            payload.setdefault("created_at", start_time.isoformat())
            payload.setdefault("updated_at", end_time.isoformat())
            if graph_sync_result is not None:
                payload["graph_sync_result"] = graph_sync_result
            payload.setdefault("workflow_status", WorkflowStatus.completed.value)
            payload.setdefault("mineru_folder", parsing_result.mineru_folder)
            payload.setdefault("parsing_metadata", parsing_metadata)
            payload.setdefault("pipeline_outcome", pipeline_outcome)

        if paper_task_id and postgres is not None:
            try:
                processing_steps = _get_paper_task_processing_steps(
                    postgres,
                    paper_task_id,
                    node_trace=node_trace,
                )
                progress_percentage = calculate_progress_percentage(processing_steps)
                warning_codes = _persist_alignments_and_warnings(
                    postgres,
                    paper_task_id,
                    source_text=source_text,
                    en_text=en_text,
                    base_warnings=translation_warnings,
                )
                normalized_warning_codes = normalize_warning_codes(warning_codes) or []
                trace_chain = build_trace_chain(
                    node_trace=node_trace,
                    processing_steps=processing_steps,
                )
                postgres.update_paper_task(
                    paper_task_id,
                    status="success",
                    workflow_status=WorkflowStatus.completed.value,
                    error_code=None,
                    error_details=None,
                    warning_codes=normalized_warning_codes or None,
                    node_trace=node_trace,
                    processing_steps=processing_steps,
                    file_size_bytes=file_size_bytes,
                    processing_duration_seconds=processing_duration_seconds,
                )
                postgres.append_paper_task_log(
                    paper_task_id,
                    status="success",
                    node="acmg",
                    message="Paper task completed",
                )
                _emit_kg_event_for_success(
                    postgres,
                    request_id=request_id,
                    paper_task_id=paper_task_id,
                    document_id=document_id,
                )
                if isinstance(payload, dict):
                    payload.setdefault("processing_steps", processing_steps)
                    payload.setdefault("progress_percentage", progress_percentage)
                    payload.setdefault("warning_codes", normalized_warning_codes)
                    payload["alignment_count"] = alignment_count
                    if trace_chain is not None:
                        payload.setdefault("trace_chain", trace_chain)
                    if request_id:
                        postgres.refresh_task_request_status(request_id)
            except Exception as success_exc:
                logger.exception(
                    "Unable to mark paper task {} success: {}",
                    paper_task_id,
                    success_exc,
                )
                _record_issue(
                    pipeline_outcome,
                    kind="warning",
                    step="mark_success_db",
                    message=f"Failed to persist success status to DB: {success_exc}",
                    exception=success_exc,
                )

        if file_hash:
            try:
                cache_pdf_result(file_hash, payload)
            except Exception as cache_exc:
                logger.exception(
                    "Failed to cache result for hash {}: {}", file_hash, cache_exc
                )
                _record_issue(
                    pipeline_outcome,
                    kind="warning",
                    step="cache_result",
                    message=f"Failed to cache result in Redis: {cache_exc}",
                    exception=cache_exc,
                )

        _cleanup_managed_upload_paths(file_paths)
        tmp_dir = Path(os.environ.get("PWD", str(Path.cwd()))) / "tmp"
        file_utils.cleanup_old_temp_folders(str(tmp_dir), keep_latest=3)

        logger.debug("Celery task complete")
        return payload
    except Exception as exc_outer:
        retry_count = int(getattr(self.request, "retries", 0))
        max_retries = int(getattr(self, "max_retries", 0))
        if paper_task_id and postgres is not None:
            try:
                if retry_count >= max_retries:
                    error_code = map_error_code(500, str(exc_outer))
                    end_time = datetime.now(timezone.utc)
                    processing_duration_seconds = (
                        end_time - start_time
                    ).total_seconds()
                    error_details = {
                        "error_code": error_code,
                        "message": str(exc_outer),
                    }
                    postgres.update_paper_task(
                        paper_task_id,
                        status="failed",
                        workflow_status=WorkflowStatus.failed.value,
                        error_code=error_code,
                        node_trace=node_trace,
                        processing_steps=normalize_processing_steps(
                            None, node_trace=node_trace
                        ),
                        processing_duration_seconds=processing_duration_seconds,
                        error_details=error_details,
                    )
                    postgres.append_paper_task_log(
                        paper_task_id,
                        status="failed",
                        node="pipeline",
                        error_code=error_code,
                        message=str(exc_outer),
                    )
                    if request_id:
                        postgres.refresh_task_request_status(request_id)
            except Exception as mark_exc:
                logger.warning(
                    "Unable to mark paper task {} failed: {}", paper_task_id, mark_exc
                )
        if retry_count >= max_retries:
            _cleanup_managed_upload_paths(file_paths)
        raise


@celery_app.task(
    name="tasks.retry_graph_sync",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2, "countdown": 60, "queue": "retry"},
    retry_jitter=True,
)
def retry_graph_sync_task(
    self, document_id: str, evidence_payload: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    logger.info("Quality retry triggered for document {}", document_id)
    return _sync_evidence_to_graph(document_id, evidence_payload)


@celery_app.task(
    name="tasks.process_pubmed_paper",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2, "countdown": 300, "queue": "retry"},
    retry_jitter=True,
)
def process_pubmed_paper_task(
    self,
    pmid: str,
    document_id: str,
    paper_task_id: str,
    request_id: str,
) -> Dict[str, Any]:
    postgres = get_postgres_client()
    start_time = datetime.now(timezone.utc)
    node_trace: Dict[str, Any] = {}

    if cfg.use_agent_workflow("pubmed"):
        return _run_supervisor_pipeline(
            source="pubmed",
            document_id=document_id or "",
            paper_task_id=paper_task_id or "",
            request_id=request_id or "",
            postgres=postgres,
            pmids=[pmid],
        )

    postgres.update_paper_task(
        paper_task_id,
        status="running",
        workflow_status=WorkflowStatus.processing_literature.value,
        processing_steps=default_processing_steps(),
        fulltext_unavailable="true",
        error_details=None,
    )
    postgres.update_task_request(request_id, status="running")
    postgres.append_paper_task_log(
        paper_task_id,
        status="running",
        node="pipeline",
        message=f"PubMed pipeline started for PMID:{pmid}",
        payload={"node_retry_policy": _build_node_policy_snapshot()},
    )

    # --- Node 1: Acquisition (PubMed fetch) ---
    _log_node_start(postgres, paper_task_id, "acquisition")
    acquisition_policy_override: Optional[Dict[str, int]] = None
    if int(getattr(self, "max_retries", 0)) == 0:
        acquisition_policy = _get_node_policy("acquisition")
        acquisition_policy_override = {
            "max_retries": 0,
            "delay": 0,
            "timeout": acquisition_policy["timeout"],
        }
    try:
        article, acquisition_attempt = asyncio.run(
            _run_async_with_node_policy(
                "acquisition",
                "fetch_pubmed_metadata_abstract",
                lambda: get_pubmed_service().fetch_article_metadata_abstract(pmid),
                policy_override=acquisition_policy_override,
            )
        )
        _log_node_end(
            postgres,
            paper_task_id,
            "acquisition",
            success=True,
            attempt=acquisition_attempt,
        )
        node_trace = _update_node_trace(node_trace, "acquisition", "success")
    except Exception as acq_exc:
        _log_node_end(
            postgres,
            paper_task_id,
            "acquisition",
            success=False,
            error_code=map_error_code(
                500, f"Fetch timeout while querying PubMed: {acq_exc}"
            ),
            message=f"PubMed fetch failed: {acq_exc}",
        )
        node_trace = _update_node_trace(node_trace, "acquisition", "failed")
        retry_count = int(getattr(self.request, "retries", 0))
        max_retries = int(getattr(self, "max_retries", 0))
        if retry_count >= max_retries:
            error_code = map_error_code(
                500, f"Fetch timeout while querying PubMed: {acq_exc}"
            )
            postgres.update_paper_task(
                paper_task_id,
                status="failed",
                workflow_status=WorkflowStatus.failed.value,
                error_code=error_code,
                node_trace=node_trace,
                processing_steps=normalize_processing_steps(
                    None, node_trace=node_trace
                ),
                error_details={"error_code": error_code, "message": str(acq_exc)},
            )
            postgres.refresh_task_request_status(request_id)
        raise

    if article is None or (not article.title and not article.abstract):
        error_code = "FETCH_NO_RESULT"
        _log_node_end(
            postgres,
            paper_task_id,
            "acquisition",
            success=False,
            error_code=error_code,
            message=f"No usable PubMed payload for PMID:{pmid}",
        )
        node_trace = _update_node_trace(node_trace, "acquisition", "failed")
        postgres.update_paper_task(
            paper_task_id,
            status="failed",
            workflow_status=WorkflowStatus.failed.value,
            error_code=error_code,
            node_trace=node_trace,
            processing_steps=normalize_processing_steps(None, node_trace=node_trace),
            error_details={
                "error_code": error_code,
                "message": "No usable PubMed payload",
            },
        )
        postgres.refresh_task_request_status(request_id)
        return {
            "pmid": pmid,
            "document_id": document_id,
            "paper_task_id": paper_task_id,
            "status": "failed",
            "error_code": error_code,
        }

    pubmed_pdf_result = asyncio.run(
        _try_download_and_store_literature_pdf(
            document_id=document_id,
            source="pubmed",
            query=f"PMID:{pmid}",
            identifiers=[str(pmid), str(getattr(article, "doi", "") or "")],
            selected_title=str(getattr(article, "title", None) or f"PMID-{pmid}"),
        )
    )
    pubmed_fulltext_unavailable = not bool(pubmed_pdf_result.get("downloaded"))
    source_trace = pubmed_pdf_result.get("source_trace")
    if isinstance(source_trace, list):
        node_trace["acquisition_detail"] = {
            "provider": str(pubmed_pdf_result.get("provider") or ""),
            "source_trace": source_trace,
        }
    postgres.append_paper_task_log(
        paper_task_id,
        status="running",
        node="acquisition",
        message=f"PubMed fulltext download {'succeeded' if not pubmed_fulltext_unavailable else 'unavailable'} for PMID:{pmid}",
        payload={"pdf_download": pubmed_pdf_result},
    )

    markdown_content = (
        f"# {article.title or f'PMID:{pmid}'}\n\n"
        f"- PMID: {article.pmid}\n"
        f"- Journal: {article.journal}\n"
        f"- Published: {article.pub_date}\n\n"
        f"## Abstract\n\n{article.abstract or ''}"
    )

    # --- Node 2: Parsing (skipped — metadata/abstract fallback) ---
    node_trace = _update_node_trace(node_trace, "parsing", "fallback_metadata_abstract")
    _update_processing_step_status(
        postgres,
        paper_task_id,
        step="parsing",
        status=ProcessingStepStatus.skipped,
        workflow_status=WorkflowStatus.processing_pdf,
        message="Parsing skipped: using metadata/abstract fallback",
    )

    # --- Node 3: Translation ---
    try:
        source_text, en_text, node_trace, translation_warnings = run_node_translation(
            postgres,
            paper_task_id,
            markdown_content,
            node_trace,
        )
    except Exception as trans_exc:
        node_trace = _update_node_trace(node_trace, "translation", "failed")
        retry_count = int(getattr(self.request, "retries", 0))
        max_retries = int(getattr(self, "max_retries", 0))
        if retry_count >= max_retries:
            error_code = map_error_code(500, str(trans_exc))
            postgres.update_paper_task(
                paper_task_id,
                status="failed",
                workflow_status=WorkflowStatus.failed.value,
                error_code=error_code,
                node_trace=node_trace,
                processing_steps=normalize_processing_steps(
                    None, node_trace=node_trace
                ),
                error_details={"error_code": error_code, "message": str(trans_exc)},
            )
            postgres.refresh_task_request_status(request_id)
        raise

    # --- Node 4: Extraction ---
    try:
        agent_response, node_trace = run_node_extraction(
            postgres,
            paper_task_id,
            source_text,
            en_text,
            [],
            node_trace,
        )
    except Exception as ext_exc:
        retry_count = int(getattr(self.request, "retries", 0))
        max_retries = int(getattr(self, "max_retries", 0))
        if retry_count >= max_retries:
            error_code = map_error_code(500, str(ext_exc))
            postgres.update_paper_task(
                paper_task_id,
                status="failed",
                workflow_status=WorkflowStatus.failed.value,
                error_code=error_code,
                node_trace=node_trace,
                processing_steps=normalize_processing_steps(
                    None, node_trace=node_trace
                ),
                error_details={"error_code": error_code, "message": str(ext_exc)},
            )
            postgres.refresh_task_request_status(request_id)
        raise

    if not agent_response or getattr(agent_response, "status", None) == "failed":
        error_code = "EVIDENCE_EXTRACTION_FAILED"
        postgres.update_paper_task(
            paper_task_id,
            status="failed",
            workflow_status=WorkflowStatus.failed.value,
            error_code=error_code,
            node_trace=node_trace,
            processing_steps=normalize_processing_steps(None, node_trace=node_trace),
            error_details={
                "error_code": error_code,
                "message": "Evidence processing returned failed status",
            },
        )
        postgres.append_paper_task_log(
            paper_task_id,
            status="failed",
            node="extraction",
            error_code=error_code,
            message="Evidence processing returned failed status",
        )
        postgres.refresh_task_request_status(request_id)
        return {
            "pmid": pmid,
            "document_id": document_id,
            "paper_task_id": paper_task_id,
            "status": "failed",
            "error_code": error_code,
        }

    files = asyncio.run(_store_outputs_in_minio(agent_response, [], document_id))

    # --- Node 5: ACMG / Graph Sync ---
    try:
        graph_sync_result, node_trace = run_node_acmg(
            postgres,
            paper_task_id,
            document_id,
            agent_response,
            node_trace,
        )
    except Exception as acmg_exc:
        logger.warning("Graph sync failed for PubMed PMID:{}: {}", pmid, acmg_exc)
        graph_sync_result = None
        node_trace = _update_node_trace(node_trace, "acmg", "failed")
        _update_processing_step_status(
            postgres,
            paper_task_id,
            step="classification",
            status=ProcessingStepStatus.skipped,
            workflow_status=WorkflowStatus.classifying,
            message="Graph sync failed but pipeline continued",
            error_code="GRAPH_SYNC_FAILED",
        )

    base_warnings = list(translation_warnings)
    if pubmed_fulltext_unavailable:
        base_warnings.insert(0, "FULLTEXT_UNAVAILABLE")
    warning_codes = _persist_alignments_and_warnings(
        postgres,
        paper_task_id,
        source_text=source_text,
        en_text=en_text,
        base_warnings=base_warnings,
    )
    normalized_warning_codes = normalize_warning_codes(warning_codes) or []
    processing_steps = _get_paper_task_processing_steps(
        postgres,
        paper_task_id,
        node_trace=node_trace,
    )
    trace_chain = build_trace_chain(
        node_trace=node_trace,
        processing_steps=processing_steps,
    )

    document_identifier: Any = document_id
    try:
        document_identifier = UUID(str(document_id))
    except (TypeError, ValueError, AttributeError):
        document_identifier = document_id

    document_update_fields: Dict[str, Any] = {
        "status": "success",
        "summary": (
            f"PubMed metadata/abstract fallback used for PMID:{pmid}"
            if pubmed_fulltext_unavailable
            else f"PubMed fulltext PDF acquired for PMID:{pmid}"
        ),
    }
    if pubmed_pdf_result.get("object_key"):
        document_update_fields["local_path"] = pubmed_pdf_result.get("object_key")
    postgres.update_document(document_identifier, **document_update_fields)
    postgres.update_paper_task(
        paper_task_id,
        status="success",
        workflow_status=WorkflowStatus.completed.value,
        error_code=None,
        error_details=None,
        fulltext_unavailable=pubmed_fulltext_unavailable,
        node_trace=node_trace,
        warning_codes=normalized_warning_codes,
        processing_steps=processing_steps,
        processing_duration_seconds=(
            datetime.now(timezone.utc) - start_time
        ).total_seconds(),
    )
    postgres.append_paper_task_log(
        paper_task_id,
        status="success",
        node="acmg",
        message=f"PubMed fallback completed for PMID:{pmid}",
        payload={
            "fulltext_unavailable": pubmed_fulltext_unavailable,
            "pdf_download": pubmed_pdf_result,
            "graph_sync_result": graph_sync_result,
        },
    )
    _emit_kg_event_for_success(
        postgres,
        request_id=request_id,
        paper_task_id=paper_task_id,
        document_id=document_id,
    )
    postgres.refresh_task_request_status(request_id)
    return {
        "pmid": pmid,
        "document_id": document_id,
        "paper_task_id": paper_task_id,
        "fulltext_unavailable": pubmed_fulltext_unavailable,
        "pdf_download": pubmed_pdf_result,
        "status": "success",
        "files": files.model_dump() if hasattr(files, "model_dump") else files,
        "graph_sync_result": graph_sync_result,
        "warning_codes": normalized_warning_codes,
        "trace_chain": trace_chain,
    }


@celery_app.task(
    name="tasks.process_web_page",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2, "countdown": 300, "queue": "retry"},
    retry_jitter=True,
)
def process_web_page_task(
    self,
    url: str,
    document_id: str,
    paper_task_id: str,
    request_id: str,
) -> Dict[str, Any]:
    postgres = get_postgres_client()
    start_time = datetime.now(timezone.utc)
    node_trace: Dict[str, Any] = {}

    if cfg.use_agent_workflow("web"):
        return _run_supervisor_pipeline(
            source="web",
            document_id=document_id or "",
            paper_task_id=paper_task_id or "",
            request_id=request_id or "",
            postgres=postgres,
            urls=[url],
        )

    postgres.update_paper_task(
        paper_task_id,
        status="running",
        workflow_status=WorkflowStatus.processing_literature.value,
        processing_steps=default_processing_steps(),
        error_details=None,
    )
    postgres.update_task_request(request_id, status="running")
    postgres.append_paper_task_log(
        paper_task_id,
        status="running",
        node="pipeline",
        message=f"Web crawl pipeline started for URL:{url}",
        payload={"node_retry_policy": _build_node_policy_snapshot(), "source": "web"},
    )

    _log_node_start(postgres, paper_task_id, "acquisition")
    acquisition_policy_override: Optional[Dict[str, int]] = None
    if int(getattr(self, "max_retries", 0)) == 0:
        acquisition_policy = _get_node_policy("acquisition")
        acquisition_policy_override = {
            "max_retries": 0,
            "delay": 0,
            "timeout": acquisition_policy["timeout"],
        }

    try:
        crawl_result, acquisition_attempt = asyncio.run(
            _run_async_with_node_policy(
                "acquisition",
                "fetch_web_markdown",
                lambda: get_firecrawl_service().scrape_markdown(url),
                policy_override=acquisition_policy_override,
            )
        )
        _log_node_end(
            postgres,
            paper_task_id,
            "acquisition",
            success=True,
            attempt=acquisition_attempt,
        )
        node_trace = _update_node_trace(node_trace, "acquisition", "success")
    except Exception as acq_exc:
        error_code = map_error_code(
            500, f"Fetch timeout while crawling web page: {acq_exc}"
        )
        _log_node_end(
            postgres,
            paper_task_id,
            "acquisition",
            success=False,
            error_code=error_code,
            message=f"Web crawl failed: {acq_exc}",
        )
        node_trace = _update_node_trace(node_trace, "acquisition", "failed")
        retry_count = int(getattr(self.request, "retries", 0))
        max_retries = int(getattr(self, "max_retries", 0))
        if retry_count >= max_retries:
            postgres.update_paper_task(
                paper_task_id,
                status="failed",
                workflow_status=WorkflowStatus.failed.value,
                error_code=error_code,
                node_trace=node_trace,
                processing_steps=normalize_processing_steps(
                    None, node_trace=node_trace
                ),
                error_details={"error_code": error_code, "message": str(acq_exc)},
            )
            postgres.refresh_task_request_status(request_id)
        raise

    markdown_content = str(getattr(crawl_result, "markdown", "") or "").strip()
    if not markdown_content:
        error_code = "FETCH_NO_RESULT"
        postgres.update_paper_task(
            paper_task_id,
            status="failed",
            workflow_status=WorkflowStatus.failed.value,
            error_code=error_code,
            node_trace=_update_node_trace(node_trace, "acquisition", "failed"),
            processing_steps=normalize_processing_steps(None, node_trace=node_trace),
            error_details={
                "error_code": error_code,
                "message": "No usable web crawl payload",
            },
        )
        postgres.refresh_task_request_status(request_id)
        return {
            "source_url": url,
            "document_id": document_id,
            "paper_task_id": paper_task_id,
            "status": "failed",
            "error_code": error_code,
        }

    acquisition_object_key = asyncio.run(
        _store_acquired_web_content(
            document_id=document_id,
            url=str(getattr(crawl_result, "final_url", None) or url),
            markdown_content=markdown_content,
            metadata=getattr(crawl_result, "metadata", None),
        )
    )
    final_url = str(getattr(crawl_result, "final_url", None) or url)
    crawl_title = str(getattr(crawl_result, "title", None) or final_url)
    web_pdf_result = asyncio.run(
        _try_download_and_store_literature_pdf(
            document_id=document_id,
            source="web",
            query=crawl_title,
            identifiers=[final_url],
            detail_link=final_url,
            selected_title=crawl_title,
        )
    )
    web_fulltext_unavailable = not bool(web_pdf_result.get("downloaded"))
    source_trace = web_pdf_result.get("source_trace")
    if isinstance(source_trace, list):
        node_trace["acquisition_detail"] = {
            "provider": str(web_pdf_result.get("provider") or ""),
            "source_trace": source_trace,
        }
    postgres.append_paper_task_log(
        paper_task_id,
        status="running",
        node="acquisition",
        message=f"Web fulltext download {'succeeded' if not web_fulltext_unavailable else 'unavailable'} for URL:{final_url}",
        payload={"pdf_download": web_pdf_result, "final_url": final_url},
    )

    document_identifier: Any = document_id
    try:
        document_identifier = UUID(str(document_id))
    except (TypeError, ValueError, AttributeError):
        document_identifier = document_id

    acquisition_summary = f"Web crawl content acquired from {final_url}"
    if not web_fulltext_unavailable and web_pdf_result.get("object_key"):
        acquisition_summary = f"{acquisition_summary}; fulltext PDF stored at {web_pdf_result.get('object_key')}"

    postgres.update_document(
        document_identifier,
        title=crawl_title,
        local_path=acquisition_object_key,
        summary=acquisition_summary,
    )

    node_trace = _update_node_trace(node_trace, "parsing", "markdown_direct")
    _update_processing_step_status(
        postgres,
        paper_task_id,
        step="parsing",
        status=ProcessingStepStatus.skipped,
        workflow_status=WorkflowStatus.processing_pdf,
        message="Parsing skipped: markdown acquired directly from web crawl",
    )

    try:
        source_text, en_text, node_trace, translation_warnings = run_node_translation(
            postgres,
            paper_task_id,
            markdown_content,
            node_trace,
        )
    except Exception as trans_exc:
        node_trace = _update_node_trace(node_trace, "translation", "failed")
        retry_count = int(getattr(self.request, "retries", 0))
        max_retries = int(getattr(self, "max_retries", 0))
        if retry_count >= max_retries:
            error_code = map_error_code(500, str(trans_exc))
            postgres.update_paper_task(
                paper_task_id,
                status="failed",
                workflow_status=WorkflowStatus.failed.value,
                error_code=error_code,
                node_trace=node_trace,
                processing_steps=normalize_processing_steps(
                    None, node_trace=node_trace
                ),
                error_details={"error_code": error_code, "message": str(trans_exc)},
            )
            postgres.refresh_task_request_status(request_id)
        raise

    try:
        agent_response, node_trace = run_node_extraction(
            postgres,
            paper_task_id,
            source_text,
            en_text,
            [],
            node_trace,
        )
    except Exception as ext_exc:
        retry_count = int(getattr(self.request, "retries", 0))
        max_retries = int(getattr(self, "max_retries", 0))
        if retry_count >= max_retries:
            error_code = map_error_code(500, str(ext_exc))
            postgres.update_paper_task(
                paper_task_id,
                status="failed",
                workflow_status=WorkflowStatus.failed.value,
                error_code=error_code,
                node_trace=node_trace,
                processing_steps=normalize_processing_steps(
                    None, node_trace=node_trace
                ),
                error_details={"error_code": error_code, "message": str(ext_exc)},
            )
            postgres.refresh_task_request_status(request_id)
        raise

    if not agent_response or getattr(agent_response, "status", None) == "failed":
        error_code = "EVIDENCE_EXTRACTION_FAILED"
        postgres.update_paper_task(
            paper_task_id,
            status="failed",
            workflow_status=WorkflowStatus.failed.value,
            error_code=error_code,
            node_trace=node_trace,
            processing_steps=normalize_processing_steps(None, node_trace=node_trace),
            error_details={
                "error_code": error_code,
                "message": "Evidence processing returned failed status",
            },
        )
        postgres.append_paper_task_log(
            paper_task_id,
            status="failed",
            node="extraction",
            error_code=error_code,
            message="Evidence processing returned failed status",
        )
        postgres.refresh_task_request_status(request_id)
        return {
            "source_url": url,
            "document_id": document_id,
            "paper_task_id": paper_task_id,
            "status": "failed",
            "error_code": error_code,
        }

    files = asyncio.run(_store_outputs_in_minio(agent_response, [], document_id))

    try:
        graph_sync_result, node_trace = run_node_acmg(
            postgres,
            paper_task_id,
            document_id,
            agent_response,
            node_trace,
        )
    except Exception as acmg_exc:
        logger.warning("Graph sync failed for web URL {}: {}", url, acmg_exc)
        graph_sync_result = None
        node_trace = _update_node_trace(node_trace, "acmg", "failed")
        _update_processing_step_status(
            postgres,
            paper_task_id,
            step="classification",
            status=ProcessingStepStatus.skipped,
            workflow_status=WorkflowStatus.classifying,
            message="Graph sync failed but pipeline continued",
            error_code="GRAPH_SYNC_FAILED",
        )

    base_warnings = list(translation_warnings)
    if web_fulltext_unavailable:
        base_warnings.append("FULLTEXT_UNAVAILABLE")
    warning_codes = _persist_alignments_and_warnings(
        postgres,
        paper_task_id,
        source_text=source_text,
        en_text=en_text,
        base_warnings=base_warnings,
    )
    normalized_warning_codes = normalize_warning_codes(warning_codes) or []
    processing_steps = _get_paper_task_processing_steps(
        postgres,
        paper_task_id,
        node_trace=node_trace,
    )
    trace_chain = build_trace_chain(
        node_trace=node_trace,
        processing_steps=processing_steps,
    )

    postgres.update_document(
        document_identifier,
        status="success",
        title=crawl_title,
        local_path=acquisition_object_key,
        summary=acquisition_summary,
    )
    postgres.update_paper_task(
        paper_task_id,
        status="success",
        workflow_status=WorkflowStatus.completed.value,
        error_code=None,
        error_details=None,
        fulltext_unavailable=web_fulltext_unavailable,
        node_trace=node_trace,
        warning_codes=normalized_warning_codes,
        processing_steps=processing_steps,
        processing_duration_seconds=(
            datetime.now(timezone.utc) - start_time
        ).total_seconds(),
    )
    postgres.append_paper_task_log(
        paper_task_id,
        status="success",
        node="acmg",
        message=f"Web crawl pipeline completed for URL:{url}",
        payload={
            "source_url": url,
            "final_url": final_url,
            "fulltext_unavailable": web_fulltext_unavailable,
            "pdf_download": web_pdf_result,
            "graph_sync_result": graph_sync_result,
        },
    )
    _emit_kg_event_for_success(
        postgres,
        request_id=request_id,
        paper_task_id=paper_task_id,
        document_id=document_id,
    )
    postgres.refresh_task_request_status(request_id)
    return {
        "source_url": url,
        "final_url": final_url,
        "document_id": document_id,
        "paper_task_id": paper_task_id,
        "fulltext_unavailable": web_fulltext_unavailable,
        "pdf_download": web_pdf_result,
        "status": "success",
        "files": files.model_dump() if hasattr(files, "model_dump") else files,
        "graph_sync_result": graph_sync_result,
        "warning_codes": normalized_warning_codes,
        "trace_chain": trace_chain,
    }
