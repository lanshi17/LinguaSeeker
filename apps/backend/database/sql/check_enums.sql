-- Check if required enum types exist in the database
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