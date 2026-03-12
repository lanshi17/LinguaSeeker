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

-- Handle taskstage enum - since it exists with different values, we need to add missing values
DO $$
DECLARE
    enum_exists BOOLEAN;
    required_values TEXT[] := ARRAY['INGESTION', 'PROCESSING', 'COMPLETED', 'FAILED'];
    current_values TEXT[];
    missing_values TEXT[];
BEGIN
    SELECT EXISTS(SELECT 1 FROM pg_type WHERE typname = 'taskstage') INTO enum_exists;
    
    IF enum_exists THEN
        SELECT ARRAY_AGG(e.enumlabel ORDER BY e.enumsortorder)
        INTO current_values
        FROM pg_enum e
        JOIN pg_type t ON t.oid = e.enumtypid
        WHERE t.typname = 'taskstage';
        
        -- Find missing values
        SELECT ARRAY(
            SELECT unnest(required_values)
            EXCEPT
            SELECT unnest(current_values)
        ) INTO missing_values;
        
        -- Add missing values
        IF array_length(missing_values, 1) > 0 THEN
            FOREACH enum_val IN ARRAY missing_values
            LOOP
                EXECUTE format('ALTER TYPE taskstage ADD VALUE IF NOT EXISTS %L', enum_val);
                RAISE NOTICE 'Added value % to taskstage enum', enum_val;
            END LOOP;
        ELSE
            RAISE NOTICE 'taskstage enum already contains all required values';
        END IF;
    ELSE
        RAISE WARNING 'taskstage enum does not exist, which is unexpected based on our check';
    END IF;
END$$;

-- Handle taskstatus enum - since it exists with different values, we need to add missing values
DO $$
DECLARE
    enum_exists BOOLEAN;
    required_values TEXT[] := ARRAY['PENDING', 'RUNNING', 'SUCCESS', 'ERROR'];
    current_values TEXT[];
    missing_values TEXT[];
BEGIN
    SELECT EXISTS(SELECT 1 FROM pg_type WHERE typname = 'taskstatus') INTO enum_exists;
    
    IF enum_exists THEN
        SELECT ARRAY_AGG(e.enumlabel ORDER BY e.enumsortorder)
        INTO current_values
        FROM pg_enum e
        JOIN pg_type t ON t.oid = e.enumtypid
        WHERE t.typname = 'taskstatus';
        
        -- Find missing values
        SELECT ARRAY(
            SELECT unnest(required_values)
            EXCEPT
            SELECT unnest(current_values)
        ) INTO missing_values;
        
        -- Add missing values
        IF array_length(missing_values, 1) > 0 THEN
            FOREACH enum_val IN ARRAY missing_values
            LOOP
                EXECUTE format('ALTER TYPE taskstatus ADD VALUE IF NOT EXISTS %L', enum_val);
                RAISE NOTICE 'Added value % to taskstatus enum', enum_val;
            END LOOP;
        ELSE
            RAISE NOTICE 'taskstatus enum already contains all required values';
        END IF;
    ELSE
        RAISE WARNING 'taskstatus enum does not exist, which is unexpected based on our check';
    END IF;
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