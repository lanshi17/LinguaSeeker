import json
import sys
from pathlib import Path
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.infrastructure.postgres import get_postgres_client
from src.infrastructure.redis import (
    redis_client,
    PDF_RESULT_KEY_PREFIX,
    PDF_HASH_KEY_PREFIX,
)


def _extract_hash(key: str) -> Optional[str]:
    if key.startswith(PDF_RESULT_KEY_PREFIX):
        return key[len(PDF_RESULT_KEY_PREFIX) :]
    return None


def main() -> None:
    conn = redis_client.get_connection()
    postgres_client = get_postgres_client()

    try:
        ping_ok = conn.ping()
    except Exception as exc:
        print(f"Redis ping failed: {exc}")
        raise SystemExit(1)

    print(f"Redis ping: {ping_ok}")

    cursor = 0
    scanned = 0
    deleted = 0
    missing_document_id = 0
    bad_payload = 0

    pattern = f"{PDF_RESULT_KEY_PREFIX}*"
    while True:
        cursor, keys = conn.scan(cursor=cursor, match=pattern, count=200)
        if not keys and cursor == 0:
            break
        raw_values = conn.mget(keys)
        pipe = conn.pipeline()
        batch_deleted = 0

        for key, raw in zip(keys, raw_values):
            scanned += 1
            payload = None
            if raw:
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    bad_payload += 1
            else:
                bad_payload += 1

            key_str = key.decode("utf-8") if isinstance(key, bytes) else str(key)
            hash_value = _extract_hash(key_str)

            cached_has_id = False
            if isinstance(payload, dict):
                cached_has_id = payload.get("document_id") is not None

            db_has_id = False
            if hash_value:
                try:
                    cached_document = postgres_client.find_document_by_hash(hash_value)
                    db_has_id = cached_document is not None
                except Exception:
                    db_has_id = False

            if not cached_has_id or not db_has_id:
                missing_document_id += 1
                if hash_value:
                    hash_key = f"{PDF_HASH_KEY_PREFIX}{hash_value}"
                    pipe.delete(key_str, hash_key)
                else:
                    pipe.delete(key_str)
                batch_deleted += 1

        if batch_deleted:
            pipe.execute()
            deleted += batch_deleted

        if cursor == 0:
            break

    print(
        "Scanned:", scanned,
        "| Missing document_id:", missing_document_id,
        "| Bad payload:", bad_payload,
        "| Deleted:", deleted,
    )


if __name__ == "__main__":
    main()
