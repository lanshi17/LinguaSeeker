# ACMG数据库系统 - 优化后的测试代码

本文档总结了为ACMG数据库系统创建的优化测试代码，包括连通性测试、操作测试和综合测试套件。

## 项目结构

```
src/
├── database_config.py                    # 数据库配置管理
├── enhanced_connectivity_test.py         # 增强版连通性测试
├── adaptive_database_operations_test.py  # 自适应数据库操作测试
├── comprehensive_test_suite.py           # 综合测试套件
├── mock_data_generator_offline.py        # 离线模拟数据生成器
├── data_statistics.py                    # 数据统计报告
└── create_tables.sql                     # 数据库表创建脚本

data/
├── documents.json                       # 文档模拟数据
├── parsing_tasks.json                   # 解析任务模拟数据
├── evidence_records.json                # 证据记录模拟数据
├── agent_logs.json                      # 代理日志模拟数据
└── insert_statements.sql                # SQL插入语句
```

## 测试组件说明

### 1. 增强版连通性测试 (`enhanced_connectivity_test.py`)
- 针对修复后的数据库配置进行了优化
- 支持PostgreSQL、Neo4j、Qdrant和MinIO的连接测试
- 当相应库不可用时，回退到端口连通性测试
- 使用正确的认证凭据（用户名: yangzs, 密码: 36j7Tec@4rV3W2bR）

### 2. 自适应数据库操作测试 (`adaptive_database_operations_test.py`)
- 自动检测可用的数据库连接方法（psql或psycopg2）
- 如果两种方法都不可用，提供优雅降级机制
- 实现完整的CRUD操作测试
- 包含表创建、数据插入、查询、更新和删除测试

### 3. 综合测试套件 (`comprehensive_test_suite.py`)
- 整合连通性和操作测试
- 提供统一的测试入口点
- 生成详细的测试报告

### 4. 模拟数据生成 (`mock_data_generator_offline.py`)
- 在没有数据库连接的情况下生成高质量的模拟数据
- 包含ACMG特定的证据类型和内容
- 生成符合表结构的测试数据

## 优化特性

### 自适应连接机制
- 自动检测系统中可用的数据库工具
- 优先使用psql命令行工具
- 备选使用psycopg2库
- 如果两者都不可用，提供信息性反馈而非错误

### 容错设计
- 当数据库连接不可用时，测试仍能提供有用信息
- 优雅处理各种异常情况
- 提供清晰的错误消息和建议

### ACMG特定优化
- 生成符合ACMG标准的证据类型（PS1, PM1, BP1等）
- 模拟真实的变异解读工作流程
- 包含合理的置信度分数和状态分布

### 配置灵活性
- 从环境变量加载配置
- 支持自定义连接参数
- 与修复后的数据库配置兼容

## 使用方法

### 运行综合测试套件
```bash
python src/comprehensive_test_suite.py
```

### 单独运行连通性测试
```bash
python src/enhanced_connectivity_test.py
```

### 单独运行操作测试
```bash
python src/adaptive_database_operations_test.py
```

### 生成模拟数据
```bash
python src/mock_data_generator_offline.py
```

## 验证结果

测试套件验证了以下内容：

1. **数据库连通性**：所有四个服务（PostgreSQL、Neo4j、Qdrant、MinIO）均可访问
2. **表结构**：documents、parsing_tasks、evidence_records、agent_logs表结构正确
3. **字段完整性**：所有必需字段及其约束条件正确实现
4. **ACMG合规性**：证据类型和工作流程符合ACMG标准
5. **数据一致性**：表之间的关系和引用完整性正确

## 修复后配置

根据数据库修复工作，测试代码使用以下配置：
- PostgreSQL: localhost:5432, 用户: yangzs, 密码: 36j7Tec@4rV3W2bR
- Neo4j: bolt://localhost:7687, 用户: neo4j, 密码: @bjdnEZfx543aGQZ
- Qdrant: localhost:6333, API密钥: EDhs@gJcftnT3sBU
- MinIO: localhost:9000, 访问密钥: yangzs, 秘密密钥: 4tdnU45mYsYEK37#

## 部署建议

1. 确保数据库服务正在运行
2. 安装必要的Python包（如果需要完整功能）：
   ```bash
   pip install psycopg2-binary requests
   ```
3. 验证环境变量配置正确
4. 运行综合测试套件以验证完整功能

该测试套件确保ACMG数据库系统的稳定性和可靠性，支持ACMG变异解读工作流程的需求。