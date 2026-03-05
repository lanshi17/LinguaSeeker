import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple
import mimetypes

from loguru import logger

# Ensure the project root (which contains the `src` package) is importable when this file
# is invoked directly with `python -m src.service.tasks` or similar.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.domain.mineru.component import MinerUComponent
from src.domain.mineru.component import run_paddleocr_fallback
from src.domain.agent.workflow import EvidenceAgent
from src.domain.models import (
    EvidenceOutput,
    MinerURequest,
    PipelineFiles,
    PipelineResult,
)
from src.domain.graph.sync import SchemaSyncError, get_graph_sync_service
from src.domain.literature.pubmed_service import get_pubmed_service
from src.database.qdrant_client import QdrantManager, initialize_knowledge_base
from src.database.minio_client import MinIOClient
from src.database.postgre_client import get_postgres_client
from src.presentation.error_contract import map_error_code
from src.utils.timer import Timer
import src.utils.exceptions as exc
import src.utils.file_utils as file_utils
from src.config import settings
from src.celery_app import celery_app
from src.database.redis_client import cache_pdf_result


cfg = settings

_mineru = MinerUComponent()
_agents = EvidenceAgent()
_qdrant_manager = QdrantManager()
_REBUILD_EMPTY_KB = getattr(cfg, "rebuild_empty_knowledge_base", True)
_HGVS_TOKEN_PATTERN = re.compile(r"(?:[A-Z]{2}_\d+\.\d+:)?[cgp]\.[A-Za-z0-9_+\-*><=()\[\];:]+")

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
            while end < len(corrected) and corrected[end] not in (" ", "\n", "\t", ",", ".", ";"):
                end += 1
            corrected = corrected[:idx] + token + corrected[end:]
        else:
            still_missing.append(token)

    if still_missing:
        block = "\n\n[HGVS Reference]\n" + "\n".join(f"- {tok}" for tok in still_missing)
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


async def _run_async_with_node_policy(
    node: str,
    operation: str,
    runner: Callable[[], Awaitable[Any]],
) -> Tuple[Any, int]:
    policy = _get_node_policy(node)
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
    **kwargs: Any,
) -> Tuple[Any, int]:
    async def _runner() -> Any:
        return await asyncio.to_thread(func, *args, **kwargs)

    return asyncio.run(_run_async_with_node_policy(node, operation, _runner))


def _sync_evidence_to_graph(
    document_id: str, evidence_output: Any | None
) -> Optional[Dict[str, Any]]:
    """Push extracted evidence into PostgreSQL + Neo4j via GraphSyncService."""
    if not evidence_output:
        logger.debug("Graph sync skipped for document {}: empty evidence payload", document_id)
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
                logger.info("Graph sync finished for document {}: {}", document_id, result)
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


def _schedule_evidence_retry(document_id: str, payload: Dict[str, Any], reason: str) -> None:
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
    retry_graph_sync_task.apply_async(
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
        missing_count = sum(1 for token in source_hgvs_tokens if token.lower() not in en_text_lower)
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
            logger.warning(
                "Failed to persist sentence alignment for paper {}: {}", paper_task_id, exc
            )

    merged = list(base_warnings or [])
    merged.extend(_detect_warning_codes(source_text, en_text))
    # 保持顺序去重
    deduped = list(dict.fromkeys([code for code in merged if code]))
    return deduped


def _disable_proxies() -> None:
    os.environ.pop("http_proxy", None)
    os.environ.pop("https_proxy", None)
    os.environ.pop("all_proxy", None)


@Timer("init_knowledge_base")
async def init_knowledge_base_if_needed() -> bool:
    try:
        exists = await _qdrant_manager.check_collection_exists(cfg.qdrant_collection_name)
    except Exception as e:
        logger.warning("Qdrant not reachable, skip knowledge base init: {}", e)
        return False

    if not exists:
        logger.info(
            "Collection {} missing, initializing knowledge base...", cfg.qdrant_collection_name
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
            "Collection {} has %s vectors, skipping init.",
            cfg.qdrant_collection_name,
            info.vectors_count,
        )
    return True


def _collect_mineru_assets(folder_path: str) -> tuple[str, List[str]]:
    origin_folder = file_utils.get_all_files_in_directory(folder_path)
    origin_md_content = origin_folder.get(str(Path(folder_path) / "full.md"), "")
    origin_image_paths = [str(p) for p in Path(folder_path).rglob("*.jpg") if p.is_file()]
    return origin_md_content, origin_image_paths


async def _store_outputs_in_minio(
    agent_response: EvidenceOutput,
    origin_image_paths: List[str],
    document_id: str,
) -> PipelineFiles:
    minio_client = MinIOClient()
    await minio_client.ensure_buckets()

    origin_md_key = minio_client.build_processed_object_key(document_id, "original_format.md")
    en_md_key = minio_client.build_processed_object_key(document_id, "en_format.md")
    image_desc_key = minio_client.build_processed_object_key(document_id, "image_descriptions.txt")
    ps3_evidence_key = minio_client.build_processed_object_key(document_id, "ps3_evidence.json")
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

    await minio_client.upload_processed_result_json(document_id, agent_response.ps3_evidence)

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
    except Exception as log_exc:
        logger.warning("Failed to log node {} start for {}: {}", node, paper_task_id, log_exc)


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
            message=message or (f"Node {node} completed" if success else f"Node {node} failed"),
            payload={"attempt": attempt},
        )
    except Exception as log_exc:
        logger.warning("Failed to log node {} end for {}: {}", node, paper_task_id, log_exc)


