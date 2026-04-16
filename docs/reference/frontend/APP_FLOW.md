# 前端应用流程（APP_FLOW）

## 1. 总览
前端当前采用 request-centric 流程：
1. 从 `/tasks/new` 完成任务澄清与确认。
2. 在同一页面进入 upload、PubMed、web crawl 三条 intake 分支。
3. 成功提交后统一进入 `/requests/:requestId` 监控请求状态。
4. 从请求页继续进入 `/documents/:documentId` 查看单文档证据。
5. `/graph` 作为独立图谱检索与控制页存在。

## 2. 入口流程
### 2.1 任务澄清与确认
1. 用户进入 `/tasks/new`。
2. 页面通过交互 Agent 完成最多 2 轮澄清。
3. 页面生成结构化任务单：目标、疾病、国家、语种。
4. 用户确认任务单后，后端返回 `request_id`。
5. 页面基于该 `request_id` 开放后续分支操作。

### 2.2 分支选择
1. **Upload**：在 `/tasks/new` 上传 PDF/DOCX，调用 `/api/v1/tasks/requests/upload`。
2. **PubMed**：跳转 `/tasks/pubmed/candidates`，检索并提交候选 PMID。
3. **Web crawl**：在 `/tasks/new` 输入 URL 列表，调用 `/api/v1/tasks/requests/web/crawl`。
4. 三条分支提交成功后都跳转 `/requests/:requestId`。

## 3. 请求监控页
### 3.1 `/requests/:requestId`
1. 展示请求聚合状态与 paper task 列表。
2. 使用 `/api/v1/tasks/requests/{request_id}` 读取状态。
3. 可使用 `/api/v1/tasks/requests/{request_id}/source-stats` 展示来源统计。
4. 通过 `WS /api/v1/stream/requests/{request_id}` 接收请求级实时状态。

## 4. 文档页
### 4.1 `/documents/:documentId`
1. 使用 `/api/v1/evidence/document/{document_id}` 加载文档证据。
2. 展示原文、译文、PS3/BS3 证据与图谱片段。
3. 文档页依附请求流转结果，不再依赖旧的分析式导航。

## 5. 图谱页
### 5.1 `/graph`
1. 图谱页主搜索接口为 `POST /api/v1/evidence/search`。
2. 页面同时使用 `GET /api/v1/evidence/graph/stats` 展示图统计。
3. 页面支持 `POST /api/v1/evidence/sync/document/{document_id}` 进行文档重同步。

## 6. 当前流程边界
1. 当前前端主流程以任务创建页、请求监控页、文档证据页、图谱页为核心。
2. PubMed 候选页属于确认后的分支页，而不是旧状态页的替代描述。
3. 旧 PDF fetch 说明不应再被视为当前前端主流程的一部分。
4. 当前后端前缀统一使用 `/api/v1`。
