# 多ACMG数据库系统

这是一个用于存储和分析ACMG（美国医学遗传学学会）变异解读证据的多数据库系统。

## 项目结构

```
├── src/
│   ├── database_config.py          # 数据库配置管理
│   ├── connectivity_test.py        # 连通性测试脚本
│   ├── basic_connectivity_test.py  # 基础连通性测试
│   ├── final_connectivity_report.py # 最终连通性报告
│   ├── mock_data_generator.py      # 模拟数据生成器（在线版）
│   ├── mock_data_generator_offline.py # 模拟数据生成器（离线版）
│   ├── data_statistics.py          # 数据统计报告
│   ├── neo4j-demo.py
│   ├── postgre-demo.py
│   ├── qdrant-demo.py
│   └── redis-demo.py
├── data/                         # 生成的模拟数据
│   ├── documents.json            # 文档数据
│   ├── parsing_tasks.json        # 解析任务数据
│   ├── evidence_records.json     # 证据记录数据
│   ├── agent_logs.json           # 代理日志数据
│   └── insert_statements.sql     # SQL插入语句
├── src/
│   └── create_tables.sql         # 数据库表创建脚本
├── .env.development             # 开发环境配置
└── pyproject.toml               # 项目依赖配置
```

## 数据库表结构

### 1. documents 表
文献文档主表，存储上传的PDF文档基本信息

| 字段名 | 类型 | 来源层 | 约束说明 |
|--------|------|--------|----------|
| id | UUID | 应用层 | 主键，{{document_id}} |
| original_filename | VARCHAR(255) | 表现层 | 原始文件名 |
| minio_path | VARCHAR(500) | 基础设施层 | MinIO存储路径 |
| status | ENUM | 应用层 | 'uploaded','parsing','completed','failed' |
| pmid | VARCHAR(50) | 领域层 | 唯一索引 |
| doi | VARCHAR(255) | 领域层 | 唯一索引 |
| title | TEXT | 领域层 | 文献标题 |
| created_at | TIMESTAMPTZ | 基础设施层 | 默认CURRENT_TIMESTAMP |

### 2. parsing_tasks 表
文档解析任务表，跟踪PDF解析过程

| 字段名 | 类型 | 来源层 | 约束说明 |
|--------|------|--------|----------|
| id | UUID | 应用层 | 主键，{{task_uuid}} |
| document_id | UUID | 应用层 | 外键→documents.id |
| task_type | VARCHAR(50) | 表现层 | 'pdf_parse','identifier_resolve' |
| celery_task_id | VARCHAR(255) | 基础设施层 | Celery任务ID |
| result_path | VARCHAR(500) | 基础设施层 | MinIO结果路径 |
| status | ENUM | 应用层 | 'pending','processing','completed','failed' |
| progress | INTEGER | 领域层 | 0-100 |

### 3. evidence_records 表
证据记录表，存储ACMG变异解读证据

| 字段名 | 类型 | 来源层 | 约束说明 |
|--------|------|--------|----------|
| id | UUID | 领域层 | 主键 |
| document_id | UUID | 领域层 | 外键→documents.id |
| evidence_type | VARCHAR(10) | 领域层 | PS1/PS2/PM1/PS3... |
| content | TEXT | 领域层 | 证据原文片段 |
| confidence_score | FLOAT | 领域层 | 0.0-1.0 |
| source_page | INTEGER | 领域层 | 原文页码 |
| source_position | VARCHAR(100) | 领域层 | 原文位置标识 |
| status | ENUM | 领域层 | 'pending','approved','rejected' |
| neo4j_node_id | VARCHAR(100) | 基础设施层 | Neo4j节点ID |
| created_at | TIMESTAMPTZ | 基础设施层 | 默认CURRENT_TIMESTAMP |

### 4. agent_logs 表
智能体日志表，记录AI处理过程

| 字段名 | 类型 | 来源层 | 约束说明 |
|--------|------|--------|----------|
| id | UUID | 领域层 | 主键 |
| task_id | UUID | 领域层 | 外键→parsing_tasks.id |
| agent_type | VARCHAR(50) | 领域层 | 'layout','translation'... |
| input_hash | CHAR(64) | 领域层 | SHA256输入摘要 |
| output | JSONB | 领域层 | Agent输出快照 |
| duration_ms | INTEGER | 领域层 | 处理耗时 |
| retry_count | INTEGER | 领域层 | 重试次数 |

## 连通性测试结果

- **PostgreSQL**: 配置正常，端口可达
- **Neo4j**: 配置正常，端口可达  
- **Qdrant**: 配置正常，端口可达
- **MinIO**: 配置正常，端口可达

## 模拟数据统计

- **Documents表**: 50 条记录
- **Parsing Tasks表**: 50 条记录
- **Evidence Records表**: 250 条记录
- **Agent Logs表**: 100 条记录

## 部署说明

1. 安装依赖包:
```bash
pip install psycopg2-binary neo4j qdrant-client minio faker
```

2. 确保所有服务正在运行:
   - PostgreSQL (默认端口 5432)
   - Neo4j (默认端口 7687)
   - Qdrant (默认端口 6333)
   - MinIO (默认端口 9000)

3. 创建数据库表:
```bash
psql -h localhost -U postgres -d acmg_ps3 -f src/create_tables.sql
```

4. 插入模拟数据:
```bash
# 使用生成的SQL文件
psql -h localhost -U postgres -d acmg_ps3 -f data/insert_statements.sql
```

## 测试脚本

- `python src/connectivity_test.py` - 运行完整连通性测试
- `python src/mock_data_generator_offline.py` - 生成模拟数据
- `python src/data_statistics.py` - 生成数据统计报告