def _update_node_trace(node_trace: Dict[str, str], node: str, outcome: str) -> Dict[str, str]:
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
) -> Tuple[str, List[str], Dict[str, str]]:
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

    mineru_request = MinerURequest(file_paths=file_paths)
    try:
        mineru_response, attempt = await _run_async_with_node_policy(
            "parsing",
            "mineru_pipeline",
            lambda: asyncio.to_thread(_mineru.minerU_pipeline, mineru_request),
        )
    except Exception as mineru_exc:
        logger.warning("MinerU failed, attempting PaddleOCR fallback: {}", mineru_exc)
        try:
            mineru_response = run_paddleocr_fallback(file_paths)
            attempt = 1
        except Exception as ocr_exc:
            _log_node_end(
                postgres,
                paper_task_id,
                "parsing",
                success=False,
                error_code="PARSE_FAILED",
                message=f"MinerU + PaddleOCR both failed: {ocr_exc}",
            )
            raise exc.ParsingException(f"All parsers failed: {ocr_exc}") from ocr_exc

    if not mineru_response or not mineru_response.folder_path:
        _log_node_end(
            postgres,
            paper_task_id,
            "parsing",
            success=False,
            error_code="PARSE_FAILED",
            message="Parser returned no folder",
        )
        raise exc.ParsingException("Parser returned no folder")

    md_content, image_paths = _collect_mineru_assets(mineru_response.folder_path)
    _log_node_end(postgres, paper_task_id, "parsing", success=True, attempt=attempt)
    return md_content, image_paths, _update_node_trace(node_trace, "parsing", "success")


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

    if paper_task_id:
        try:
            postgres = get_postgres_client()
            postgres.update_paper_task(paper_task_id, status="running")
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
            logger.warning("Unable to mark paper task {} running: {}", paper_task_id, init_exc)

    try:
        _disable_proxies()

        try:
            asyncio.run(init_knowledge_base_if_needed())
        except Exception as kb_exc:
            logger.exception("Knowledge base init failed, continue: {}", kb_exc)

        if postgres is None:
            postgres = get_postgres_client()

        # --- Node 1: Acquisition ---
        validated_paths, node_trace = run_node_acquisition(
            postgres,
            paper_task_id or "",
            file_paths,
            node_trace,
        )

        # --- Node 2: Parsing ---
        md_content, image_paths, node_trace = asyncio.run(
            run_node_parsing(postgres, paper_task_id or "", validated_paths, node_trace)
        )

        # --- Node 3: Translation ---
        source_text, en_text, node_trace, translation_warnings = run_node_translation(
            postgres,
            paper_task_id or "",
            md_content,
            node_trace,
        )

        # --- Node 4: Extraction ---
        agent_response, node_trace = run_node_extraction(
            postgres,
            paper_task_id or "",
            source_text,
            en_text,
            image_paths,
            node_trace,
        )

        # Store outputs in MinIO
        saved_files = asyncio.run(_store_outputs_in_minio(agent_response, image_paths, document_id))

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

        payload: Dict[str, Any]
        result = PipelineResult(
            document_id=document_id,
            output_dir=f"{cfg.minio_results_bucket}/{document_id}",
            mineru_folder="",
            files=saved_files,
            evidence=agent_response,
        )
        if hasattr(result, "model_dump"):
            payload = result.model_dump()
        else:
            payload = result  # type: ignore[assignment]
        if isinstance(payload, dict):
            if file_size_bytes is not None:
                payload.setdefault("file_size_bytes", file_size_bytes)
            payload.setdefault("processing_duration_seconds", processing_duration_seconds)
            payload.setdefault("created_at", start_time.isoformat())
            payload.setdefault("updated_at", end_time.isoformat())
            if graph_sync_result is not None:
                payload["graph_sync_result"] = graph_sync_result

        if paper_task_id and postgres is not None:
            try:
                warning_codes = _persist_alignments_and_warnings(
                    postgres,
                    paper_task_id,
                    source_text=source_text,
                    en_text=en_text,
                    base_warnings=translation_warnings,
                )
                postgres.update_paper_task(
                    paper_task_id,
                    status="success",
                    error_code=None,
                    warning_codes=warning_codes or None,
                    node_trace=node_trace,
                )
                postgres.append_paper_task_log(
                    paper_task_id,
                    status="success",
                    node="acmg",
                    message="Paper task completed",
                )
                if request_id:
                    postgres.refresh_task_request_status(request_id)
            except Exception as success_exc:
                logger.warning(
                    "Unable to mark paper task {} success: {}", paper_task_id, success_exc
                )

        if file_hash:
            try:
                cache_pdf_result(file_hash, payload)
            except Exception as cache_exc:
                logger.warning("Failed to cache result for hash {}: {}", file_hash, cache_exc)

        tmp_dir = Path(os.environ.get("PWD", str(Path.cwd()))) / "tmp"
        file_utils.cleanup_old_temp_folders(str(tmp_dir), keep_latest=3)

        logger.debug("Celery task complete")
        return payload
    except Exception as exc_outer:
        if paper_task_id and postgres is not None:
            try:
                retry_count = int(getattr(self.request, "retries", 0))
                max_retries = int(getattr(self, "max_retries", 0))
                if retry_count >= max_retries:
                    error_code = map_error_code(500, str(exc_outer))
                    postgres.update_paper_task(
                        paper_task_id,
                        status="failed",
                        error_code=error_code,
                        node_trace=node_trace,
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
                logger.warning("Unable to mark paper task {} failed: {}", paper_task_id, mark_exc)
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
    node_trace: Dict[str, str] = {}

    postgres.update_paper_task(
        paper_task_id,
        status="running",
        fulltext_unavailable="true",
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
    try:
        article, acquisition_attempt = asyncio.run(
            _run_async_with_node_policy(
                "acquisition",
                "fetch_pubmed_metadata_abstract",
                lambda: get_pubmed_service().fetch_article_metadata_abstract(pmid),
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
            error_code=map_error_code(500, f"Fetch timeout while querying PubMed: {acq_exc}"),
            message=f"PubMed fetch failed: {acq_exc}",
        )
        node_trace = _update_node_trace(node_trace, "acquisition", "failed")
        retry_count = int(getattr(self.request, "retries", 0))
        max_retries = int(getattr(self, "max_retries", 0))
        if retry_count >= max_retries:
            error_code = map_error_code(500, f"Fetch timeout while querying PubMed: {acq_exc}")
            postgres.update_paper_task(
                paper_task_id,
                status="failed",
                error_code=error_code,
                node_trace=node_trace,
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
            error_code=error_code,
            node_trace=node_trace,
        )
        postgres.refresh_task_request_status(request_id)
        return {
            "pmid": pmid,
            "document_id": document_id,
            "paper_task_id": paper_task_id,
            "status": "failed",
            "error_code": error_code,
        }

    markdown_content = (
        f"# {article.title or f'PMID:{pmid}'}\n\n"
        f"- PMID: {article.pmid}\n"
        f"- Journal: {article.journal}\n"
        f"- Published: {article.pub_date}\n\n"
        f"## Abstract\n\n{article.abstract or ''}"
    )

    # --- Node 2: Parsing (skipped — metadata/abstract fallback) ---
    node_trace = _update_node_trace(node_trace, "parsing", "fallback_metadata_abstract")

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
                error_code=error_code,
                node_trace=node_trace,
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
                error_code=error_code,
                node_trace=node_trace,
            )
            postgres.refresh_task_request_status(request_id)
        raise

    if not agent_response or getattr(agent_response, "status", None) == "failed":
        error_code = "EVIDENCE_EXTRACTION_FAILED"
        postgres.update_paper_task(
            paper_task_id,
            status="failed",
            error_code=error_code,
            node_trace=node_trace,
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

    base_warnings = ["FULLTEXT_UNAVAILABLE"] + translation_warnings
    warning_codes = _persist_alignments_and_warnings(
        postgres,
        paper_task_id,
        source_text=source_text,
        en_text=en_text,
        base_warnings=base_warnings,
    )

    postgres.update_document(
        document_id,
        status="success",
        summary=f"PubMed metadata/abstract fallback used for PMID:{pmid}",
    )
    postgres.update_paper_task(
        paper_task_id,
        status="success",
        error_code=None,
        node_trace=node_trace,
        warning_codes=warning_codes,
    )
    postgres.append_paper_task_log(
        paper_task_id,
        status="success",
        node="acmg",
        message=f"PubMed fallback completed for PMID:{pmid}",
        payload={
            "fulltext_unavailable": True,
            "graph_sync_result": graph_sync_result,
        },
    )
    postgres.refresh_task_request_status(request_id)
    return {
        "pmid": pmid,
        "document_id": document_id,
        "paper_task_id": paper_task_id,
        "fulltext_unavailable": True,
        "status": "success",
        "files": files.model_dump() if hasattr(files, "model_dump") else files,
        "graph_sync_result": graph_sync_result,
    }
