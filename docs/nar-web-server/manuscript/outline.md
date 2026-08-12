# Lingua Seeker: A Multi-Agent Web Server for Cross-Lingual ACMG Evidence Curation

## 论文大纲

> **暂定标题:** Lingua Seeker: A Multi-Agent Web Server for Cross-Lingual Automated Evidence Curation for ACMG Variant Classification

---

## Abstract (~200 words)

**要点:**
- 问题：ACMG 变异分类需要大量人工文献证据搜集，非英语文献尤其被忽视
- 方案：LLM Multi-Agent 编排式流水线，四阶段自动化（文献获取→跨语言证据提取→实体标准化→专家审查）
- 创新点：跨语言双轨证据提取与融合；15+ 多源文献获取；Rust 原生 I/O 加速
- 结果：[Benchmark 数据占位]
- 可用性：免费公开 web server

---

## 1. Introduction

**目标:** ~1 页

### 要点
1. **背景:** ACMG/AMP 指南定义了变异分类的证据体系，但证据搜集耗时巨大
2. **痛点:**
   - 现有工具（Mastermind、Franklin、ClinVar Miner）仅覆盖英文文献
   - 非英语地区（中文、日文、俄文等）的遗传学文献被系统性忽视
   - 手工证据提取存在遗漏和主观偏差
3. **现有方案不足:**
   - Mastermind: 关键词检索，无语义理解，不支持中文文献
   - ClinVar Miner: 仅基于 ClinVar 数据库，不覆盖原始文献
   - LitVar: PubMed 检索为主，无全文证据提取
4. **Lingua Seeker 方案:**
   - LLM Multi-Agent 自动化全流程
   - 跨语言双轨证据提取（原文 + 译文并行）
   - 端到端流水线：从文献检索到 ACMG 结构化证据
   - Expert-in-the-loop 审查闭环

---

## 2. Materials and Methods

**目标:** ~1.5 页

### 2.1 System Architecture

- 编排式垂直切片架构（Orchestrated Vertical Slice Architecture）
- LangGraph 工作流编排 + Pydantic 状态管理
- Rust PyO3 原生扩展处理 HTTP I/O
- Vite + React + Ant Design 前端

**Figure 1: 系统架构图**（四阶段流水线 + 技术栈分层）

### 2.2 Phase 1: Literature Acquisition and Digitization

- 15+ 数据源（Crossref、PubMed、OpenAlex、EuropePMC、PMC、DOAJ、J-STAGE、Unpaywall + 6 国 Web Scrapers）
- Rust net-io 并行检索 + Python 业务编排
- MinerU 2.5 Pro 文档解析（PDF→Markdown + 表格 + 图片 + 布局坐标）

### 2.3 Phase 2: Cross-Lingual Dual-Track Evidence Extraction

- 语言检测 + 多阶段翻译（术语保持 → 结构对齐 → 草译 → 审校）
- 原文与译文双轨并行提取 ACMG 证据字段
- 多阶段提取流水线：目录提取 → 溯源定位 → 证据映射 → 分组聚合 → 质量审查
- 证据溯源：每条证据精确回溯到文档位置（页码 + 原文 span）

**Figure 2: 跨语言双轨证据提取流程图**

### 2.4 Phase 3: Entity Standardization and Knowledge Alignment

- 确定性精确匹配（HGNC、OMIM、HPO、ClinVar）
- 向量相似度匹配（BAAI/bge-m3 embedding + pgvector）
- 匹配结果分类：唯一匹配 / 多候选消歧 / 未映射

### 2.5 Phase 4: Expert-in-the-Loop Visualization

- 对话式入口（SSE 实时反馈）
- 证据工作台：左原文 + 右证据卡片对照视图
- Delta 审计日志：记录所有专家修正
- 导出：CSV / JSON / ACMG 分类报告

### 2.6 LLM Model Configuration

- 通用任务 LLM（配置化模型选择）
- 推理/验证 LLM（高精度场景）
- 多模态 LLM（图表/家系图解析）
- 模型通过 OpenAI-compatible API 接入

---

## 3. Web Server Usage

**目标:** ~1 页

### 要点
- 访问方式：[URL] 免费使用
- 核心交互流程：
  1. 输入（关键词/DOI/PMID/PDF 上传）
  2. 实时进度反馈（SSE）
  3. 证据审查与编辑
  4. 导出结构化报告
- 支持的文献语言：中文、英文、日文、俄文、韩文、西班牙文、葡萄牙文

**Figure 3: Web Server 界面截图**（聊天入口 + 证据工作台 + 证据库）

---

## 4. Results

**目标:** ~1 页

### 4.1 Benchmark Dataset

- 基于 ClinGen + ClinVar 融合金标数据集
- 30+ 篇文献（中英文混合）
- 评估字段：gene、disease、variant、inheritance、classification 等 ~10 个字段

### 4.2 Extraction Performance

| 指标 | 定义 | 目标 |
|------|------|------|
| Precision | 正确提取的证据 / 系统提取的总证据 | ≥ 0.80 |
| Recall | 正确提取的证据 / 金标总证据 | ≥ 0.70 |
| F1 | 调和平均 | ≥ 0.75 |
| Cohen's κ | 与专家一致性 | ≥ 0.70 |

**Figure 4: Benchmark 结果图**（分字段 P/R/F1 柱状图）

### 4.3 Cross-Lingual Comparison

- 中文文献 vs 英文文献的提取性能对比
- 双轨融合 vs 单轨提取的性能提升
- 案例展示：中文文献中独有证据的发现

### 4.4 System Performance

- 端到端处理时间（单篇文献）
- 多源检索覆盖率
- 实体标准化匹配率

---

## 5. Discussion

**目标:** ~0.5 页

### 要点
1. **优势:** 跨语言能力填补了非英语遗传学文献的证据空白
2. **局限:**
   - LLM 生成结果存在幻觉风险（通过溯源机制缓解）
   - 当前以证据提取为边界，不做自主分类
   - Recall 依赖文献获取覆盖度
3. **与现有工具对比:** [对比表]
4. **未来方向:** 双轨交叉验证自动化、主动学习反馈闭环、多模态深度整合

---

## References

- ACMG/AMP 指引 (Richards et al., 2015)
- ClinGen (Rehm et al., 2015)
- ClinVar (Landrum et al., 2014)
- Mastermind (Rao et al., 2017)
- LitVar (Allot et al., 2018)
- LangGraph (GitHub)
- MinerU (OpenDataLab)
- BGE embedding / reranker (BAAI)

---

## Figures 清单

| 编号 | 标题 | 类型 | 内容 |
|------|------|------|------|
| F1 | System Architecture | 架构图 | 四阶段流水线 + 技术栈分层 |
| F2 | Cross-Lingual Dual-Track Extraction | 流程图 | 双轨提取与融合机制 |
| F3 | Web Server Interface | 截图 | 聊天入口 + 证据工作台 + 证据库 |
| F4 | Benchmark Results | 柱状图 | 分字段 P/R/F1 |
| F5 (optional) | Case Study | 示例 | 中文文献证据提取全流程案例 |
