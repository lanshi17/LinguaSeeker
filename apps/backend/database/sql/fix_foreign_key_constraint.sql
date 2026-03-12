-- 紧急修复：修改外键约束为可延迟，以解决parsing_tasks表外键约束错误
-- 此修复允许在事务中先插入parsing_tasks记录，再插入对应的documents记录

-- 检查当前约束状态
SELECT 
    con.conname AS constraint_name,
    con.contype AS constraint_type,
    con.condeferrable AS deferrable,
    con.condeferred AS initially_deferred
FROM 
    pg_constraint con
WHERE 
    con.conname = 'parsing_tasks_document_id_fkey';

-- 删除现有的外键约束
ALTER TABLE parsing_tasks DROP CONSTRAINT parsing_tasks_document_id_fkey;

-- 重建外键约束，设置为可延迟（DEFERRABLE）
ALTER TABLE parsing_tasks 
ADD CONSTRAINT parsing_tasks_document_id_fkey 
FOREIGN KEY (document_id) REFERENCES documents(id) 
ON DELETE CASCADE 
DEFERRABLE INITIALLY IMMEDIATE;

-- 确认约束已正确重建
SELECT 
    con.conname AS constraint_name,
    con.contype AS constraint_type,
    con.condeferrable AS deferrable,
    con.condeferred AS initially_deferred
FROM 
    pg_constraint con
WHERE 
    con.conname = 'parsing_tasks_document_id_fkey';

\echo '外键约束已修改为可延迟模式。'
\echo '现在可以在同一事务中先创建parsing_tasks记录，再创建对应的documents记录。'
\echo '这解决了业务逻辑中外键约束导致的插入失败问题。'