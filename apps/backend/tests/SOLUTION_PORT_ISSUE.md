# 解决Qdrant端口占用问题

## 问题分析

根据之前的诊断，系统中存在以下问题：
1. 端口6333被`rootlessport`进程占用（Docker rootless模式的端口转发工具）
2. 实际运行的不是Qdrant服务
3. HTTP请求被系统代理（http://127.0.0.1:7890）拦截

## 解决方案

### 方案1：使用Docker启动Qdrant（推荐）

#### 步骤1：检查Docker服务
```bash
# 检查Docker是否运行
sudo systemctl status docker

# 如未运行，则启动Docker
sudo systemctl start docker
```

#### 步骤2：停止可能冲突的服务
```bash
# 停止任何正在运行的Qdrant容器
docker stop qdrant 2>/dev/null || true
docker rm qdrant 2>/dev/null || true

# 停止可能的其他Qdrant容器
docker stop qdrant-vector-db 2>/dev/null || true
docker rm qdrant-vector-db 2>/dev/null || true
```

#### 步骤3：启动Qdrant服务
```bash
# 运行Qdrant容器
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -e QDRANT_API_KEY="EDhs@gJcftnT3sBU" \
  qdrant/qdrant:latest
```

#### 步骤4：验证服务
```bash
# 等待服务启动
sleep 10

# 检查服务状态（绕过代理）
curl --noproxy localhost http://localhost:6333/healthz

# 检查端口占用
lsof -i :6333
```

### 方案2：使用Docker Compose

如果您更喜欢使用Docker Compose，可以使用之前创建的配置：

```bash
# 在tests目录中
cd /mnt/data/Documents/Graduate/02_Research/07_Multi-ACMG-database/tests

# 停止现有容器
docker compose down

# 启动Qdrant服务
docker compose up -d
```

### 方案3：绕过系统代理进行测试

如果Qdrant已经在运行但被代理拦截，可以通过以下方式测试：

```bash
# 临时取消代理设置
unset http_proxy
unset https_proxy

# 或者在测试时明确绕过代理
curl --noproxy localhost http://localhost:6333/healthz
```

## 验证步骤

### 1. 检查端口占用
```bash
sudo lsof -i :6333
```

### 2. 检查Qdrant健康状态
```bash
curl --noproxy localhost http://localhost:6333/healthz
```

### 3. 运行修复后的测试脚本
```bash
cd /mnt/data/Documents/Graduate/02_Research/07_Multi-ACMG-database/tests
source .venv/bin/activate
python test_https_connection.py
```

## 故障排除

### 问题1：Permission denied for Docker
**解决方案**：
```bash
# 将用户添加到docker组
sudo usermod -aG docker $USER
# 然后重新登录或运行
newgrp docker
```

### 问题2：Port already allocated
**解决方案**：
```bash
# 查找占用端口的进程并终止
sudo lsof -i :6333
sudo kill -9 <PID>
```

### 问题3：Qdrant container fails to start
**解决方案**：
```bash
# 检查容器日志
docker logs qdrant
```

## 环境变量配置

确保环境变量正确设置，特别是用于测试时：

```bash
# 临时禁用TLS进行初步测试
export QDRANT_USE_TLS=false
export QDRANT_VERIFY_SSL=false
```

## 完整测试流程

一旦Qdrant服务启动，按以下顺序运行测试：

1. 基本连接测试
```bash
python simple_qdrant_test.py
```

2. 详细诊断
```bash
python diagnose_qdrant.py
```

3. HTTPS连接测试
```bash
python test_https_connection.py
```

这样应该能解决端口6333上运行的不是Qdrant服务的问题。