from pathlib import Path
import asyncio
import os
import sys
from uuid import uuid4
from typing import Any, Dict, List, Optional
import mimetypes

from loguru import logger

# Ensure the project root (which contains the `src` package) is importable when this file
# is invoked directly with `python -m src.service.tasks` or similar.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.domain.mineru import MinerUComponent
from src.domain.agents import EvidenceAgent
from src.domain.models import (
    EvidenceOutput,
    MinerURequest,
    MinerUResponse,
    PipelineFiles,
    PipelineResult,
)
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
    else:
        logger.info("Collection {} exists, skipping init.", cfg.qdrant_collection_name)
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

    document_id = str(uuid4())

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


@celery_app.task(name="tasks.process_pdf")
def process_pdf_task(
    file_paths: List[str],
    output_root: Optional[str] = None,
    file_hash: Optional[str] = None,
) -> Dict[str, Any]:
    logger.debug(
        "Celery task start file_paths: {} output_root: {} file_hash: {}",
        file_paths,
        output_root,
        file_hash,
    )
    resolved_output_root = Path(output_root) if output_root else None
    result = asyncio.run(run_fastapi_pipeline(file_paths, output_root=resolved_output_root))
    payload: Dict[str, Any]
    if hasattr(result, "model_dump"):
        payload = result.model_dump()
    else:
        payload = result
    if file_hash:
        try:
            cache_pdf_result(file_hash, payload)
        except Exception as exc:
            logger.warning("Failed to cache result for hash {}: {}", file_hash, exc)
    logger.debug("Celery task complete")
    return payload

