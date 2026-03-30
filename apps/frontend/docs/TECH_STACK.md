# 技术栈规范（TECH_STACK）

## 1. 总体原则
1. MVP 优先稳定可运行，不做超范围技术迁移。
2. 关键链路可追踪、可重放、可排错。
3. 以现有代码基础为主，新增能力按模块扩展。

## 2. 架构与组件选型
| 层级 | 组件 | 选型 | 说明 |
|---|---|---|---|
| API 服务 | Web 框架 | FastAPI | 对外 REST API |
| 工作流编排 | Agent Orchestration | LangGraph | 单篇文献子流程编排 |
| 异步任务 | Queue | Celery + Redis | 每篇文献一个任务 |
| 文档解析 | Parser | MinerU API | 主解析引擎 |
| OCR 回退 | OCR Fallback | PaddleOCR-VL-1.5 | MinerU 失败时回退 |
| 翻译模型 | LLM | `MT_MODEL` | 多语言转英文 |
| 证据提取模型 | LLM | `EVIDENCE_MODEL` | 实体与证据关系抽取 |
| ACMG 判定模型 | LLM | `ARBITRATION_MODEL` | PS3/BS3 判定 |
| 关系存储 | OLTP | PostgreSQL | 任务/证据/对齐等结构化数据 |
| 向量检索 | Vector DB | Qdrant | 保持现状，不迁移 pgvector |
| 图数据库 | Graph DB | Neo4j | KG 服务图谱存储 |
| 对象存储 | Object Storage | MinIO | 原始文件、处理产物 |
| 身份验证 | Email Verify | SMTP（第三方） | 邮箱验证码 |

## 3. 数据源策略
### 3.1 MVP 启用
1. PubMed（官方 API）

### 3.2 后续规划（MVP 不落地）
1. CNKI
2. medRxiv / bioRxiv
3. J-STAGE
4. CyberLeninka
5. Thieme Connect
6. LIVIVO

### 3.3 合规边界
1. 仅合法来源与授权访问
2. 付费墙失败时只做摘要级证据并标记 `fulltext_unavailable`

## 4. 模型路由
按任务类型路由：
1. 文献获取：非 LLM
2. 文档解析：非 LLM（MinerU/PaddleOCR）
3. 翻译：`MT_MODEL`（主）+ `.env.local` 备选
4. 证据提取：`EVIDENCE_MODEL`（主）+ `.env.local` 备选
5. ACMG：`ARBITRATION_MODEL`（主）+ `.env.local` 备选

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

## 6. 节点级重试策略（固定）
| 节点 | max_retries | delay | timeout |
|---|---:|---:|---:|
| 获取 | 2 | 300s | 900s |
| 解析 | 1 | 600s | 1800s |
| 翻译 | 2 | 120s | 1200s |
| 提取 | 2 | 300s | 1800s |
| ACMG | 1 | 180s | 900s |

补充：
1. 自动重跑关闭，最终失败默认终止。
2. 仅运维脚本可手动重开（复用原 `paper_task_id`）。

## 7. 幂等策略
1. 请求级：`req:{request_id}`
2. 文献级：`req:{request_id}:paper:{paper_sha256}`
3. 步骤级：`req:{request_id}:paper:{paper_sha256}:step:{step}:v{schema_version}`

## 8. 错误码与告警
### 8.1 基础错误码（20 个）
`INPUT_INVALID, FILE_TOO_LARGE, FILE_TYPE_UNSUPPORTED, FILE_DUPLICATE, FETCH_TIMEOUT, FETCH_NO_RESULT, FULLTEXT_UNAVAILABLE, PARSE_FAILED, OCR_FAILED, OCR_TIMEOUT, TRANSLATION_FAILED, TRANSLATION_EMPTY, ALIGNMENT_FAILED, ENTITY_EXTRACTION_FAILED, EVIDENCE_EXTRACTION_FAILED, ACMG_RULE_UNSUPPORTED, ACMG_PARSE_FAILED, GRAPH_SYNC_FAILED, TASK_TIMEOUT, INTERNAL_ERROR`

### 8.2 Warning
`HGVS_AUTOCORRECT_FAILED`

## 9. 存储策略
### 9.1 PostgreSQL
1. 任务单与结构化元数据：永久
2. 对齐表：永久
3. 证据与任务记录：永久

### 9.2 MinIO
1. 原始文件：不自动删除（允许运维手动清理）
2. 中间文件：7 天保留

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
5. 失败进入重试队列，沿用 ACMG 节点级重试参数

## 12. 验收口径技术化定义
1. 发布号维度统计（非模型版本、非 git tag）
2. 固定 100 篇验收清单（同发布号内不变）
3. 文献级成功率 >=95%，`FILE_DUPLICATE` 计入分子和分母
4. 单篇时长 <=30 分钟，计时起点为 worker 开始执行时间
