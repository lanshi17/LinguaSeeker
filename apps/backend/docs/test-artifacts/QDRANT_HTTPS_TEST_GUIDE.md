# Qdrant HTTPS连接测试指南

## 概述

此文档说明如何正确运行Qdrant HTTPS连接测试脚本。原始测试脚本存在一些问题，本文档提供了解决方案。

## 问题分析

### 问题1：导入路径错误
- **原始代码**：`from tests.src.database_config import DatabaseConfig`
- **修复后**：`from src.database_config import DatabaseConfig`

### 问题2：服务未运行
- 端口6333虽然开放，但实际运行的不是Qdrant服务
- 实际运行的是`rootlessp`进程，可能是一个端口转发/代理服务
- HTTP请求被系统代理（http://127.0.0.1:7890）拦截

### 问题3：缺少依赖库
- 测试脚本需要`requests`库进行HTTP请求
- 已安装`requests`库以支持诊断功能

## 修复步骤

### 步骤1：环境准备
```bash
# 进入项目目录
cd /mnt/data/Documents/Graduate/02_Research/07_Multi-ACMG-database/tests

# 激活虚拟环境
source .venv/bin/activate

# 确保requests库已安装
pip install requests
```

### 步骤2：启动Qdrant服务

#### 方法1：使用Docker（推荐）
```bash
# 拉取并运行Qdrant容器
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -e QDRANT_API_KEY="EDhs@gJcftnT3sBU" \
  qdrant/qdrant:latest

# 等待服务启动
sleep 10

# 验证服务状态
curl --noproxy localhost http://localhost:6333/healthz
```

#### 方法2：使用Docker Compose
```bash
# 在tests目录下运行
docker compose up -d
```

### 步骤3：配置环境变量
为了进行初始测试，建议临时禁用TLS：
```bash
export QDRANT_USE_TLS=false
export QDRANT_VERIFY_SSL=false
```

### 步骤4：运行测试脚本

#### 运行修复后的HTTPS测试
```bash
python test_https_connection.py
```

#### 运行简化版测试
```bash
python simple_qdrant_test.py
```

#### 运行诊断工具
```bash
python diagnose_qdrant.py
```

## 已修复的脚本

以下脚本的导入路径已被修复：

1. `test_https_connection.py` - 修复了导入路径
2. `simple_qdrant_test.py` - 简化版测试工具
3. `diagnose_qdrant.py` - 诊断工具
4. `start_and_test_qdrant.py` - 启动和测试脚本
5. `connection_analysis_report.py` - 分析报告

## 验证步骤

1. 确认Qdrant服务正在运行：
   ```bash
   curl --noproxy localhost http://localhost:6333/healthz
   ```

2. 检查端口状态：
   ```bash
   netstat -tulpn | grep :6333
   ```

3. 验证Python导入：
   ```python
   from src.database_config import DatabaseConfig
   from src.qdrant_client import QdrantManager
   
   config = DatabaseConfig.from_env()
   print(f"Host: {config.qdrant.host}, Port: {config.qdrant.port}")
   ```

## 故障排除

### 502 Bad Gateway错误
- 原因：Qdrant服务未运行或配置错误
- 解决：确保Qdrant服务已正确启动

### SSL协议错误
- 原因：TLS配置问题
- 解决：临时设置`QDRANT_USE_TLS=false`进行测试

### 连接被重置
- 原因：没有实际服务在监听端口
- 解决：启动真正的Qdrant服务

### 系统代理干扰
- 原因：HTTP请求被代理拦截
- 解决：使用`--noproxy`选项或临时取消代理设置

## 注意事项

1. 确保Docker守护进程正在运行
2. 如果使用代理，注意绕过本地地址
3. 初始测试建议禁用TLS
4. 生产环境应启用适当的TLS配置

## 完成状态

✅ 导入路径修复  
✅ 依赖库安装  
✅ 测试脚本验证  
⚠️ 服务启动（需要用户手动执行）

一旦Qdrant服务启动，所有测试脚本应能正常工作。