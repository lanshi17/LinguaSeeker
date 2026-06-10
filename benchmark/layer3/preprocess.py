"""Preprocess ground truth entries: run Phase 1/2 and save results.

This script prepares Phase 1/2 outputs (translation + evidence extraction)
for ground truth entries, saving them to the ground_truth directory.
The evaluation script can then use these preprocessed results to skip
Phase 1/2 and directly run Phase 3 (standardization).
"""
from __future__ import annotations

import asyncio
import base64
import json
import shutil
import sys
import time
from pathlib import Path

import httpx
import yaml
from loguru import logger

GROUND_TRUTH_DIR = Path(__file__).resolve().parent / "ground_truth"
MAX_POLL_ATTEMPTS = 360  # 30 min max per entry
POLL_INTERVAL_S = 5.0
TERMINAL_STATUSES = {"awaiting_review", "completed", "failed"}


def load_proxy() -> str | None:
    config_path = Path(__file__).resolve().parent.parent.parent / "backend" / "config" / "environments" / "development.yaml"
    if config_path.exists():
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        proxy = cfg.get("network", {}).get("proxy", "")
        if proxy:
            import socket
            from urllib.parse import urlparse
            try:
                parsed = urlparse(proxy)
                host = parsed.hostname
                port = parsed.port or (443 if parsed.scheme == "https" else 80)
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1.0)
                result = sock.connect_ex((host, port))
                sock.close()
                if result != 0:
                    logger.warning("Proxy {} is not reachable, skipping", proxy)
                    return None
            except Exception:
                return None
        return proxy
    return None


async def submit_and_poll_phase12(
    client: httpx.AsyncClient,
    base_url: str,
    md_text: str,
    filename: str,
) -> dict:
    """Submit document and poll until Phase 2 completion."""
    payload = {
        "source_type": "local",
        "mode": "full",
        "filename": filename,
        "pre_parsed_markdown": md_text,
    }

    resp = await client.post(
        f"{base_url}/api/v1/pipeline/run",
        json=payload,
        timeout=60.0,
    )
    resp.raise_for_status()
    data = resp.json()
    status_url = data["status_url"]
    run_id = data.get("processing_run_id")

    logger.info("[{}] Submitted, run_id={}", filename, run_id)

    # Poll until Phase 2 completes (status = awaiting_review means Phase 3 done)
    for attempt in range(MAX_POLL_ATTEMPTS):
        await asyncio.sleep(POLL_INTERVAL_S)
        try:
            resp = await client.get(f"{base_url}{status_url}", timeout=30.0)
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            status_data = resp.json()
            ps = status_data.get("pipeline_status", "")
            phase = status_data.get("current_phase", "")
            logger.debug("[{}] Poll {}: status={}, phase={}", filename, attempt, ps, phase)
            if ps in TERMINAL_STATUSES:
                return status_data
        except Exception as e:
            logger.warning("[{}] Poll error: {}", filename, e)
            continue

    return {"pipeline_status": "timeout", "error_message": "Poll timed out"}


async def preprocess_entry(
    client: httpx.AsyncClient,
    base_url: str,
    entry_id: str,
) -> bool:
    """Preprocess one entry: run Phase 1/2 and save results."""
    entry_dir = GROUND_TRUTH_DIR / entry_id
    source_path = entry_dir / "source.md"

    if not source_path.exists():
        logger.error("[{}] source.md not found", entry_id)
        return False

    md_text = source_path.read_text(encoding="utf-8")
    if len(md_text) < 100:
        logger.error("[{}] source.md too small ({} chars)", entry_id, len(md_text))
        return False

    logger.info("[{}] Starting preprocessing ({} chars)", entry_id, len(md_text))
    t0 = time.time()

    try:
        status_data = await submit_and_poll_phase12(
            client, base_url, md_text, f"{entry_id}.md"
        )
        duration = time.time() - t0
        pipeline_status = status_data.get("pipeline_status", "unknown")
        run_id = status_data.get("processing_run_id")

        logger.info("[{}] Pipeline completed: status={}, duration={:.1f}s", entry_id, pipeline_status, duration)

        if pipeline_status not in ("awaiting_review", "completed"):
            logger.error("[{}] Pipeline failed: {}", entry_id, status_data.get("error_message", "unknown"))
            return False

        # Copy Phase 1/2 outputs to ground_truth
        pipeline_dir = Path("/data/[redacted-user]/Projects/01_ACMG_Lingua/backend/data/pipeline") / run_id
        phase1_dir = pipeline_dir / "phase_1"
        phase2_dir = pipeline_dir / "phase_2"

        if not phase1_dir.exists() or not phase2_dir.exists():
            logger.error("[{}] Phase directories not found", entry_id)
            return False

        # Save preprocessing metadata
        preprocess_meta = {
            "entry_id": entry_id,
            "run_id": run_id,
            "pipeline_status": pipeline_status,
            "duration_s": round(duration, 2),
            "phase_1_files": [],
            "phase_2_files": [],
        }

        # Copy Phase 1 files
        preprocess_dir = entry_dir / "preprocessed"
        preprocess_dir.mkdir(exist_ok=True)
        phase1_out = preprocess_dir / "phase_1"
        phase1_out.mkdir(exist_ok=True)

        for f in phase1_dir.iterdir():
            if f.is_file():
                shutil.copy2(f, phase1_out / f.name)
                preprocess_meta["phase_1_files"].append(f.name)

        # Copy Phase 2 files
        phase2_out = preprocess_dir / "phase_2"
        phase2_out.mkdir(exist_ok=True)

        for f in phase2_dir.iterdir():
            if f.is_file():
                shutil.copy2(f, phase2_out / f.name)
                preprocess_meta["phase_2_files"].append(f.name)

        # Save metadata
        meta_path = preprocess_dir / "preprocess_meta.json"
        meta_path.write_text(json.dumps(preprocess_meta, indent=2), encoding="utf-8")

        logger.info("[{}] Preprocessing complete: {} Phase 1 files, {} Phase 2 files",
                    entry_id, len(preprocess_meta["phase_1_files"]), len(preprocess_meta["phase_2_files"]))
        return True

    except Exception as e:
        logger.error("[{}] Preprocessing error: {}", entry_id, e)
        return False


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Preprocess ground truth entries")
    parser.add_argument("--entries", nargs="+", help="Entry IDs to preprocess")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend API URL")
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")

    # Load entries
    selection_path = GROUND_TRUTH_DIR / "selection.json"
    all_entries = json.loads(selection_path.read_text(encoding="utf-8"))

    if args.entries:
        entries = [e for e in all_entries if e["entry_id"] in args.entries]
    else:
        entries = all_entries[:3]  # Default: first 3

    logger.info("Preprocessing {} entries", len(entries))

    proxy = load_proxy()
    transport_kwargs = {"proxy": proxy} if proxy else {}

    async with httpx.AsyncClient(**transport_kwargs) as client:
        for entry in entries:
            entry_id = entry["entry_id"]
            success = await preprocess_entry(client, args.base_url, entry_id)
            if success:
                logger.info("[{}] ✓ Preprocessed", entry_id)
            else:
                logger.error("[{}] ✗ Failed", entry_id)


if __name__ == "__main__":
    asyncio.run(main())
