from pathlib import Path
import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

# Ensure the project root (which contains the `src` package) is importable when this file
# is invoked directly with `python -m src.service.tasks` or similar.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from component.mineru import MinerUComponent
from component.agents import EvidenceAgent
from component.models import EvidenceOutput, MinerURequest, MinerUResponse
from src.database.qdrant_client import QdrantManager, initialize_knowledge_base
from utils.timer import Timer
import utils.exceptions as exc
import utils.file_utils as file_utils
from config import settings


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


def _prepare_output_dir(output_root: Optional[Path]) -> Path:
    root = output_root or (Path.cwd() / "demo_output")
    run_dir = root / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    file_utils.ensure_directory_exists(str(run_dir))
    return run_dir


def _save_outputs(
    agent_response: EvidenceOutput,
    origin_image_paths: List[str],
    output_dir: Path,
) -> Dict[str, str]:
    origin_md_path = output_dir / "original_format.md"
    origin_md_path.write_text(agent_response.origin_format_md or "", encoding="utf-8")

    en_md_path = output_dir / "en_format.md"
    en_md_path.write_text(agent_response.en_format_md or "", encoding="utf-8")

    image_desc_path = output_dir / "image_descriptions.txt"
    with image_desc_path.open("w", encoding="utf-8") as f:
        for desc in agent_response.image_descriptions or []:
            f.write(desc + "\n")

    output_image_dir = output_dir / "images"
    file_utils.ensure_directory_exists(str(output_image_dir))
    for img_path in origin_image_paths:
        file_utils.copy_file_to_directory(img_path, str(output_image_dir))

    ps3_evidence_path = output_dir / "ps3_evidence.json"
    with ps3_evidence_path.open("w", encoding="utf-8") as f:
        json.dump(agent_response.ps3_evidence, f, ensure_ascii=False, indent=4)

    return {
        "origin_md_path": str(origin_md_path),
        "en_md_path": str(en_md_path),
        "image_desc_path": str(image_desc_path),
        "ps3_evidence_path": str(ps3_evidence_path),
        "image_dir": str(output_image_dir),
    }


async def run_fastapi_pipeline(
    file_paths: List[str],
    output_root: Optional[Path] = None,
    keep_tmp_runs: int = 3,
    hash_file_paths: bool = False,
) -> Dict[str, Any]:
    """FastAPI-friendly pipeline wrapper based on pipline.py."""
    if not file_paths:
        raise exc.ValidationException("file_paths is empty")

    _disable_proxies()

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

        output_dir = _prepare_output_dir(output_root)
        saved_files = _save_outputs(agent_response, origin_image_paths, output_dir)

        tmp_dir = Path.cwd() / "tmp"
        file_utils.cleanup_old_temp_folders(str(tmp_dir), keep_latest=keep_tmp_runs)

        return {
            "output_dir": str(output_dir),
            "mineru_folder": mineru_response.folder_path,
            "files": saved_files,
            "evidence": agent_response.model_dump(),
        }

