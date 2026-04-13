# ACMG-Lingua 技术栈规范（TECH_STACK）

## 1. 总体原则
1. v1.0 优先稳定可运行，保留可追溯链路。
2. 工作流节点顺序固定，节点内工具调用可策略化。
3. 可观测性优先，所有节点输出需可回溯。

## 2. 架构与组件选型
| 层级 | 组件 | 选型 | 说明 |
|---|---|---|---|
| API 服务 | Web 框架 | FastAPI | 对外 REST API |
| 工作流编排 | Agent Orchestration | LangGraph | 单篇文献 6 节点子流程编排 |
| 异步任务 | Queue | Celery + Redis | 每篇文献一个任务，Redis 缓存 |
| 文献获取 | Multi-source Connectors | API + Crawler Adapters | API 与爬取多源融合 |
| 文档解析微服务 | Parser Service | MinerU API | 主解析引擎，输出结构化 md/jpg |
| OCR 回退 | OCR Fallback | PaddleOCR-VL-1.5 | MinerU 失败时回退 |
| 多语言微服务 | Translation Service | `MT_MODEL` + BGE-M3 | 翻译 + 向量化入 Qdrant |
| 证据提取微服务 | Extraction Service | scispaCy + LlamaIndex | 实体、关系、实验信息提取 |
| 检索增强 | Hybrid Retrieval | Keyword + Qdrant + Juniper Reranker | `juniper-bge-reranker-large_v2` 精排 |
| ACMG 分类 | LLM + RAG | `ARBITRATION_MODEL` | 基于 ACMG 知识库分类（PS3/BS3） |
| 专家裁决 | LLM + RAG | `ARBITRATION_MODEL` | 证据强度裁决与说明 |
| 关系存储 | OLTP | PostgreSQL | 任务/证据/对齐等结构化数据 |
| 向量检索 | Vector DB | Qdrant | 保持现状，不迁移 pgvector |
| 图数据库 | Graph DB | Neo4j | KG 服务图谱存储 |
| 对象存储 | Object Storage | MinIO | 原始文件、处理中间产物 |
| 身份验证 | Email Verify | SMTP（第三方） | 邮箱验证码 |

## 3. 数据源策略（v1.0）
### 3.1 API 数据源
1. `biopython/pubmed`
2. `pmc`
3. `crossref`
4. `doaj`
5. `jstage`
6. `unpaywall`

### 3.2 网页爬取源
1. `hans_publishers`
2. `pubscholar`
3. `cyberleninka`

### 3.3 调度策略
1. 数据源调用顺序由调度智能体动态决定。
2. 源级重试由调度智能体在策略范围内执行。
3. 节点级默认重试模板与兜底上限见 `docs/CONSTANTS.md`。

### 3.4 合规边界
1. 仅合法来源与授权访问。
2. 付费墙失败时降级到摘要级证据并标记 `fulltext_unavailable`。

## 4. 模型路由
按任务类型路由：
1. 文献获取：非 LLM（调度智能体仅做源选择与重试策略）
2. 文档解析：非 LLM（MinerU/PaddleOCR）
3. 翻译：`MT_MODEL`
4. 证据提取：`EVIDENCE_MODEL` + scispaCy/LlamaIndex 工具链
5. ACMG 分类：`ARBITRATION_MODEL`
6. 专家裁决：`ARBITRATION_MODEL`

## 5. 任务与状态设计
### 5.1 ID 规范
1. `request_id`: UUIDv4
2. `paper_task_id`: UUIDv4

### 5.2 请求状态
`queued/running/partial_failed/failed/success`

### 5.3 文献状态
`queued/running/success/failed`

### 5.4 重复文件策略
1. 全库 SHA-256 去重
2. 命中后新建 `paper_task_id`
3. `status=success` + `FILE_DUPLICATE`
4. 响应返回 `duplicate_of=<历史paper_task_id>`

## 6. 重试策略
**单一来源**：见 [`docs/CONSTANTS.md`](CONSTANTS.md)。

补充：
1. 源级调用与重试可由 LLM 动态编排。
2. 节点级失败默认终止，支持运维脚本重开。

## 7. 幂等策略
**单一来源**：见 [`docs/CONSTANTS.md`](CONSTANTS.md)。

## 8. 错误码与告警
**单一来源**：见 [`docs/CONSTANTS.md`](CONSTANTS.md)。

## 9. 存储策略
### 9.1 PostgreSQL
1. 任务单与结构化元数据：永久
2. 对齐表：永久
3. 证据与任务记录：永久

### 9.2 MinIO
1. 原始文件：不自动删除（允许运维手动清理）
2. 解析与翻译中间文件：7 天保留

### 9.3 日志
1. 运行日志：7 天保留
2. 失败日志通过签名链接访问

## 10. 日志访问与安全
1. `log_link` 签名 URL 有效期 24h
2. 到期支持重签发
3. 重签发限流：每 `task_id` 每分钟 1 次
4. 访问范围：任意已登录用户可用

## 11. KG 服务技术约束
1. KG 独立服务部署
2. 主服务通过 Celery 事件触发 KG 更新
3. KG 服务从 PostgreSQL 拉取证据数据
4. 初次支持全量回灌脚本（断点续跑）
5. 失败进入重试队列，沿用专家裁决节点默认重试模板

## 12. 验收口径技术化定义
1. 发布号维度统计（`v1.0`）
2. 固定 100 篇验收清单（同发布号内不变）
3. 文献级成功率 >=95%，`FILE_DUPLICATE` 计入分子和分母
4. 单篇时长 <=30 分钟，计时起点为 worker 开始执行时间
