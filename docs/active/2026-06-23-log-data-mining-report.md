# 日志数据挖掘报告 — 警告与错误分布

> 工具：**drain3** 日志模板聚类（将变长 token 如时间戳/UUID/请求 ID 屏蔽后，按结构归并相似日志行）
> 范围：`logs/*.log` + `logs/*.log.gz`，共 **160,082** 行（INFO 113,487 / **WARNING 2,723** / **ERROR 450**）
> 聚类结果：3,173 条 WARNING/ERROR → **406 个模板**

---

## 一、根因分类（合并子簇后）

按 drain3 模板归并到根因桶，WARNING+ERROR 合计：

| 排名 | 条数 | 根因类别 | 级别 |
|---|---|---|---|
| 1 | 873 | trace pairing 轨迹配对跳过 | WARNING |
| 2 | 453 | Snippet 定位失败 → `SOURCE_INVALID` | WARNING |
| 3 | 296 | LLM API 余额不足 / 鉴权失败 (403) | WARNING |
| 4 | 272 | special_evidence 结构化输出失败 | ERROR |
| 5 | 271 | JSON-mode 429（`response_format` 不兼容） | WARNING |
| 6 | 181 | Phase 3 语义匹配连接失败（model-server 不可达） | WARNING |
| 7 | 137 | LLM 请求超时 | WARNING |
| 8 | 132 | model-server 401 未授权 | WARNING |
| 9 | 80 | LLM 格式化输出长度不匹配 | WARNING |
| 10 | 73 | Pipeline 阶段失败/取消 | ERROR |

> "余额不足"(403 code 30001) 与 "model-server 401" 在实际语义上是同一类——**外部 LLM 凭证/配额耗尽**，合计 ~560 条，是错误侧最大的系统性问题。

---

## 二、Top 模板（drain3 聚类后按频次）

| # | 条数 | 级别 | 模板（`<*>` = 被屏蔽的变量 token） |
|---|---|---|---|
| 1 | 614 | WARN | `Non-standard track value 'reconciled' for <*> <*> — skipping in trace pairing` |
| 2 | 272 | ERROR | `special_evidence chunk <*> failed: Stage <*> failed structured output` |
| 3 | 271 | WARN | `Stage <*> transient failure: Error code: 429 - 'messages' must contain the word 'json' ... response_format` |
| 4 | 261 | WARN | `LLM key <*> auth error, failover: Error code: 403 - 'code': 30001, 'message': 'Sorry, your account balance is insufficient'` |
| 5 | 259 | WARN | `No original/translated track found for <*> — skipping trace` |
| 6 | 156 | WARN | `Semantic matching service error for candidate <*> All connection attempts failed` |
| 7 | 110 | WARN | `Local <*> failed (Client error '401 Unauthorized' for url http://localhost:8001/v1/embeddings)` |
| 8 | 80 | WARN | `LLM format output length mismatch <*> vs <*> chars), keeping original` |
| 9 | 63 | WARN | `JSON stage <*> attempt <*> failed: Request timed out. Retrying in <*>` |
| 10 | 58 | WARN | `Heartbeat failed for run= <*> (consecutive failures: <*>)` |
| 11 | 38 | ERROR | `Phase <*> failed, stopping pipeline` |
| 12 | 37 | WARN | `Snippet <*> ... not found in document, marking SOURCE_INVALID`（453 条分散到多子簇） |

---

## 三、热点源码位置（`module:func:line`）

按发出 WARNING/ERROR 的代码位置聚合，最热的 12 处：

| 条数 | 级别 | 位置 |
|---|---|---|
| 335 | WARN | `extract_evidence.core:_ground_one:751` |
| 330 | WARN | `search_service:get_group_detail:713` |
| 271 | WARN | `extract_evidence.providers:ainvoke_structured:151` |
| 268 | ERROR | `special_evidence:run_async:141` |
| 191 | WARN | `extract_evidence.core:_ground_one:719` |
| 181 | WARN | `search_service:get_group_detail:706` / `:716` |
| 156 | WARN | `matchers:match:36`（Phase 3 语义匹配） |
| 103 | WARN | `search_service:get_group_detail:626` |
| 103 | WARN | `llm_adapter:ainvoke:101` |
| 80 | WARN | `formatter:_apply_llm_formatting:267` |
| 63 | WARN | `translate.providers:invoke_json_with_retry:182` |
| 59 | WARN | `similarity_match.providers:embed_texts:148` |

> 三个明显的"重灾区模块"：
> - **`search_service.get_group_detail`**（~990 条）—— L4 证据详情 API 反复触发 trace pairing 跳过告警
> - **`extract_evidence.core._ground_one`**（~580 条）—— snippet 源定位失败
> - **`special_evidence.run_async`**（272 ERROR）—— 结构化输出全链路失败

---

## 四、可行动建议（按收益排序）

### P0 — special_evidence 结构化输出（272 ERROR，第二大错误源）
- **位置**：`special_evidence.py:131` 用 `response_method="json_mode"` 调用 STRONG tier。
- **现象**：`Stage special_evidence failed structured output`，且同模板 #3 显示该 stage 触发 429 `response_format` 不兼容（模型不支持 `response_format=json_object`）。
- **根因**：`providers.ainvoke_structured` 在 `json_mode` 失败时不走 `_ainvoke_json_text` 回退（回退只对 `json_schema` 的 unsupported-format 异常生效，见 `providers.py:154`）；429 被当作 transient 重试耗尽后直接 `raise RuntimeError`。
- **修复方向**：对 `json_mode` 路径也接入 JSON-text 回退；或在 429/response_format 不兼容时降级到纯文本 JSON 解析。

### P0 — LLM 凭证/配额（~560 条，余额不足 403 + model-server 401）
- 403 `code 30001 余额不足` 来自主 LLM provider，触发 failover 但全部 key 都余额耗尽 → 级联成翻译/格式化/抽取全链路失败。
- model-server 401 来自 `localhost:8001/v1/embeddings`，Phase 3 语义匹配因此退化为纯精确匹配。
- **修复方向**：监控告警接入余额阈值；model-server 鉴权配置核对（开发环境是否漏配 API key）。

### P1 — trace pairing 跳过告警（873 条，最大 WARNING 源）
- `Non-standard track value 'reconciled' ... skipping in trace pairing`（614）+ `No original/translated track found`（259）。
- 这是 `search_service.get_group_detail` 在构建 original/translated 双轨证据时，遇到 `reconciled` 轨迹（既非 original 也非 translated）直接跳过并逐条告警。
- **修复方向**：`reconciled` 是合法的融合轨迹，trace pairing 逻辑应将其作为第三轨处理或静默跳过，而非逐条 WARNING 刷屏（990 条告警集中在此函数）。

### P1 — Snippet 源定位失败（453 条 → `SOURCE_INVALID`）
- `extract_evidence.core:_ground_one` 在文档中找不到 LLM 给出的引文片段，标记 `SOURCE_INVALID`。
- 大量 MECP2 `c.806del` 相关片段定位失败，说明 OCR/翻译后文本与原文片段漂移导致无法字面匹配。
- **修复方向**：放宽匹配（模糊匹配/归一化空白与标点），或对翻译轨迹改用对齐偏移而非字面子串。

### P2 — LLM 超时与长度不匹配（137 + 80）
- 翻译/格式化阶段超时重试（`invoke_json_with_retry`、`_apply_llm_formatting`）。
- 长度不匹配（输入 vs 输出字符数差异大）时 `keeping original` 放弃格式化——属降级行为，可降级为 DEBUG。
