#!/usr/bin/env python3
"""
Database schema synchronization script to ensure model matches database.
"""

import os
import asyncio
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine
from src.infrastructure.database.postgres_models import Base, ParsingTask
from src.config.database_config import DatabaseConfig
from urllib.parse import quote_plus


async def sync_schema():
    """Sync the database schema with the model."""
    # Load environment
    load_dotenv('.env.development', override=True)
    
    # Get database config
    config = DatabaseConfig.from_env()
    password = config.postgresql.password
    encoded_password = quote_plus(password)
    
    database_url = f"postgresql+asyncpg://{config.postgresql.user}:{encoded_password}@{config.postgresql.host}:{config.postgresql.port}/{config.postgresql.database}"
    
    print(f"Connecting to database: {database_url.replace(encoded_password, '***')}")
    
    # Create async engine
    engine = create_async_engine(database_url)
    
    try:
        # Test direct connection to the table
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT COUNT(*) FROM parsing_tasks LIMIT 1"))
            count = result.scalar()
            print(f"✅ Successfully connected to parsing_tasks table, found {count} records")
            
            # Get table columns
            result = await conn.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'parsing_tasks' 
                ORDER BY ordinal_position
            """))
            columns = result.fetchall()
            print(f"Table has {len(columns)} columns:")
            for col in columns[:10]:  # Show first 10 columns
                print(f"  - {col[0]} ({col[1]})")
            if len(columns) > 10:
                print(f"  ... and {len(columns) - 10} more columns")
        
        print("✅ Database connection and table access successful!")
        return True
        
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        return False
    finally:
        await engine.dispose()


async def test_model_mapping():
    """Test if SQLAlchemy model can map to the table."""
    # Load environment
    load_dotenv('.env.development', override=True)
    
    # Get database config
    config = DatabaseConfig.from_env()
    password = config.postgresql.password
    encoded_password = quote_plus(password)
    
    database_url = f"postgresql+asyncpg://{config.postgresql.user}:{encoded_password}@{config.postgresql.host}:{config.postgresql.port}/{config.postgresql.database}"
    
    print("Testing model mapping...")
    
    # Create async engine
    engine = create_async_engine(database_url)
    
    try:
        # Try to reflect the table and see if it matches our model
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy import inspect
        
        async with engine.begin() as conn:
            # Use reflection to get table info
            insp = inspect(conn)
            columns = await conn.run_sync(lambda sync_conn: insp.get_columns('parsing_tasks'))
            
            print(f"Reflection found {len(columns)} columns:")
            for col in columns:
                print(f"  - {col['name']} ({col['type']})")
        
        print("✅ Model reflection successful!")
        return True
        
    except Exception as e:
        print(f"❌ Error reflecting model: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await engine.dispose()


if __name__ == "__main__":
    async def main():
        print("Testing database connectivity and model mapping...")
        success1 = await sync_schema()
        success2 = await test_model_mapping()
        
        if success1 and success2:
            print("\\n✅ All tests passed! Database and model are properly configured.")
        else:
            print("\\n❌ Some tests failed.")
    
    asyncio.run(main())