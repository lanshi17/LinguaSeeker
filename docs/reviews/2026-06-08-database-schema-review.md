# Database Schema Review & Optimization Plan

**Date**: 2026-06-08
**Reviewer**: AI Agent
**Scope**: 18 PostgreSQL tables (17 ORM + 1 read projection), 7 Alembic migrations, Redis cache layer

---

## 1. Overall Assessment

Schema 设计质量 **良好**：
- UUID 主键、JSONB 灵活载荷、部分唯一索引、循环 FK 处理均合理
- 表职责划分清晰，遵循垂直切片架构
- Alembic 迁移链完整，无断裂

但存在 **7 个缺失索引** 和 **1 个 N+1 查询** 需要修复。

---

## 2. Critical Issues

### 2.1 `canonical_evidence_items.active_payload['group_id']` — 无索引

**影响**: 搜索服务中 3 个核心查询均依赖此 JSONB 字段作为 WHERE 条件和 ORDER BY 排序键。

| 查询位置 | 用法 | 影响 |
|---|---|---|
| `search_service.py:154` | WHERE 过滤匹配 group_id | 全表扫描 |
| `search_service.py:176` | WHERE IN 加载匹配组的所有字段 | 全表扫描 |
| `search_service.py:296` | WHERE 精确匹配 group_id (detail) | 全表扫描 |
| `search_service.py:180` | ORDER BY group_id | 内存排序 |

**修复**: 添加 B-tree 表达式索引 `(active_payload->>'group_id')`。

### 2.2 `frontend_search_index` 搜索列 — 全部无索引

**影响**: 前端搜索栏的所有过滤条件均无法走索引。

| 列 | 查询方式 | 建议索引 |
|---|---|---|
| `pmid` | `=` 精确匹配 + ORDER BY | B-tree |
| `doi` | `=` 精确匹配 | B-tree |
| `gene_ids` | JSONB `?|` 数组重叠 | GIN |
| `variant_ids` | JSONB `?|` 数组重叠 | GIN |

### 2.3 N+1 查询：`upsert_canonical_evidence`

**位置**: `repositories.py:892-943`

```python
for row, spec in self._run_item_rows:
    statement = select(CanonicalEvidenceItem).where(...)  # ← 每条 run_item 一次 SELECT
    existing = (await self.session.execute(statement)).scalars().first()
```

**影响**: 处理 100 条证据条目 = 100 次 SELECT 查询。
**修复**: 批量预加载所有匹配的 CanonicalEvidenceItem，构建内存 lookup dict。

---

## 3. Medium Issues

### 3.1 ORDER BY 列缺少复合索引

| 表 | ORDER BY 列 | 前置 WHERE | 建议复合索引 |
|---|---|---|---|
| `chat_messages` | `created_at ASC` | `chat_session_id =` | `(chat_session_id, created_at)` |
| `chat_sessions` | `created_at DESC` | `processing_run_id =` | `(processing_run_id, created_at DESC)` |
| `review_audit_events` | `created_at DESC` | `canonical_evidence_id =` 或 `reviewer_id =` | 两个复合索引 |

### 3.2 `terminology_entries.external_id` 单列查询无索引

**问题**: 联合唯一约束 `(source_db, external_id)` 中 `source_db` 是前导列。当仅按 `external_id` 查询时（`repositories.py:692`, `repositories.py:971`），无法使用该索引。

**修复**: 添加 `external_id` 单列 B-tree 索引。

---

## 4. Low Issues (Noted, Not Fixed)

### 4.1 `search_service` 内存分页

搜索结果在 Python 中分组、排序、分页。数据量增长后需迁移到数据库层分页。当前数据量（百级）可接受。

### 4.2 Relationship 无 lazy loading 保护

当前代码全部使用显式 `select()` + `join()`，未触发 lazy loading。但缺少防护，未来可能误用。已添加 `lazy="raise"` 保护。

---

## 5. Additional Findings (Code Review Round 2)

