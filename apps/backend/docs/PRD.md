# 多语种遗传证据平台 PRD

## 1. 文档信息
- 文档名称：Product Requirements Document (PRD)
- 项目代号：Multi-ACMG Evidence Platform
- 版本口径：按发布号统计（例如 `v1.0.0`）
- 当前状态：MVP 规格冻结

## 2. 产品目标与优先级
- 第一优先目标：可解释性（重点为“证据来源可解释性”）
- 目标用户：遗传咨询师、临床医生、研究员
- 使用场景：科研方法展示与验证

## 3. 用户与权限
- 业务用户权限：统一权限（不区分遗传咨询师/临床医生/研究员）
- 运维权限：独立体系，不在业务用户权限模型内
- 登录注册：
1. 邮箱注册
2. SMTP 邮箱验证码验证
3. 验证码有效期 5 分钟
4. 重发限制 1 分钟（按邮箱维度）
5. 每邮箱每天最多 20 次验证码请求
6. 密码策略：至少 8 位，且同时包含字母、数字、特殊字符

## 4. MVP 范围
### 4.1 In Scope
1. 交互 Agent 将模糊意图转换为任务单
2. 主流程 5 节点：文献获取 -> 文档解析 -> 多语言处理 -> 证据提取 -> ACMG 判定
3. 支持用户上传文献并跳过爬取
4. 每篇文献独立 Celery 任务
5. 请求级聚合与进度追踪
6. 证据冲突并列展示（按文献粒度）
7. PDF 合并导出（对照阅读页 + 证据表/ACMG/冲突说明）
8. KG 独立服务（先存库，后续服务从 PG 更新图谱）

### 4.2 Out of Scope（MVP）
1. 质量评估智能体（已移除）
2. `quality API`（删除，对外调用返回 `404`）
3. 非 PubMed 的生产级文献抓取实现（仅保留规划）
4. pgvector 迁移（MVP 保留 Qdrant）

## 5. 核心业务规则
### 5.1 交互任务单
- 输出形式：自然语言任务单
- 固定字段：`目标`、`疾病`、`国家`、`语种`
- 澄清轮次：最多 2 轮，之后按默认值自动执行
- 任务单落库：是（永久保存文本与结构化元数据）
- 默认值白名单（首版）：
1. `country=不限`
2. `language=auto`
3. `source=pubmed`
4. `candidate_limit=15`
5. `select_limit=10`
6. `fulltext_policy=fulltext_first_then_abstract`
7. `time_range=10y`

### 5.2 国家与数据源
- 国家判定方式：语种识别 + 数据库来源（非作者单位/研究对象地）
- 国家映射表使用 ISO 代码
- 英语组首批：`US, UK, CA, AU, NZ, IE, SG, IN, ZA, NG`
- 中文组首批：`CN, SG, MY, HK, MO, TW`
- 未覆盖国家：返回 `FETCH_NO_RESULT`
- MVP 数据源：仅 `PubMed`（前端仅显示 pubmed，其余隐藏为规划中）
- 不允许在 MVP 中降级为“语种近似国家过滤”

### 5.3 文献候选与选择
- 候选列表排序：`时间 > 相关性 > 证据强度`
- 候选总上限：15
- 分页：`default_page_size=10`，`max_page_size=15`
- 用户选择范围：最少 1 篇，最多 10 篇
- 用户未选择且未上传：返回 `failed + INPUT_INVALID`
- 用户只选 1 篇：立即执行，不再追问

### 5.4 上传与去重
- 上传格式：PDF、DOCX
- 上传限制：最多 10 个文件、单文件 <=10MB、总大小 <=50MB
- 去重策略：全库 `SHA-256`（按单个 PDF）
- 命中重复行为：
1. 新建 `paper_task_id`
2. `paper_task.status=success`
3. 标记 `FILE_DUPLICATE`
4. 跳过处理
5. 响应返回 `duplicate_of=<historical_paper_task_id>`
- `FILE_DUPLICATE` 计入成功率分子与分母
- 若一次请求全部为重复文件：请求级状态为 `success`

