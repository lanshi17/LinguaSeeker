# SQL 脚本目录

此目录包含所有数据库相关的SQL脚本。

## 文件说明

- `init_database_schema.sql` - PostgreSQL数据库模式初始化脚本，包含所有表结构、索引和约束的定义

## 使用说明

### 初始化数据库
要初始化数据库，请在项目根目录下运行：
```bash
./init_db.sh
```

或者直接使用psql命令：
```bash
psql -h localhost -p 5432 -U [username] -d [database_name] -f sql/init_database_schema.sql
```

## 脚本详情

### init_database_schema.sql
此脚本将创建以下数据库对象：

#### 表结构
- `users` - 存储系统用户信息
- `documents` - 存储文档信息，包含file_hash字段防止重复
- `tasks` - 存储处理任务信息
- `entities` - 存储识别的实体信息
- `entity_document_mapping` - 存储实体与文档之间的映射关系
- `graph_nodes_cache` - 存储图数据库节点缓存信息
- `graph_edges_cache` - 存储图数据库边缓存信息

#### 索引
- 为主键、外键和常用查询字段创建了索引
- 为documents.file_hash字段添加了唯一索引，防止重复插入
- 为常用查询字段创建了专门的索引

#### 触发器
- 为需要跟踪更新时间的表创建了自动更新updated_at字段的触发器