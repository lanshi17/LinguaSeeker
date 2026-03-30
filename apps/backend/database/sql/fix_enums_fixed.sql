-- Emergency fix for enum types required by the application
-- This script ensures all enum types have the exact values required by the backend code

-- First, let's check what enum values currently exist
\echo 'Current enum values in the database:'
SELECT 
    t.typname AS enum_name,
    ARRAY_AGG(e.enumlabel ORDER BY e.enumsortorder) AS enum_values
FROM 
    pg_type t 
    JOIN pg_enum e ON t.oid = e.enumtypid
WHERE 
    t.typname IN ('tasktype', 'taskstage', 'taskstatus')
GROUP BY 
    t.typname
ORDER BY 
    t.typname;

-- Create tasktype enum if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tasktype') THEN
        CREATE TYPE tasktype AS ENUM ('PDF_PARSE', 'IDENTIFIER_RESOLVE', 'DATA_EXTRACTION');
        RAISE NOTICE 'Created tasktype enum with values: PDF_PARSE, IDENTIFIER_RESOLVE, DATA_EXTRACTION';
    ELSE
        RAISE WARNING 'tasktype enum already exists. Due to PostgreSQL limitations, existing enum values cannot be altered directly with ALTER TYPE.';
        RAISE WARNING 'If the existing values differ from required values, manual migration is needed.';
    END IF;
END$$;

-- Add missing values to taskstage enum
DO $$
DECLARE
    enum_value TEXT;
BEGIN
    BEGIN
        ALTER TYPE taskstage ADD VALUE IF NOT EXISTS 'PROCESSING';
    EXCEPTION
        WHEN duplicate_object THEN
            RAISE NOTICE 'Value PROCESSING already exists in taskstage enum';
    END;

    BEGIN
        ALTER TYPE taskstage ADD VALUE IF NOT EXISTS 'FAILED';
    EXCEPTION
        WHEN duplicate_object THEN
            RAISE NOTICE 'Value FAILED already exists in taskstage enum';
    END;
END$$;

-- Add missing values to taskstatus enum
DO $$
DECLARE
BEGIN
    BEGIN
        ALTER TYPE taskstatus ADD VALUE IF NOT EXISTS 'RUNNING';
    EXCEPTION
        WHEN duplicate_object THEN
            RAISE NOTICE 'Value RUNNING already exists in taskstatus enum';
    END;

    BEGIN
        ALTER TYPE taskstatus ADD VALUE IF NOT EXISTS 'SUCCESS';
    EXCEPTION
        WHEN duplicate_object THEN
            RAISE NOTICE 'Value SUCCESS already exists in taskstatus enum';
    END;

    BEGIN
        ALTER TYPE taskstatus ADD VALUE IF NOT EXISTS 'ERROR';
    EXCEPTION
        WHEN duplicate_object THEN
            RAISE NOTICE 'Value ERROR already exists in taskstatus enum';
    END;
END$$;

-- Show final state of enum values
\echo ''
\echo 'Final enum values in the database after updates:'
SELECT 
    t.typname AS enum_name,
    ARRAY_AGG(e.enumlabel ORDER BY e.enumsortorder) AS enum_values
FROM 
    pg_type t 
    JOIN pg_enum e ON t.oid = e.enumtypid
WHERE 
    t.typname IN ('tasktype', 'taskstage', 'taskstatus')
GROUP BY 
    t.typname
ORDER BY 
    t.typname;

\echo ''
\echo 'Enum types have been updated to include all required values.'
\echo 'Note: PostgreSQL enum values cannot be removed, only added. If existing values'
\echo 'are incompatible with the application, a table migration may be required.'