from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List, Set, Tuple

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.infrastructure.postgres import get_postgres_client
from src.infrastructure.redis import (
    redis_client,
    PDF_HASH_KEY_PREFIX,
    PDF_RESULT_KEY_PREFIX,
)
from src.infrastructure.minio import MinIOClient
from src.infrastructure.enum import MinioBucketNameEnum
from src.infrastructure.neo4j import get_neo4j_client


def _iter_chunks(items: List[str], size: int) -> Iterable[List[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _fetch_pg_documents(batch_size: int) -> Tuple[Set[str], Set[str]]:
    pg = get_postgres_client()
    doc_ids: Set[str] = set()
    hashes: Set[str] = set()
    offset = 0

    while True:
        docs = pg.list_documents(limit=batch_size, offset=offset)
        if not docs:
            break
        for doc in docs:
            if doc.document_id:
                doc_ids.add(str(doc.document_id))
            if doc.file_hash:
                hashes.add(str(doc.file_hash))
        offset += len(docs)

    return doc_ids, hashes


def _extract_hash(key: str) -> str | None:
    if key.startswith(PDF_RESULT_KEY_PREFIX):
        return key[len(PDF_RESULT_KEY_PREFIX) :]
    if key.startswith(PDF_HASH_KEY_PREFIX):
        return key[len(PDF_HASH_KEY_PREFIX) :]
    return None


def cleanup_redis(valid_hashes: Set[str], apply: bool) -> Tuple[int, int]:
    conn = redis_client.get_connection()
    total = 0
    deleted = 0

    for prefix in (PDF_RESULT_KEY_PREFIX, PDF_HASH_KEY_PREFIX):
        cursor = 0
        pattern = f"{prefix}*"
        while True:
            cursor, keys = conn.scan(cursor=cursor, match=pattern, count=200)
            if not keys and cursor == 0:
                break
            pipe = conn.pipeline()
            batch_deleted = 0
            for raw_key in keys:
                total += 1
                key = raw_key.decode("utf-8") if isinstance(raw_key, bytes) else str(raw_key)
                hash_value = _extract_hash(key)
                if not hash_value or hash_value not in valid_hashes:
                    if apply:
                        pipe.delete(key)
                    batch_deleted += 1
            if apply and batch_deleted:
                pipe.execute()
            deleted += batch_deleted
            if cursor == 0:
                break

    return total, deleted


def cleanup_neo4j(valid_doc_ids: Set[str], apply: bool, batch_size: int) -> Tuple[int, int]:
    neo = get_neo4j_client()
    rows = neo.run_query("MATCH (doc:Document) RETURN doc.document_id AS document_id")
    neo_ids = {str(r.get("document_id")) for r in rows if r.get("document_id")}
    missing = sorted(neo_ids - valid_doc_ids)

    deleted = 0
    if not apply:
        return len(missing), deleted

    for batch in _iter_chunks(missing, batch_size):
        neo.run_query(
            "MATCH (doc:Document) WHERE doc.document_id IN $ids DETACH DELETE doc",
            {"ids": batch},
        )
        deleted += len(batch)

    return len(missing), deleted


def _cleanup_minio_bucket(
    minio_client: MinIOClient,
    bucket: str,
    valid_prefixes: Set[str],
    apply: bool,
) -> Tuple[int, int]:
    total = 0
    deleted = 0
    for obj in minio_client.client.list_objects(bucket_name=bucket, recursive=True):
        object_name = obj.object_name
        total += 1
        prefix = object_name.split("/", 1)[0]
        if prefix not in valid_prefixes:
            if apply:
                minio_client.client.remove_object(bucket_name=bucket, object_name=object_name)
            deleted += 1
    return total, deleted


def cleanup_minio(valid_doc_ids: Set[str], valid_hashes: Set[str], apply: bool) -> Tuple[int, int, int, int]:
    minio_client = MinIOClient()
    uploads_bucket = MinioBucketNameEnum.LITERATURE_UPLOADS.value
    results_bucket = MinioBucketNameEnum.PROCESSED_RESULTS.value

    uploads_total, uploads_deleted = _cleanup_minio_bucket(
        minio_client,
        uploads_bucket,
        valid_hashes,
        apply,
    )
    results_total, results_deleted = _cleanup_minio_bucket(
        minio_client,
        results_bucket,
        valid_doc_ids,
        apply,
    )
    return uploads_total, uploads_deleted, results_total, results_deleted


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cleanup orphaned resources across PostgreSQL/Redis/Neo4j/MinIO",
    )
    parser.add_argument("--apply", action="store_true", help="Perform deletions")
    parser.add_argument("--batch-size", type=int, default=500, help="Neo4j delete batch size")
    parser.add_argument("--skip-redis", action="store_true", help="Skip Redis cleanup")
    parser.add_argument("--skip-neo4j", action="store_true", help="Skip Neo4j cleanup")
    parser.add_argument("--skip-minio", action="store_true", help="Skip MinIO cleanup")
    parser.add_argument("--pg-batch-size", type=int, default=500, help="PostgreSQL scan batch size")
    args = parser.parse_args()

    apply = args.apply
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"Mode: {mode}")

    doc_ids, hashes = _fetch_pg_documents(args.pg_batch_size)
    print(f"PostgreSQL documents: {len(doc_ids)} | hashes: {len(hashes)}")

    if not args.skip_redis:
        redis_total, redis_deleted = cleanup_redis(hashes, apply)
        print(f"Redis scanned: {redis_total} | delete: {redis_deleted}")

    if not args.skip_neo4j:
        neo_missing, neo_deleted = cleanup_neo4j(doc_ids, apply, args.batch_size)
        print(f"Neo4j missing docs: {neo_missing} | delete: {neo_deleted}")

    if not args.skip_minio:
        up_total, up_deleted, res_total, res_deleted = cleanup_minio(doc_ids, hashes, apply)
        print(
            "MinIO uploads scanned: {} | delete: {} | results scanned: {} | delete: {}".format(
                up_total, up_deleted, res_total, res_deleted
            )
        )

    if not apply:
        print("Dry-run only. Re-run with --apply to execute deletions.")


if __name__ == "__main__":
    main()

#示例用法:
# 1. 先进行一次干运行，查看将要删除的资源数量：
#    python cleanup_orphan_resources.py
#
# 2. 确认无误后，执行删除操作：
#    python cleanup_orphan_resources.py --apply
# 3. 如果数据量较大，可以分批删除Neo4j节点：
#    python cleanup_orphan_resources.py --apply --batch-size 200
# 4. 如果只想清理MinIO资源，可以跳过Redis和Neo4j的清理：
#    python cleanup_orphan_resources.py --apply --skip-redis --skip-neo4j
# 5. 如果只想清理Redis资源，可以跳过Neo4j和MinIO的清理：
#    python cleanup_orphan_resources.py --apply --skip-neo4j --skip-minio
# 6. 如果只想清理Neo4j资源，可以跳过Redis和MinIO的清理：
#    python cleanup_orphan_resources.py --apply --skip-redis --skip-minio
# 7. 调整PostgreSQL扫描批次大小以适应不同规模的数据：
#    python cleanup_orphan_resources.py --apply --pg-batch-size 1000
# 注意：执行删除操作前务必做好数据备份，以防误删重要数据！  
