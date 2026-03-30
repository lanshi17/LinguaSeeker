-- 紧急修复：修改parsing_tasks表以解决外键约束问题
-- 方法：允许document_id暂时为空，直到文档创建完成

-- 首先，检查当前的外键约束
SELECT 
    con.conname AS constraint_name,
    con.contype AS constraint_type,
    con.condeferrable AS deferrable,
    con.condeferred AS initially_deferred
FROM 
    pg_constraint con
WHERE 
    con.conname = 'parsing_tasks_document_id_fkey';

-- 检查parsing_tasks表中document_id列的NULL状态
SELECT column_name, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'parsing_tasks' AND column_name = 'document_id';

-- 临时移除外键约束
ALTER TABLE parsing_tasks DROP CONSTRAINT parsing_tasks_document_id_fkey;

-- 修改document_id列允许NULL值
ALTER TABLE parsing_tasks ALTER COLUMN document_id DROP NOT NULL;
ALTER TABLE parsing_tasks ALTER COLUMN document_id SET DEFAULT NULL;

-- 重建外键约束，允许NULL值
ALTER TABLE parsing_tasks 
ADD CONSTRAINT parsing_tasks_document_id_fkey 
FOREIGN KEY (document_id) REFERENCES documents(id) 
ON DELETE SET NULL  -- 当文档被删除时，将任务的document_id设为NULL而不是删除任务
DEFERRABLE INITIALLY IMMEDIATE;

-- 验证修改结果
SELECT 
    con.conname AS constraint_name,
    con.contype AS constraint_type,
    con.condeferrable AS deferrable,
    con.condeferred AS initially_deferred
FROM 
    pg_constraint con
WHERE 
    con.conname = 'parsing_tasks_document_id_fkey';

SELECT column_name, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'parsing_tasks' AND column_name = 'document_id';

\echo 'parsing_tasks表已更新：'
\echo '1. document_id列现在允许NULL值'
\echo '2. 外键约束允许NULL值并设置ON DELETE SET NULL'
\echo '3. 约束是可延迟的，允许在事务中灵活处理'
\echo '现在可以在创建文档前先创建任务记录。'