# database/sql 脚本说明（代码对齐版）

本目录包含初始化、清理及历史修复 SQL。并非所有脚本都会被 `dbctl.sh` 自动调用。

## 自动调用脚本

- `init_database_schema.sql`：初始化参考 schema（当前主要通过 ORM `create_all`）
- `seed_data.sql`：初始化种子数据（`dbctl.sh init` 会执行）
- `cleanup_orphan_records.sql`：清理孤儿记录（`dbctl.sh cleanup` 会执行）

## 历史修复脚本（按需人工执行）

- `alter_table_to_use_enums.sql`
- `alter_table_to_use_enums_corrected.sql`
- `check_enums.sql`
- `fix_enums.sql`
- `fix_enums_fixed.sql`
- `fix_foreign_key_constraint.sql`
- `fix_foreign_key_constraint_final.sql`

这些脚本多用于历史数据迁移/应急修复，执行前请先在测试环境验证。

## 手工执行示例

```bash
psql -h <host> -p <port> -U <user> -d <db> -f database/sql/check_enums.sql
```
