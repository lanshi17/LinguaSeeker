# ACMG数据库系统测试流水线

本项目包含一个完整的测试流水线，用于验证ACMG数据库系统的连接性、功能和性能。

## 项目结构

```
.
├── main.py                          # 测试流水线入口点
├── src/
│   ├── database_config.py          # 数据库配置管理
│   ├── enhanced_connectivity_test.py # 增强版连通性测试
│   ├── adaptive_database_operations_test.py # 自适应数据库操作测试
│   ├── mock_data_generator_offline.py # 离线模拟数据生成器
│   ├── data_statistics.py          # 数据统计报告
│   └── create_tables.sql           # 数据库表创建脚本
├── data/
│   ├── documents.json              # 生成的文档数据
│   ├── parsing_tasks.json          # 生成的解析任务数据
│   ├── evidence_records.json       # 生成的证据记录数据
│   ├── agent_logs.json             # 生成的代理日志数据
│   └── insert_statements.sql       # SQL插入语句
└── OPTIMIZED_TEST_CODE_SUMMARY.md  # 优化代码总结
```

## 功能特性

### 1. 连通性测试
- 测试PostgreSQL、Neo4j、Qdrant和MinIO的连接状态
- 验证端口可达性和服务响应
- 自动使用正确的认证凭据

### 2. 数据库操作测试
- 自动检测可用的数据库连接方法（psql或psycopg2）
- 执行完整的CRUD操作测试
- 验证表结构和数据完整性

### 3. 模拟数据生成
- 生成符合ACMG标准的高质量模拟数据
- 包含所有四个核心表的数据（documents, parsing_tasks, evidence_records, agent_logs）
- 支持自定义数据量

### 4. 数据统计分析
- 提供详细的统计数据和分布信息
- 验证数据质量和完整性

## 使用方法

### 运行完整测试流水线
```bash
python main.py
```

### 运行特定测试步骤

#### 连通性测试
```bash
python main.py --step connectivity
```

#### 模拟数据生成
```bash
python main.py --step mock-data --count 50
```
其中 `--count` 指定每个表生成的记录数量，默认为20。

#### 数据统计
```bash
python main.py --step statistics
```

#### 数据库操作测试
```bash
python main.py --step operations
```

### 查看帮助
```bash
python main.py --help
```

## 流水线执行步骤

1. **连通性测试**：验证所有数据库服务的连接状态
2. **模拟数据生成**：创建测试数据并保存到文件
3. **数据统计**：分析生成数据的统计信息
4. **操作测试**：执行数据库CRUD操作测试

## 输出文件

- `test_pipeline_results_<timestamp>.json` - 测试流水线的详细结果
- `data/*.json` - 生成的模拟数据文件
- `data/insert_statements.sql` - 用于数据库插入的SQL语句

## 配置要求

流水线使用以下数据库配置（基于修复后的设置）：
- PostgreSQL: localhost:5432, 用户: yangzs, 密码: ${POSTGRES_PASSWORD}
- Neo4j: bolt://localhost:7687, 用户: neo4j, 密码: ${NEO4J_PASSWORD}
- Qdrant: localhost:6333, API密钥: ${QDRANT_API_KEY}
- MinIO: localhost:9000, 访问密钥: yangzs, 秘密密钥: ${MINIO_SECRET_KEY}

**重要提示**: 必须在运行测试前通过 `export` 设置上述环境变量。绝不应在此文档或任何源代码中提交明文密码。

## 错误处理

- 如果数据库连接工具不可用，系统会提供信息性反馈
- 所有步骤都经过错误处理，确保流水线的稳定性
- 详细的错误日志帮助诊断问题

## ACMG特定验证

- 验证ACMG证据类型（PS1, PM1, BP1等）的正确性
- 确保变异解读工作流程的数据完整性
- 验证置信度分数和状态字段的合理性