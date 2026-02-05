#!/usr/bin/env python3
"""Bootstrap the PostgreSQL schema to match SQLAlchemy models."""

import asyncio

from dotenv import load_dotenv

from src.infrastructure.database.bootstrap import ensure_database_ready


async def init_db() -> bool:
    """Initialize and validate the database schema using shared bootstrap logic."""

    # Load base env plus development overrides to mirror the FastAPI runtime.
    load_dotenv(".env", override=False)
    load_dotenv(".env.development", override=True)

    return await ensure_database_ready(create_missing=True, raise_on_failure=False)


if __name__ == "__main__":
    success = asyncio.run(init_db())
    if success:
        print("\n✅ Database initialization completed successfully!")
    else:
        print("\n❌ Database initialization failed!")
        exit(1)
