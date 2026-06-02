# Pipeline Benchmark 增强计划

## 任务背景

现有 `benchmark/pipeline/benchmark.py` 已实现 HTTP 提交 + 轮询 + 报告生成，但存在两个不足：
1. 数据源仅支持 `manifest.json`（指向 `literature_acquisition/downloads/`），不支持 `benchmark/pipeline/input/` 目录下 159 份用户上传 PDF
2. 缺少 PG 入库证据指标 — 当前报告仅包含耗时和阶段状态，无法评估管线的证据提取质量

**目标**：增强 benchmark 脚本，以 `benchmark/pipeline/input/` 为输入源，跑真实 E2E 管线，以 PG 入库的证据项数量/质量为核心性能指标，生成基线报告。

## 任务列表

### 任务 1: 添加 input 目录扫描器 ✅

**目标**：自动发现 `benchmark/pipeline/input/{lang}/{type}/*.pdf`，生成 manifest 数据结构。

**步骤**：
1. 在 `benchmark/pipeline/benchmark.py` 中添加 `scan_input_dir()` 函数
2. 扫描 `benchmark/pipeline/input/` 目录结构 `{lang}/{literature_type}/*.pdf`
3. 返回与现有 `load_manifest()` 兼容的 `list[dict]` 结构
4. CLI 添加 `--source` 参数：`input`（默认，扫描 input 目录）| `manifest`（使用现有 manifest.json）
5. 添加 `--lang` 过滤参数，支持单语言运行

**验证**：`--dry-run --source input` 列出全部 159 份 PDF 及其语言/类型/大小。

### 任务 2: 添加 PG 证据指标查询模块 ✅

**目标**：管线完成后，通过 `processing_run_id` 查询 PG 中的证据入库指标。

**步骤**：
1. 新建 `benchmark/pipeline/evidence_metrics.py`
2. 使用 async SQLAlchemy 连接 PG（复用 `backend/src/dao/postgresql/connection.py` 的 `build_async_engine`）
3. 实现 `query_evidence_metrics(session_factory, processing_run_id) -> EvidenceMetrics`：
   - `run_evidence_count`：`run_evidence_items` 表中该 run 的证据总数
   - `canonical_evidence_count`：`canonical_evidence_items` 表中该文档的规范证据数
   - `entity_binding_count`：`evidence_entity_bindings` 表中该 run 的实体绑定数
   - `track_breakdown`：按 track（original/translated）分组的证据数
   - `status_breakdown`：按 status 分组的证据数
   - `avg_confidence`：平均置信度
   - `field_coverage`：提取到的不同 field_id 数量
4. 使用 dataclass `EvidenceMetrics` 作为返回类型（遵守规则 22）

**验证**：对已有报告中 `passed` 的 `processing_run_id` 手动运行查询，确认返回非零指标。

### 任务 3: 增强报告结构 ✅

**目标**：在 benchmark 报告中嵌入每篇 PDF 的 PG 证据指标和汇总统计。

**步骤**：
1. `PdfResult` dataclass 添加 `evidence_metrics: EvidenceMetrics | None` 字段
2. 管线完成后（terminal status = `awaiting_review`），调用 `query_evidence_metrics()` 获取指标
3. `generate_report()` 增加：
   - `by_evidence` 汇总：总证据数、平均证据数/PDF、平均置信度、字段覆盖率
   - 每条 result 中嵌入 `evidence_metrics` 对象
4. 控制台摘要输出添加证据指标行

**验证**：运行 `--limit 1 --source input --lang en`，检查报告 JSON 中包含 `evidence_metrics` 字段。

### 任务 4: 端到端集成验证

**目标**：用 1 篇 PDF 跑完整 E2E 流程，验证全链路。

**步骤**：
1. 确保后端服务运行中（`uv run uvicorn app.main:app`）
2. 运行 `uv run python -m benchmark.pipeline.benchmark --source input --lang en --limit 1`
3. 检查：
   - PDF 从 `input/en/` 被正确发现
   - 管线成功提交并轮询到 `awaiting_review`
   - PG 中查到 `run_evidence_items` 记录
   - 报告 JSON 包含 `evidence_metrics`
   - 控制台输出证据摘要

**验证**：报告文件中 `results[0].evidence_metrics.run_evidence_count > 0`。

## 关键设计决策

| 决策 | 选择 | 理由 |
|---|---|---|
| PG 连接方式 | 复用 `build_async_engine()` | 与项目现有模式一致，避免重复配置 |
| input 扫描 vs manifest | 两者并存，`--source` 切换 | 保持向后兼容，manifest 用于精选子集 |
| 证据指标收集时机 | 管线成功后立即查询 | 失败的管线无证据可查，避免无效查询 |
| 报告格式 | 在现有 JSON 结构上扩展 | 保持与现有报告分析工具兼容 |

## 依赖

- 后端服务必须运行（API + PG）
- `benchmark/pipeline/input/` 目录已有 PDF 文件（已确认 159 份）
- PG 中已有术语数据（Phase 3 标准化依赖）

---

*计划生成时间: 2026-06-02*
