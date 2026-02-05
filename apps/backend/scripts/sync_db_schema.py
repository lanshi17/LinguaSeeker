#!/usr/bin/env python3
"""
Database schema synchronization script.
This script synchronizes the database schema with the application models.
"""

import os
import asyncio
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine
from src.infrastructure.database.postgres_models import Base


def sync_database_schema():
    """Synchronize database schema with application models."""
    # Load development environment variables
    load_dotenv('.env.development', override=True)
    
    # Get database URL with proper URL encoding for special characters in password
    import urllib.parse
    password = os.getenv('POSTGRES_PASSWORD')
    encoded_password = urllib.parse.quote_plus(password)  # Properly encode special characters
    database_url = f"postgresql://{os.getenv('POSTGRES_USER')}:{encoded_password}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB')}"
    
    print(f"Connecting to database: {database_url.replace(encoded_password, '***')}")
    
    # Create sync engine to execute DDL statements
    engine = create_engine(database_url)
    
    try:
        print("Synchronizing database schema with application models...")
        
        # Create all tables (this will only create missing tables or columns)
        Base.metadata.create_all(engine)
        
        print("✅ Database schema synchronized successfully!")
        
        # Print table information
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'parsing_tasks'
                ORDER BY ordinal_position;
            """))
            
            print("\\nColumns in parsing_tasks table:")
            for row in result:
                print(f"- {row[0]} ({row[1]}, nullable: {row[2]})")
        
        return True
        
    except Exception as e:
        print(f"❌ Error synchronizing database schema: {e}")
        return False
    finally:
        engine.dispose()


if __name__ == "__main__":
    success = sync_database_schema()
    if success:
        print("\\n✅ Database schema synchronization completed successfully!")
    else:
        print("\\n❌ Database schema synchronization failed!")
        exit(1)