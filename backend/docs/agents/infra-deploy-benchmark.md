# 基础设施、部署与性能基准

> 子代理专长：Docker 容器化、CI/CD 流水线、数据库管理、性能监控与基准测试。

## 职责范围

负责后端服务的基础设施搭建、自动化部署、数据库运维及性能优化。

### 核心模块

| 模块 | 路径 | 说明 |
|------|------|------|
| Dockerfile | `Dockerfile` | 多阶段构建，含 Rust 编译 |
| Docker Compose | `docker-compose.yml` | 本地开发环境编排 |
| CI/CD | `.github/workflows/` | GitHub Actions 流水线 |
| 数据库迁移 | `alembic/` | Alembic 迁移管理 |
| 配置管理 | `config/` | 分层 YAML 配置 |

### Docker 构建

#### 多阶段构建

```dockerfile
# 阶段 1: Rust 编译
FROM rust:1.82-slim AS rust-builder
WORKDIR /build
COPY libs/ ./libs/
RUN cargo build --release -p rust-io

# 阶段 2: Python 依赖
FROM python:3.12-slim AS python-builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --no-dev

# 阶段 3: 运行时
FROM python:3.12-slim
WORKDIR /app
COPY --from=rust-builder /build/target/release/librust_io.so ./rust_io.so
COPY --from=python-builder /app/.venv ./.venv
COPY app/ ./app/
COPY config/ ./config/
CMD ["./.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 镜像优化

- **多阶段构建**：分离编译时和运行时依赖，减小镜像体积
- **层缓存**：先复制依赖文件，再复制源代码，利用 Docker 层缓存
- **精简基础镜像**：使用 `slim` 变体，仅安装必要系统依赖
- **Rust 静态链接**：`librust_io.so` 静态链接所有 Rust 依赖

### Docker Compose 编排

```yaml
version: '3.8'
services:
  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/lingua_seeker
      - REDIS_URL=redis://redis:6379
      - SECRET_KEY=${SECRET_KEY}
    depends_on:
      - db
      - redis
    volumes:
      - ./data:/app/data

  db:
    image: postgres:16-alpine
    environment:
      - POSTGRES_DB=lingua_seeker
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

### CI/CD 流水线

#### GitHub Actions 工作流

```yaml
name: Backend CI/CD
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: test_db
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install uv
        run: pip install uv
      - name: Install dependencies
        run: uv sync
      - name: Build Rust extensions
        run: uv run maturin develop --release -m libs/rust-io/Cargo.toml
      - name: Run Rust tests
        run: |
          cargo test -p net-io
          cargo test -p files-io
      - name: Run Python tests
        run: uv run pytest --cov=app --cov-report=xml
      - name: Lint Rust
        run: cargo clippy --all-targets -- -D warnings
      - name: Lint Python
        run: uv run ruff check .

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker image
        run: docker build -t lingua-seeker-backend:${{ github.sha }} .
      - name: Push to registry
        run: |
          echo ${{ secrets.DOCKER_PASSWORD }} | docker login -u ${{ secrets.DOCKER_USERNAME }} --password-stdin
          docker tag lingua-seeker-backend:${{ github.sha }} ${{ secrets.DOCKER_REGISTRY }}/lingua-seeker-backend:latest
          docker push ${{ secrets.DOCKER_REGISTRY }}/lingua-seeker-backend:latest
```

### 数据库管理

#### Alembic 迁移

```bash
# 创建迁移脚本
uv run alembic revision --autogenerate -m "add_variant_table"

# 应用迁移
uv run alembic upgrade head

# 回滚迁移
uv run alembic downgrade -1

# 查看迁移历史
uv run alembic history

# 查看当前版本
uv run alembic current
```

#### 数据库初始化

```bash
# 创建数据库
createdb lingua_seeker

# 运行迁移
uv run alembic upgrade head

# 加载初始数据
uv run python scripts/seed_data.py
```

### 性能基准测试

#### 基准测试工具

使用 `pytest-benchmark` 进行性能基准测试：

```bash
# 运行基准测试
uv run pytest tests/benchmark/ --benchmark-only

# 生成基准报告
uv run pytest tests/benchmark/ --benchmark-only --benchmark-json=benchmark.json

# 比较基准结果
uv run pytest tests/benchmark/ --benchmark-compare=benchmark.json
```

#### 关键性能指标

| 指标 | 目标 | 说明 |
|------|------|------|
| API 响应时间 | < 200ms (P95) | 标准 API 端点 |
| 文献搜索延迟 | < 2s (P95) | 单数据源搜索 |
| 并行搜索延迟 | < 5s (P95) | 5 个数据源并行 |
| PDF 解析时间 | < 30s (P95) | 10 页 PDF |
| 数据库查询 | < 50ms (P95) | 标准查询 |
| 并发用户数 | > 100 | 同时在线用户 |

#### 基准测试用例

```python
# tests/benchmark/test_api_benchmark.py
import pytest

@pytest.mark.benchmark
def test_variant_search_benchmark(benchmark, client, auth_headers):
    """基准测试：变异搜索 API"""
    result = benchmark(
        client.get,
        "/api/variants/search",
        params={"gene": "BRCA1"},
        headers=auth_headers,
    )
    assert result.status_code == 200

@pytest.mark.benchmark
def test_literature_search_benchmark(benchmark, client, auth_headers):
    """基准测试：文献搜索 API"""
    result = benchmark(
        client.post,
        "/api/literature/search",
        json={"query": "CRISPR", "providers": ["crossref"]},
        headers=auth_headers,
    )
    assert result.status_code == 200
```

### 监控与日志

#### 监控指标

- **应用指标**：请求速率、错误率、响应时间分布
- **系统指标**：CPU、内存、磁盘 I/O、网络 I/O
- **数据库指标**：连接池使用率、查询耗时、慢查询
- **Rust 扩展指标**：原生函数调用次数、耗时

#### 日志配置

```python
# app/core/logging.py
import logging
from pythonjsonlogger import jsonlogger

def setup_logging():
    logger = logging.getLogger()
    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        fmt='%(asctime)s %(name)s %(levelname)s %(message)s',
        rename_fields={'asctime': 'timestamp', 'levelname': 'level'},
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
```

### 关键配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `WORKERS` | Uvicorn worker 数量 | 4 |
| `DATABASE_POOL_SIZE` | 数据库连接池大小 | 20 |
| `DATABASE_MAX_OVERFLOW` | 连接池最大溢出 | 10 |
| `REDIS_MAX_CONNECTIONS` | Redis 最大连接数 | 50 |
| `LOG_LEVEL` | 日志级别 | INFO |
| `SENTRY_DSN` | Sentry 错误追踪 DSN | 可选 |

### 测试

```bash
# 基础设施测试
uv run pytest tests/test_infra.py -v

# Docker 构建测试
docker build -t test-backend .
docker run --rm test-backend python -c "import rust_io; print('OK')"

# 数据库迁移测试
uv run alembic upgrade head
uv run alembic downgrade base
uv run alembic upgrade head

# 性能基准测试
uv run pytest tests/benchmark/ --benchmark-only --benchmark-json=benchmark.json
```
