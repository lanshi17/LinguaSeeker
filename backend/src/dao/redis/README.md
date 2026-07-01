# Redis — 异步读缓存

> 基于 redis.asyncio 的异步读缓存层，提供 JSON 序列化的命名空间缓存和事务性失效。

## 概述

`redis` 子包为 Lingua Seeker 提供读模型加速缓存。它使用 `redis.asyncio` 客户端，支持按命名空间前缀组织缓存键，并通过 Redis 事务性 pipeline 实现原子失效，防止部分网络故障导致脏缓存。

### 关键特性

- **异步操作** — 基于 `redis.asyncio.Redis`，支持 `await` 语义
- **命名空间缓存** — 按 `doc`/`canonical`/`entity`/`search` 前缀隔离键空间
- **JSON 序列化** — 缓存值以 JSON 字节存储，支持任意嵌套结构
- **事务性失效** — 使用 Redis pipeline 原子删除多个键，防止部分失效
- **懒加载导出** — `__getattr__` 避免未使用时触发 `redis.asyncio` 导入

## 目录结构

```
redis/
├── __init__.py       # 懒加载导出（CacheRepository、CACHE_PREFIX、build_redis_client）
├── connection.py     # 异步 Redis 客户端构建器
└── cache_repo.py     # CacheRepository：JSON 缓存 + 事务性失效
```

## 核心组件

### 连接构建（`connection.py`）

**`build_redis_client(settings)`** — 从 Settings 构建 `redis.asyncio.Redis` 客户端：
- 配置 host/port/password/db/max_connections
- `decode_responses=False`：缓存以原始字节存储，由消费方显式解码
- 单例生命周期由 `src.api.wiring` 管理

### CacheRepository（`cache_repo.py`）

Redis 缓存仓储，提供类型安全的读写操作：

**命名空间前缀（`CACHE_PREFIX`）：**
- `doc` — 文档级缓存
- `canonical` — 规范证据缓存
- `entity` — 实体缓存
- `search` — 搜索结果缓存

**公共方法：**
- `set(prefix, key, value, ttl=None)` — 设置缓存值（JSON 序列化）
- `get(prefix, key)` — 获取缓存值（JSON 反序列化）
- `delete(prefix, *keys)` — 删除一个或多个缓存键
- `invalidate(prefixes)` — 事务性批量失效：通过 pipeline 原子删除指定前缀的所有匹配键

## 数据流

```
应用层 (Service)
        │
        ▼
   CacheRepository
        │
        ├─→ set("doc", "123", {"data": ...})  →  JSON.dumps → SET doc:123
        ├─→ get("doc", "123")                  →  GET doc:123 → JSON.loads
        ├─→ delete("doc", "123", "456")        →  DEL doc:123 doc:456
        └─→ invalidate(["doc", "canonical"])   →  PIPELINE: KEYS + DEL (原子)
        │
        ▼
   Redis Server
```

## 使用方式

```python
from src.dao.redis import CacheRepository, build_redis_client

# 构建客户端
redis = build_redis_client(settings)
cache = CacheRepository(redis)

# 缓存读写
await cache.set("doc", "pmid:12345", {"title": "Example", "genes": ["BRCA1"]})
data = await cache.get("doc", "pmid:12345")

# 事务性失效
await cache.invalidate(["doc", "canonical"])  # 原子删除所有 doc:* 和 canonical:* 键
```
