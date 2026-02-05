#!/usr/bin/env python3
"""
Database schema patch script.
This script adds missing columns to the parsing_tasks table to match the application model.
"""

import os
import asyncio
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect
from urllib.parse import quote_plus


def patch_parsing_tasks_table():
    """Add missing columns to parsing_tasks table to match application model."""
    # Load development environment variables
    load_dotenv('.env.development', override=True)
    
    # Get database URL with proper URL encoding for special characters in password
    password = os.getenv('POSTGRES_PASSWORD')
    encoded_password = quote_plus(password)  # Properly encode special characters
    database_url = f"postgresql://{os.getenv('POSTGRES_USER')}:{encoded_password}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB')}"
    
    print(f"Connecting to database: {database_url.replace(encoded_password, '***')}")
    
    # Create engine to execute DDL statements
    engine = create_engine(database_url)
    
    try:
        print("Checking current parsing_tasks table structure...")
        
        # Get current columns
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('parsing_tasks')]
        
        print(f"Current columns in parsing_tasks: {columns}")
        
        # Define required columns according to the application model
        required_columns = [
            'id', 'document_id', 'current_stage', 'progress_percentage', 
            'status', 'priority', 'retry_count', 'failure_reason', 
            'started_at', 'completed_at', 'created_at', 'updated_at', 
            'estimated_completion'
        ]
        
        missing_columns = [col for col in required_columns if col not in columns]
        
        if not missing_columns:
            print("✅ All required columns already exist in parsing_tasks table")
            return True
        
        print(f"Missing columns that need to be added: {missing_columns}")
        
        # Connect and add missing columns
        with engine.connect() as conn:
            trans = conn.begin()  # Start transaction
            
            try:
                # Add missing columns one by one
                for col in missing_columns:
                    if col == 'current_stage':
                        conn.execute(text("ALTER TABLE parsing_tasks ADD COLUMN IF NOT EXISTS current_stage VARCHAR(50) DEFAULT 'INGESTION'"))
                    elif col == 'progress_percentage':
                        conn.execute(text("ALTER TABLE parsing_tasks ADD COLUMN IF NOT EXISTS progress_percentage INTEGER DEFAULT 0"))
                    elif col == 'priority':
                        conn.execute(text("ALTER TABLE parsing_tasks ADD COLUMN IF NOT EXISTS priority INTEGER DEFAULT 5"))
                    elif col == 'retry_count':
                        conn.execute(text("ALTER TABLE parsing_tasks ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0"))
                    elif col == 'failure_reason':
                        conn.execute(text("ALTER TABLE parsing_tasks ADD COLUMN IF NOT EXISTS failure_reason TEXT"))
                    elif col == 'started_at':
                        conn.execute(text("ALTER TABLE parsing_tasks ADD COLUMN IF NOT EXISTS started_at TIMESTAMP"))
                    elif col == 'updated_at':
                        conn.execute(text("ALTER TABLE parsing_tasks ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()"))
                    elif col == 'estimated_completion':
                        conn.execute(text("ALTER TABLE parsing_tasks ADD COLUMN IF NOT EXISTS estimated_completion TIMESTAMP"))
                    elif col == 'status':
                        # Check if status column exists but has wrong type
                        if 'status' not in columns:
                            conn.execute(text("ALTER TABLE parsing_tasks ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'pending'"))
                    elif col == 'document_id':
                        # Check if document_id column exists but has wrong type
                        if 'document_id' not in columns:
                            conn.execute(text("ALTER TABLE parsing_tasks ADD COLUMN IF NOT EXISTS document_id UUID NOT NULL"))
                    
                    print(f"✅ Added column: {col}")
                
                trans.commit()
                print("✅ All missing columns added successfully!")
                
                # Verify the changes
                updated_columns = [col['name'] for col in inspector.get_columns('parsing_tasks')]
                still_missing = [col for col in required_columns if col not in updated_columns]
                
                if not still_missing:
                    print("✅ Table structure now matches application model!")
                else:
                    print(f"⚠️  Some columns are still missing: {still_missing}")
                
                return True
                
            except Exception as e:
                trans.rollback()
                print(f"❌ Error during column addition: {e}")
                raise
                
    except Exception as e:
        print(f"❌ Error patching parsing_tasks table: {e}")
        return False
    finally:
        engine.dispose()


if __name__ == "__main__":
    success = patch_parsing_tasks_table()
    if success:
        print("\\n✅ Database schema patching completed successfully!")
    else:
        print("\\n❌ Database schema patching failed!")
        exit(1)