### 5.5 解析与翻译
- 文档格式支持：PDF 扫描版、PDF 文本版、DOCX
- OCR 语言：中、日、英、法、德、俄
- OCR 策略：优先 MinerU；MinerU 失败回退 PaddleOCR-VL-1.5（解析节点内部）
- DOCX 解析失败：直接失败
- 解析范围：正文 + 表格 + 图注
- 翻译策略：全文翻译；原文已英文则跳过
- 专有名词：以英文为准
- 对齐策略：支持 1:N / N:1；使用 alignment 表存储
- 坐标策略：英文优先，同时保留原文坐标
- 翻译破坏 HGVS/基因符号：
1. 先自动纠正
2. 纠正失败仍继续流程
3. 附加 `warning_code=HGVS_AUTOCORRECT_FAILED`

### 5.6 证据提取与 ACMG
- 关系抽取最小单元：句级
- 支持跨句合并推理
- 必须标注否定与不确定语气
- 标准化体系：
1. 变异：HGVS（GRCh38，转录本优先级 `RefSeq > Ensembl > UCSC`）
2. 基因：HGNC
3. 疾病：MONDO/OMIM/MeSH（优先级 `MONDO > OMIM > MeSH`）
4. 疾病无法映射：允许自由文本节点并标记 `unmapped`
- ACMG：
1. 先采用 2015 基线
2. MVP 只输出 PS3/BS3
3. 全自动判定
4. 输出规则触发明细
- 冲突处理：保留全部结论并标注冲突；按文献粒度并列展示；允许 `VUS`
- 付费墙无法获取全文：降级为元数据 + 摘要级证据，标记 `fulltext_unavailable` 并落库

### 5.7 报告与展示
- 页面 1：原文-英文对照阅读，实体标注（双语同时高亮）
- 页面 2：证据表 + ACMG 判定 + 冲突说明
- 导出：两个页面合并为一个 PDF

## 6. 技术与流程约束
- 工作流编排：LangGraph（单篇文献粒度）
- 异步执行：Celery（每篇文献一个任务）
- 请求聚合：`request_id` 管理多个 `paper_task_id`
- ID 格式：`request_id`、`paper_task_id` 均为 UUIDv4
- 节点重试策略（固定）：
1. 文献获取：`max_retries=2, delay=300s, timeout=900s`
2. 文档解析：`max_retries=1, delay=600s, timeout=1800s`
3. 多语言翻译：`max_retries=2, delay=120s, timeout=1200s`
4. 证据提取：`max_retries=2, delay=300s, timeout=1800s`
5. ACMG判定：`max_retries=1, delay=180s, timeout=900s`
- 失败处理：默认终止；可由运维脚本手动重开（复用原 `paper_task_id`）
- 运维重开状态流转：`failed -> queued -> running -> ...`
- 重开次数：不设上限
- 运维重开日志：记录普通任务日志 `reopened_by_ops_script`

## 7. 状态机定义
### 7.1 请求级状态
- `queued`
- `running`
- `partial_failed`（至少 1 成功且至少 1 失败）
- `failed`
- `success`（所有入选文献成功；或全部重复且跳过）

### 7.2 文献级状态
- `queued`
- `running`
- `success`
- `failed`

## 8. 错误码与告警

**单一来源**：见 [`docs/CONSTANTS.md`](CONSTANTS.md)（错误码 / warning 码）。

## 9. 幂等与事件

**单一来源**：见 [`docs/CONSTANTS.md`](CONSTANTS.md)（幂等键格式 / KG 事件载荷最小字段）。
- KG 失败处理：重试队列（沿用 ACMG 节点级重试策略）
- KG 首次上线：支持“全量回灌 + 增量更新”，脚本触发，支持断点续跑

## 10. 数据保留策略
- 任务单文本与结构化元数据：永久
- 原始文件：不自动删除（允许运维手动清理）
- 解析中间文件：7 天
- 运行日志：7 天

## 11. 安全与访问
- `log_link`：签名临时 URL，有效期 24 小时
- 过期后允许重签发
- 重签发限流：每 `task_id` 每分钟 1 次
- 重签发访问者：任意已登录用户可调用

## 12. 合规边界
- 仅使用合法来源与授权访问
- 不设计、不接入绕过版权/付费墙方案

## 13. 验收标准（MVP）
1. 支持 6 种语言（中英日法德俄）
2. 固定验收集 100 篇（同发布号内清单锁定不变）
3. 文献级成功率 >=95%（分母包含 `FILE_DUPLICATE`）
4. 单篇端到端时长 <=30 分钟（从 worker 开始计时）
5. 请求、文献、日志、报告、错误码链路完整可追踪
