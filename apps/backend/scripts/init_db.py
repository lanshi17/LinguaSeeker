#!/usr/bin/env python3
"""
Script to initialize the database schema.
This creates all necessary tables in the PostgreSQL database.
"""

import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from src.infrastructure.database.postgres_models import Base


async def init_db():
    """Initialize the database with all required tables."""
    # Get database URL from environment or use default
    database_url = os.getenv(
        "DATABASE_URL",
        f"postgresql+asyncpg://{os.getenv('POSTGRES_USER', 'postgres')}:{os.getenv('POSTGRES_PASSWORD', 'your-postgres-password')}@{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'acmg_ps3')}"
    )
    
    print(f"Connecting to database: {database_url.replace(os.getenv('POSTGRES_PASSWORD', 'your-postgres-password'), '***')}")
    
    # Create async engine
    engine = create_async_engine(database_url)
    
    try:
        # Create all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        print("Database tables created successfully!")
        
    except Exception as e:
        print(f"Error creating database tables: {e}")
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_db())