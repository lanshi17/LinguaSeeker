# Change Control

## Scope
本文件是变更控制单一入口，合并原 `RELEASE_NOTES.md` 与 `BACKWARD_IMPACT.md`。

## Release Notes
### v1.0 (2026-03-22)

#### Summary
`v1.0` 基线从“单源 PubMed + 5 节点”升级为“多源获取 + 6 节点（含专家裁决）”。

#### Product/Workflow Changes
1. 主工作流由 5 节点调整为 6 节点：
   - 文献获取 -> 文档解析 -> 多语言处理 -> 证据提取 -> ACMG 分类 -> 专家裁决
2. 文献获取由单源 PubMed 调整为多源融合：
   - API：`biopython/pubmed`、`pmc`、`crossref`、`doaj`、`jstage`、`unpaywall`
   - Crawler：`hans_publishers`、`pubscholar`、`cyberleninka`
3. 输出结果要求升级为完整 JSON 溯源链。

#### Architecture Changes
1. `pdf-parser-service` 独立运行。
2. `translation-service` 独立运行。
3. `evidence-extraction-service` 独立运行。
4. 节点级重试从“固定矩阵”升级为“默认模板 + 兜底上限 + LLM 动态调度”。

#### Data/Storage Changes
1. 继续保留 `PDF/DOCX` 上传。
2. 翻译产物英文 `md` 持久化至 MinIO。
3. `BGE-M3` 向量写入 Qdrant。

## Backward Impact Statement (v1.0)

### 1. Impact Scope
本次变更影响以下维度：
1. 工作流节点数量与节点语义（5 -> 6）
2. 数据源策略（单源 -> 多源）
3. 重试策略（固定矩阵 -> 动态调度）
4. 服务拓扑（新增 3 个独立微服务边界）

### 2. API / Contract Impact
1. 请求/文献状态集合不变：`queued/running/partial_failed/failed/success` 与 `queued/running/success/failed`。
2. 错误码集合保持兼容（无删除）。
3. 响应体新增或强化 `source_trace`、节点溯源字段时，旧客户端需忽略未知字段。

### 3. Runtime/Infra Impact
1. 部署依赖新增：
   - `pdf-parser-service`
   - `translation-service`
   - `evidence-extraction-service`
2. 调度层需支持多源连接器与源级重试策略。
3. 监控面需新增 6 节点维度指标与来源健康指标。

### 4. Data Impact
1. `paper_tasks` 建议增加来源追踪字段（如 `source_trace`）。
2. 证据输出需落地节点级溯源链字段（如 `trace_chain`）。
3. 既有历史数据无需回写可运行，但旧记录不保证具备完整溯源字段。

### 5. Test/Acceptance Impact
1. 现有仅 PubMed 的集成测试需扩展到多源适配场景。
2. 5 节点流程断言需升级为 6 节点流程断言。
3. 验收口径（100 篇、成功率、时长）保持不变。

### 6. Rollback Strategy
1. 回滚时可禁用新增数据源并退回单源获取策略。
2. 回滚时可将专家裁决节点降级为 ACMG 分类后直接出结果。
3. 回滚期间保留新增字段，不执行破坏性删表或删列。
