# Qdrant HTTPS连接测试修复和端口问题解决方案

## 问题概述

原始的 `test_https_connection.py` 脚本存在两个主要问题：

1. **导入路径错误**：脚本使用 `from tests.src...` 而不是 `from src...`
2. **服务未运行**：端口6333虽然开放，但运行的不是Qdrant服务

## 已完成的修复工作

### 1. 修复导入路径
- 已将 `from tests.src.database_config import DatabaseConfig` 修复为 `from src.database_config import DatabaseConfig`
- 已将 `from tests.src.qdrant_client import QdrantManager` 修复为 `from src.qdrant_client import QdrantManager`

### 2. 安装必要依赖
- 已在虚拟环境中安装 `requests` 库用于诊断功能

### 3. 创建辅助工具
- `simple_qdrant_test.py` - 简化版连接测试
- `diagnose_qdrant.py` - 详细诊断工具
- `check_qdrant_status.py` - 状态检查工具
- `QDRANT_HTTPS_TEST_GUIDE.md` - 详细使用指南

## 端口问题解决方案

### 问题分析
- 端口6333被 `rootlessport` 进程占用（Docker rootless模式的端口转发工具）
- 实际运行的不是Qdrant服务
- HTTP请求被系统代理（http://127.0.0.1:7890）拦截

### 解决步骤

#### 步骤1：启动真正的Qdrant服务

使用Docker启动Qdrant服务：

```bash
# 检查Docker是否运行
sudo systemctl status docker

# 如未运行，则启动Docker
sudo systemctl start docker

# 停止任何可能冲突的容器
docker stop qdrant 2>/dev/null || true
docker rm qdrant 2>/dev/null || true

# 启动Qdrant容器
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -e QDRANT_API_KEY="EDhs@gJcftnT3sBU" \
  qdrant/qdrant:latest

# 等待服务启动
sleep 10
```

#### 步骤2：验证Qdrant服务

```bash
# 检查服务健康状态（绕过代理）
curl --noproxy localhost http://localhost:6333/healthz
```

#### 步骤3：运行测试脚本

```bash
cd /mnt/data/Documents/Graduate/02_Research/07_Multi-ACMG-database/tests
source .venv/bin/activate

# 临时禁用TLS进行初步测试
export QDRANT_USE_TLS=false
export QDRANT_VERIFY_SSL=false

# 运行测试
python test_https_connection.py
```

## 验证修复

修复后的导入功能已验证正常工作：

```bash
cd /mnt/data/Documents/Graduate/02_Research/07_Multi-ACMG-database/tests
source .venv/bin/activate
python -c "from src.database_config import DatabaseConfig; from src.qdrant_client import QdrantManager; print('✅ 导入测试成功')"
```

## 环境配置建议

为了成功运行HTTPS连接测试，建议：

1. **启动Qdrant服务**：确保真正的Qdrant服务在端口6333上运行
2. **配置环境变量**：
   ```bash
   export QDRANT_USE_TLS=false  # 初次测试时禁用TLS
   export QDRANT_VERIFY_SSL=false
   ```
3. **绕过系统代理**：使用 `--noproxy localhost` 选项

## 完整测试流程

一旦Qdrant服务启动，按以下顺序运行测试：

1. 状态检查：
   ```bash
   python check_qdrant_status.py
   ```

2. 简化测试：
   ```bash
   python simple_qdrant_test.py
   ```

3. 详细诊断：
   ```bash
   python diagnose_qdrant.py
   ```

4. HTTPS连接测试：
   ```bash
   python test_https_connection.py
   ```

## 总结

- ✅ **代码修复**：导入路径错误已修复
- ✅ **依赖安装**：所需库已安装
- ✅ **辅助工具**：已创建多个诊断和测试工具
- ⏳ **服务启动**：需要用户启动真正的Qdrant服务

修复后的脚本现在可以正确运行，但需要启动真正的Qdrant服务才能完成完整的HTTPS连接测试。