# 后端结构规范（BACKEND_STRUCTURE）

## 1. 架构分层
采用五层结构：
1. `presentation`：API 层（FastAPI 路由）
2. `service`：任务编排、状态聚合、权限校验
3. `domain`：子智能体节点逻辑（获取/解析/翻译/提取/ACMG）
4. `repository`：PostgreSQL/Qdrant/Neo4j/MinIO 访问
5. `infra`：Celery、Redis、SMTP、签名 URL、定时清理

## 2. 服务边界
### 2.1 主服务
1. 接收用户请求与上传
2. 生成 `request_id` 与 `paper_task_id`
3. 执行主工作流
4. 产出结构化证据与报告
5. 发送 KG 事件

### 2.2 KG 服务（独立）
1. 读取 PostgreSQL 结构化证据
2. 更新 Neo4j 图谱
3. 支持全量回灌与增量更新

## 3. 关键数据模型
### 3.1 task_requests（任务单）
最小字段：
1. `request_id` (UUIDv4, PK)
2. `user_id`
3. `raw_task_text`（自然语言任务单）
4. `parsed_slots`（结构化槽位）
5. `status`
6. `created_at`

补充建议字段：
1. `updated_at`
2. `release_no`
3. `source`（MVP=pubmed）

### 3.2 paper_tasks（文献任务）
核心字段：
1. `paper_task_id` (UUIDv4, PK)
2. `request_id` (FK)
3. `paper_sha256`
4. `status` (`queued/running/success/failed`)
5. `error_code`（可空）
6. `warning_codes`（数组，可空）
7. `duplicate_of`（历史 `paper_task_id`，可空）
8. `fulltext_unavailable`（bool）
9. `created_at/updated_at`

### 3.3 paper_task_logs（任务日志）
1. `log_id`
2. `paper_task_id`
3. `level`
4. `message`
5. `event_code`
6. `log_object_key`
7. `created_at`

### 3.4 sentence_alignments（对齐表）
固定字段：
1. `paper_id`
2. `src_lang`
3. `src_span`
4. `en_span`
5. `sentence_id`
6. `confidence`

### 3.5 evidence_outputs（证据结果）
核心字段：
1. `paper_task_id`
2. `inputs`
3. `outputs`
4. `evidence_spans`
5. `confidence`（0~1）
6. `errors`（结构化）
7. `created_at`

## 4. API 契约
### 4.1 创建请求
`POST /requests`
- 输入：任务意图、可选上传文件
- 输出：`request_id`, `status`

### 4.2 候选文献
`GET /requests/{request_id}/candidates?page=&page_size=`
- `page_size` 默认 10，最大 15
- 总候选 <=50
- 排序：时间 > 相关性 > 证据强度

### 4.3 提交执行
`POST /requests/{request_id}/execute`
- 输入：选中的文献 ID 列表（1~10）或上传文件列表
- 空选择且无上传：`failed + INPUT_INVALID`

### 4.4 状态查询
`GET /requests/{request_id}`
- 返回请求级状态与文献级汇总

`GET /paper-tasks/{paper_task_id}`
- 返回单篇状态、错误码、warning、`log_link`

### 4.5 日志链接重签发
`POST /paper-tasks/{paper_task_id}/log-link/reissue`
- 条件：登录用户
- 限流：每 `paper_task_id` 每分钟 1 次
- 返回：新签名 URL（24h）

### 4.6 删除项
- `quality API` 全量移除；旧路径返回 `404`

## 5. 请求与任务状态规则
### 5.1 请求级状态
1. `queued`
2. `running`
3. `partial_failed`：至少 1 成功且至少 1 失败
4. `failed`
5. `success`：全部成功，或全部 `FILE_DUPLICATE`

### 5.2 重复文件规则
1. 全库 SHA-256 匹配即重复
2. 新建 `paper_task_id`
3. `status=success`
4. `error_code=FILE_DUPLICATE`
5. `duplicate_of` 指向历史 `paper_task_id`

## 6. 工作流与重试实现
### 6.1 节点链路
1. 获取
2. 解析
3. 翻译
4. 提取
5. ACMG

### 6.2 节点重试参数
| 节点 | max_retries | delay | timeout |
|---|---:|---:|---:|
| 获取 | 2 | 300s | 900s |
| 解析 | 1 | 600s | 1800s |
| 翻译 | 2 | 120s | 1200s |
| 提取 | 2 | 300s | 1800s |
| ACMG | 1 | 180s | 900s |

### 6.3 失败处理
1. 自动重跑关闭
2. 失败后终止
3. 运维脚本可手动重开
4. 重开复用原 `paper_task_id`
5. 状态流 `failed -> queued -> running -> ...`
6. 写入日志 `reopened_by_ops_script`

## 7. 幂等与事件
### 7.1 幂等键
1. `req:{request_id}`
2. `req:{request_id}:paper:{paper_sha256}`
3. `req:{request_id}:paper:{paper_sha256}:step:{step}:v{schema_version}`

### 7.2 KG 事件
最小载荷：
`request_id, paper_id, step, status, timestamp, idempotency_key`

失败策略：
1. 进入重试队列
2. 重试参数沿用 ACMG 节点策略

## 8. 错误码规范
固定首版：
`INPUT_INVALID, FILE_TOO_LARGE, FILE_TYPE_UNSUPPORTED, FILE_DUPLICATE, FETCH_TIMEOUT, FETCH_NO_RESULT, FULLTEXT_UNAVAILABLE, PARSE_FAILED, OCR_FAILED, OCR_TIMEOUT, TRANSLATION_FAILED, TRANSLATION_EMPTY, ALIGNMENT_FAILED, ENTITY_EXTRACTION_FAILED, EVIDENCE_EXTRACTION_FAILED, ACMG_RULE_UNSUPPORTED, ACMG_PARSE_FAILED, GRAPH_SYNC_FAILED, TASK_TIMEOUT, INTERNAL_ERROR`

Warning：
`HGVS_AUTOCORRECT_FAILED`

## 9. 存储与保留
1. 任务单文本 + 结构化元数据：永久
2. 原始文件：不自动删（运维手工清理）
3. 解析中间文件：7 天
4. 运行日志：7 天

## 10. 指标采集与验收口径
1. 统计单位：发布号
2. 固定验收集：100 篇，发布内固定不变
3. 成功率：文献级 >=95%，分母包含 `FILE_DUPLICATE`
4. 单篇时长：<=30 分钟，从 worker 开始计时

## 11. 安全约束
1. `log_link` 签名 URL 24h 有效
2. 拿到链接可访问（已接受风险）
3. 重签发仅限已登录用户
4. 不提供匿名重签发
