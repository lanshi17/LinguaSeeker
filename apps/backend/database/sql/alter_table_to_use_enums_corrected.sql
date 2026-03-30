-- Emergency fix: Update parsing_tasks table to use proper enum types
-- This addresses the mismatch between application expectations and database schema

-- Check current values in the table to understand the data we're working with
\echo 'Current values in parsing_tasks table (sample):'
SELECT 
    task_type, 
    status, 
    current_stage,
    COUNT(*) as count
FROM parsing_tasks 
GROUP BY task_type, status, current_stage
LIMIT 10;

-- Step 1: Temporarily disable triggers/constraints if any to prevent conflicts
-- We'll drop the old check constraints first
ALTER TABLE parsing_tasks DROP CONSTRAINT IF EXISTS parsing_tasks_status_check;
ALTER TABLE parsing_tasks DROP CONSTRAINT IF EXISTS parsing_tasks_task_type_check;

-- Step 2: Add new columns with the proper enum types
-- We'll use temporary names first to avoid conflicts
ALTER TABLE parsing_tasks ADD COLUMN task_type_new tasktype;
ALTER TABLE parsing_tasks ADD COLUMN status_new taskstatus;
ALTER TABLE parsing_tasks ADD COLUMN current_stage_new taskstage;

-- Step 3: Migrate data from old columns to new enum columns
-- Map existing lowercase values to the required uppercase enum values
UPDATE parsing_tasks SET 
    task_type_new = CASE 
        WHEN LOWER(task_type) = 'pdf_parse' OR LOWER(task_type) = 'pdf-parse' OR LOWER(task_type) = 'pdfparse' THEN 'PDF_PARSE'::tasktype
        WHEN LOWER(task_type) = 'identifier_resolve' OR LOWER(task_type) = 'identifier-resolve' OR LOWER(task_type) = 'identifierresolve' THEN 'IDENTIFIER_RESOLVE'::tasktype
        WHEN LOWER(task_type) = 'data_extraction' OR LOWER(task_type) = 'data-extract' OR LOWER(task_type) = 'dataextract' THEN 'DATA_EXTRACTION'::tasktype
        ELSE 'PDF_PARSE'::tasktype  -- Default fallback
    END,
    status_new = CASE 
        WHEN LOWER(status) = 'pending' THEN 'PENDING'::taskstatus
        WHEN LOWER(status) = 'processing' THEN 'RUNNING'::taskstatus  -- Mapping processing -> running
        WHEN LOWER(status) = 'completed' THEN 'SUCCESS'::taskstatus  -- Mapping completed -> success
        WHEN LOWER(status) = 'failed' THEN 'ERROR'::taskstatus       -- Mapping failed -> error
        WHEN LOWER(status) = 'running' THEN 'RUNNING'::taskstatus
        WHEN LOWER(status) = 'success' THEN 'SUCCESS'::taskstatus
        WHEN LOWER(status) = 'error' THEN 'ERROR'::taskstatus
        ELSE 'PENDING'::taskstatus  -- Default fallback
    END,
    current_stage_new = CASE 
        WHEN LOWER(current_stage) = 'ingestion' THEN 'INGESTION'::taskstage
        WHEN LOWER(current_stage) = 'processing' THEN 'PROCESSING'::taskstage
        WHEN LOWER(current_stage) = 'completed' THEN 'COMPLETED'::taskstage
        WHEN LOWER(current_stage) = 'failed' THEN 'FAILED'::taskstage
        ELSE 'INGESTION'::taskstage  -- Default fallback
    END;

-- Step 4: Drop the old columns and rename the new ones
ALTER TABLE parsing_tasks DROP COLUMN task_type;
ALTER TABLE parsing_tasks DROP COLUMN status;
ALTER TABLE parsing_tasks DROP COLUMN current_stage;

ALTER TABLE parsing_tasks RENAME COLUMN task_type_new TO task_type;
ALTER TABLE parsing_tasks RENAME COLUMN status_new TO status;
ALTER TABLE parsing_tasks RENAME COLUMN current_stage_new TO current_stage;

-- Step 5: Set NOT NULL constraints and defaults
ALTER TABLE parsing_tasks ALTER COLUMN task_type SET NOT NULL;
ALTER TABLE parsing_tasks ALTER COLUMN status SET NOT NULL;
ALTER TABLE parsing_tasks ALTER COLUMN status SET DEFAULT 'PENDING'::taskstatus;
ALTER TABLE parsing_tasks ALTER COLUMN current_stage SET DEFAULT 'INGESTION'::taskstage;

\echo 'Table parsing_tasks has been updated to use proper enum types.'
\echo 'Columns now use tasktype, taskstatus, and taskstage enums as required by the application.'