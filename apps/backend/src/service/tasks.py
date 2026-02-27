import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Any, Dict, List, Optional
import mimetypes

from loguru import logger

# Ensure the project root (which contains the `src` package) is importable when this file
# is invoked directly with `python -m src.service.tasks` or similar.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.domain.mineru.component import MinerUComponent
from src.domain.agent.workflow import EvidenceAgent
from src.domain.models import (
    EvidenceOutput,
    MinerURequest,
    MinerUResponse,
    PipelineFiles,
    PipelineResult,
)
from src.domain.graph.sync import SchemaSyncError, get_graph_sync_service
from src.database.qdrant_client import QdrantManager, initialize_knowledge_base
from src.database.minio_client import MinIOClient
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
_REBUILD_EMPTY_KB = getattr(cfg, "rebuild_empty_knowledge_base", False)


def _sync_evidence_to_graph(document_id: str, evidence_output: Any | None) -> Optional[Dict[str, Any]]:
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
				"Graph sync attempt %s/%s failed for document %s: %s",
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
        logger.info("Collection {} missing, initializing knowledge base...", cfg.qdrant_collection_name)
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
    origin_image_paths = [
        str(p) for p in Path(folder_path).rglob("*.jpg") if p.is_file()
    ]
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


async def run_fastapi_pipeline(
    file_paths: List[str],
    output_root: Optional[Path] = None,
    keep_tmp_runs: int = 3,
    hash_file_paths: bool = False,
    document_id: Optional[str] = None,
) -> PipelineResult:
    """FastAPI-friendly pipeline wrapper based on pipline.py."""
    if not file_paths:
        raise exc.ValidationException("file_paths is empty")

    logger.debug(
        "Pipeline start file_paths: {} output_root: {} keep_tmp_runs: {}",
        file_paths,
        str(output_root) if output_root else None,
        keep_tmp_runs,
    )

    _disable_proxies()

    document_id = document_id or str(uuid4())

    with Timer("pipeline_total"):
        try:
            await init_knowledge_base_if_needed()
        except Exception as e:
            logger.exception("Knowledge base init failed, continue: {}", e)

        mineru_request = MinerURequest(file_paths=file_paths)
        mineru_response: Optional[MinerUResponse]
        try:
            mineru_response = await asyncio.to_thread(_mineru.minerU_pipeline, mineru_request)
        except Exception as e:
            logger.exception("MinerU parsing failed: {}", e)
            raise exc.ParsingException(str(e))

        if not mineru_response or not mineru_response.folder_path:
            raise exc.ParsingException("MinerU did not return parsed folder")

        logger.debug("MinerU parsing done, folder: {}", mineru_response.folder_path)
        origin_md_content, origin_image_paths = _collect_mineru_assets(mineru_response.folder_path)
        logger.debug("Markdown preview: {}", origin_md_content[:100])
        logger.debug("Image paths: {}", origin_image_paths)

        try:
            agent_response = await asyncio.to_thread(
                _agents.process_medical_evidence,
                markdown_content=origin_md_content,
                image_paths=origin_image_paths,
            )
        except Exception as e:
            logger.exception("Evidence processing failed: {}", e)
            raise exc.ReasoningException(str(e))

        if not agent_response or getattr(agent_response, "status", None) == "failed":
            raise exc.ReasoningException("Evidence processing failed")

        saved_files = await _store_outputs_in_minio(
            agent_response,
            origin_image_paths,
            document_id,
        )
        logger.debug("Outputs stored in MinIO with document_id: {}", document_id)

        tmp_dir = Path(os.environ.get("PWD", str(Path.cwd()))) / "tmp"
        file_utils.cleanup_old_temp_folders(str(tmp_dir), keep_latest=keep_tmp_runs)
        logger.debug("Temp cleanup complete in {}", str(tmp_dir))

        return PipelineResult(
            document_id=document_id,
            output_dir=f"{cfg.minio_results_bucket}/{document_id}",
            mineru_folder=mineru_response.folder_path,
            files=saved_files,
            evidence=agent_response,
        )


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
        except OSError as exc:
            logger.warning("Unable to read file size for {}: {}", file_path, exc)
    if sized_files == 0:
        file_size_bytes = None
    resolved_output_root = Path(output_root) if output_root else None
    run_kwargs: Dict[str, Any] = {
        "output_root": resolved_output_root,
    }
    if document_id is not None:
        run_kwargs["document_id"] = document_id
    result = asyncio.run(run_fastapi_pipeline(file_paths, **run_kwargs))
    graph_sync_result = _sync_evidence_to_graph(result.document_id, getattr(result, "evidence", None))
    end_time = datetime.now(timezone.utc)
    processing_duration_seconds = (end_time - start_time).total_seconds()
    payload: Dict[str, Any]
    if hasattr(result, "model_dump"):
        payload = result.model_dump()
    else:
        payload = result
    if isinstance(payload, dict):
        if file_size_bytes is not None:
            payload.setdefault("file_size_bytes", file_size_bytes)
        payload.setdefault("processing_duration_seconds", processing_duration_seconds)
        payload.setdefault("created_at", start_time.isoformat())
        payload.setdefault("updated_at", end_time.isoformat())
        if graph_sync_result is not None:
            payload["graph_sync_result"] = graph_sync_result
    if file_hash:
        try:
            cache_pdf_result(file_hash, payload)
        except Exception as exc:
            logger.warning("Failed to cache result for hash {}: {}", file_hash, exc)
    logger.debug("Celery task complete")
    return payload


@celery_app.task(
    name="tasks.retry_graph_sync",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2, "countdown": 60, "queue": "retry"},
    retry_jitter=True,
)
def retry_graph_sync_task(self, document_id: str, evidence_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    logger.info("Quality retry triggered for document {}", document_id)
    return _sync_evidence_to_graph(document_id, evidence_payload)
