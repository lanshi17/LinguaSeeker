-- Update parsing_tasks table to use proper enum types
-- This script will alter the table columns to use the newly created enum types

-- First, let's backup the current constraint names to drop them
-- Then we'll change the column types to use the enums

-- Step 1: Drop the existing check constraints
ALTER TABLE parsing_tasks DROP CONSTRAINT IF EXISTS parsing_tasks_status_check;
ALTER TABLE parsing_tasks DROP CONSTRAINT IF EXISTS parsing_tasks_task_type_check;

-- Step 2: Rename the existing columns temporarily
ALTER TABLE parsing_tasks RENAME COLUMN task_type TO task_type_old;
ALTER TABLE parsing_tasks RENAME COLUMN status TO status_old;
ALTER TABLE parsing_tasks RENAME COLUMN current_stage TO current_stage_old;

-- Step 3: Add new columns with enum types
ALTER TABLE parsing_tasks ADD COLUMN task_type tasktype;
ALTER TABLE parsing_tasks ADD COLUMN status taskstatus;
ALTER TABLE parsing_tasks ADD COLUMN current_stage taskstage;

-- Step 4: Copy data from old columns to new enum columns
-- Note: This assumes the string values match the enum values
UPDATE parsing_tasks SET 
    task_type = CASE 
        WHEN UPPER(task_type_old) = 'PDF_PARSE' THEN 'PDF_PARSE'::tasktype
        WHEN UPPER(task_type_old) = 'IDENTIFIER_RESOLVE' THEN 'IDENTIFIER_RESOLVE'::tasktype
        WHEN UPPER(task_type_old) = 'DATA_EXTRACTION' THEN 'DATA_EXTRACTION'::tasktype
        ELSE 'PDF_PARSE'::tasktype  -- Default fallback
    END,
    status = CASE 
        WHEN UPPER(status_old) = 'PENDING' THEN 'PENDING'::taskstatus
        WHEN UPPER(status_old) = 'RUNNING' THEN 'RUNNING'::taskstatus
        WHEN UPPER(status_old) = 'PROCESSING' THEN 'PROCESSING'::taskstatus
        WHEN UPPER(status_old) = 'SUCCESS' THEN 'SUCCESS'::taskstatus
        WHEN UPPER(status_old) = 'COMPLETED' THEN 'COMPLETED'::taskstatus
        WHEN UPPER(status_old) = 'FAILED' THEN 'FAILED'::taskstatus
        WHEN UPPER(status_old) = 'ERROR' THEN 'ERROR'::taskstatus
        ELSE 'PENDING'::taskstatus  -- Default fallback
    END,
    current_stage = CASE 
        WHEN UPPER(current_stage_old) = 'INGESTION' THEN 'INGESTION'::taskstage
        WHEN UPPER(current_stage_old) = 'PROCESSING' THEN 'PROCESSING'::taskstage
        WHEN UPPER(current_stage_old) = 'COMPLETED' THEN 'COMPLETED'::taskstage
        WHEN UPPER(current_stage_old) = 'FAILED' THEN 'FAILED'::taskstage
        ELSE 'INGESTION'::taskstage  -- Default fallback
    END;

-- Step 5: Make the new enum columns NOT NULL where appropriate
ALTER TABLE parsing_tasks ALTER COLUMN task_type SET NOT NULL;
ALTER TABLE parsing_tasks ALTER COLUMN status SET NOT NULL;

-- Step 6: Set appropriate defaults
ALTER TABLE parsing_tasks ALTER COLUMN status SET DEFAULT 'PENDING';
ALTER TABLE parsing_tasks ALTER COLUMN current_stage SET DEFAULT 'INGESTION';

-- Step 7: Drop the old columns
ALTER TABLE parsing_tasks DROP COLUMN task_type_old;
ALTER TABLE parsing_tasks DROP COLUMN status_old;
ALTER TABLE parsing_tasks DROP COLUMN current_stage_old;

-- Step 8: Add foreign key constraints back if needed
-- The original foreign key constraint is still there for document_id

\echo 'Table parsing_tasks has been updated to use enum types.'
\echo 'Columns task_type, status, and current_stage now use proper enum types.'