| # | 文件 | 问题 | 修复 |
|---|---|---|---|
| F1 | `state_persistence.py:115` | `recover_orphaned_runs` 全表扫描，加载所有 run | 添加 `WHERE state_json->>'pipeline_status' IN (...)` 过滤 + JSONB 表达式索引 |
| F2 | `state_persistence.py:126` | `error_phase` 硬编码 0，丢弃实际运行 phase | 新增 `_derive_error_phase()` 从 `phase_N_status` 字段推导 |
| F3 | `state_persistence.py:127` | `datetime.now()` 产生 naive timestamp | 改为 `datetime.now(timezone.utc)` |
| F4 | `state_persistence.py:22` | `DirectStatePersistence` 缺少 `recover_orphaned_runs` | 添加 stub 方法（raise NotImplementedError） |
| F5 | `runner.py:69` | `error_phase` 可能为 None（orchestrator 未设置） | 添加 None 守卫，fallback 到 `_derive_error_phase()` |
| F6 | `models.py:555` | `pipeline_run_states.state_json` 缺少 JSONB 表达式索引 | 添加 `(state_json ->> 'pipeline_status')` B-tree 索引 |
| F7 | `migration` | `CREATE INDEX` 未设置 lock_timeout | 迁移开头添加 `SET lock_timeout = '30s'` |
| F8 | `repositories.py:904` | `tuple_().in_()` 无分块，>16K 行会触发参数限制 | 添加 5000 条/批的分块逻辑 |
| F9 | `models.py` | 复合索引未清理冗余单列索引 | 删除 4 个被复合索引完全覆盖的单列索引 |
| F10 | `main.py:96` | 恢复成功日志重复打印（WARNING + INFO） | 删除 `main.py` 中的冗余 INFO 日志 |
| F11 | `test_runner.py:257` | cancel 测试未断言 `persistence.save` 被调用 | 添加 `mock_persistence.save.assert_called()` |
| F12 | `test_runner.py:264` | 缺少 `error_phase=None` 的测试覆盖 | 新增 `test_cancelled_task_defaults_phase_when_orchestrator_did_not_set` |

---

## 6. Optimization Summary

| # | 类型 | 表 | 变更 | 优先级 |
|---|---|---|---|---|
| 1 | Index | `canonical_evidence_items` | B-tree on `(active_payload->>'group_id')` | Critical |
| 2 | Index | `canonical_evidence_items` | B-tree on `field_id` | Medium |
| 3 | Index | `frontend_search_index` | B-tree on `pmid`, `doi` | Critical |
| 4 | Index | `frontend_search_index` | GIN on `gene_ids`, `variant_ids` | Critical |
| 5 | Index | `chat_messages` | Composite `(chat_session_id, created_at)` | Medium |
| 6 | Index | `chat_sessions` | Composite `(processing_run_id, created_at DESC)` | Medium |
| 7 | Index | `review_audit_events` | 2× composite with `created_at DESC` | Medium |
| 8 | Index | `terminology_entries` | B-tree on `external_id` | Medium |
| 9 | Index | `pipeline_run_states` | B-tree on `(state_json->>'pipeline_status')` | Medium |
| 10 | Drop | `review_audit_events` | 2 redundant single-column indexes | Medium |
| 11 | Drop | `chat_sessions`, `chat_messages` | 2 redundant single-column indexes | Medium |
| 12 | Code | `repositories.py` | Fix N+1 in `upsert_canonical_evidence` + chunking | Critical |
| 13 | Code | `models.py` | Add `lazy="raise"` to all relationships | Low |
| 14 | Code | `state_persistence.py` | WHERE filter + error_phase derivation + tz-aware + LSP stub | Critical |
| 15 | Code | `runner.py` | None error_phase guard + tz-aware | Critical |
| 16 | Code | `main.py` | Remove duplicate recovery log | Low |

---

## 7. Existing Strengths (No Action Needed)

- **Partial unique indexes** on `normalized_entities`: 精妙地按 status 分区唯一性
- **NULLS NOT DISTINCT** on `terminology_relationships`: 正确处理 scalar assertion 去重
- **Circular FK with `use_alter`**: canonical_evidence_items ↔ run_evidence_items 正确处理
- **HNSW index** on `terminology_embeddings`: pgvector cosine distance 已优化
- **Read projection isolation**: `frontend_search_index` 使用独立 MetaData，不污染 Alembic
- **Redis cache layer**: 三级缓存 + 事务性失效设计合理
- **CHECK constraints** on confidence ranges: 数据库层保证值域
