#!/usr/bin/env python3
"""
Test script to verify database connectivity with correct credentials.
"""

import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from src.infrastructure.database.postgres_models import Base


async def test_db_connection():
    """Test database connection with the correct credentials."""
    # Explicitly set environment variables for this test
    os.environ['POSTGRES_USER'] = 'yangzs'
    os.environ['POSTGRES_PASSWORD'] = 'xxxxxxxxxx'
    os.environ['POSTGRES_HOST'] = 'localhost'
    os.environ['POSTGRES_PORT'] = '5432'
    os.environ['POSTGRES_DB'] = 'acmg_ps3'
    
    # Get database URL from environment
    database_url = f"postgresql+asyncpg://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    
    print(f"Testing connection to: {database_url.replace(os.getenv('POSTGRES_PASSWORD'), '***')}")
    
    # Create async engine
    engine = create_async_engine(database_url)
    
    try:
        # Test connection by executing a simple query
        async with engine.connect() as conn:
            result = await conn.execute("SELECT 1")
            row = result.fetchone()
            print(f"✅ Database connection successful! Result: {row}")
            
            # Try to check if tables exist
            from sqlalchemy import text
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            tables = [row[0] for row in result]
            if tables:
                print(f"Existing tables: {tables}")
            else:
                print("No tables found in database")
                
            return True
            
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False
    finally:
        await engine.dispose()


async def create_tables_if_needed():
    """Create tables if they don't exist."""
    # Set environment variables
    os.environ['POSTGRES_USER'] = 'yangzs'
    os.environ['POSTGRES_PASSWORD'] = 'xxxxxx'
    os.environ['POSTGRES_HOST'] = 'localhost'
    os.environ['POSTGRES_PORT'] = '5432'
    os.environ['POSTGRES_DB'] = 'acmg_ps3'
    
    # Get database URL from environment
    database_url = f"postgresql+asyncpg://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    
    print(f"Creating tables using: {database_url.replace(os.getenv('POSTGRES_PASSWORD'), '***')}")
    
    # Create async engine
    engine = create_async_engine(database_url)
    
    try:
        # Create all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        print("✅ Database tables created successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error creating database tables: {e}")
        return False
    finally:
        await engine.dispose()


async def main():
    print("Testing database connection...")
    success = await test_db_connection()
    
    if success:
        print("\nCreating tables if needed...")
        await create_tables_if_needed()
    else:
        print("\nSkipping table creation due to connection failure.")
    

if __name__ == "__main__":
    asyncio.run(main())