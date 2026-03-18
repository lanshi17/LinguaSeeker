# 常量与枚举单一来源（CONSTANTS）

> 本文档用于集中维护“冻结/约定不随实现漂移”的常量与枚举值。
> 其他文档若出现重复表格/列表，应改为引用本页对应小节。

## 1. 错误码（Error Codes）

基础错误码（冻结首版，20 个）：

`INPUT_INVALID, FILE_TOO_LARGE, FILE_TYPE_UNSUPPORTED, FILE_DUPLICATE, FETCH_TIMEOUT, FETCH_NO_RESULT, FULLTEXT_UNAVAILABLE, PARSE_FAILED, OCR_FAILED, OCR_TIMEOUT, TRANSLATION_FAILED, TRANSLATION_EMPTY, ALIGNMENT_FAILED, ENTITY_EXTRACTION_FAILED, EVIDENCE_EXTRACTION_FAILED, ACMG_RULE_UNSUPPORTED, ACMG_PARSE_FAILED, GRAPH_SYNC_FAILED, TASK_TIMEOUT, INTERNAL_ERROR`

## 2. Warning 码（Warning Codes）

`HGVS_AUTOCORRECT_FAILED`

## 3. 状态机（Status Sets）

### 3.1 请求级状态（Request Status）

`queued/running/partial_failed/failed/success`

### 3.2 文献级状态（Paper Status）

`queued/running/success/failed`

## 4. 节点级重试参数（Node Retry Parameters）

| 节点 | max_retries | delay | timeout |
|---|---:|---:|---:|
| 获取 | 2 | 300s | 900s |
| 解析 | 1 | 600s | 1800s |
| 翻译 | 2 | 120s | 1200s |
| 提取 | 2 | 300s | 1800s |
| ACMG | 1 | 180s | 900s |

## 5. 幂等键格式（Idempotency Keys）

1. 请求级：`req:{request_id}`
2. 文献级：`req:{request_id}:paper:{paper_sha256}`
3. 步骤级：`req:{request_id}:paper:{paper_sha256}:step:{step}:v{schema_version}`

## 6. KG 事件载荷最小字段（KG Event Payload Minimal Fields）

`request_id, paper_id, step, status, timestamp, idempotency_key`
