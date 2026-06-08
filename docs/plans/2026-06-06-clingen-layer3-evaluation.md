# Plan: ClinGen-based Layer 3 Pipeline Evaluation

## 目标

利用 ClinGen 已有的基因-疾病有效性评审数据，构建自动化评估框架，衡量 pipeline 的证据提取准确性（Precision/Recall/F1）。

## 核心思路

```
ClinGen CSV (3,592 条评审)
    ↓ 选取代表性子集
提取 gene + disease + classification + MOI
    ↓ 构建 ground truth JSON
翻译成 zh/ja/ko/es/pt/ru（利用 pipeline 翻译能力）
    ↓ 生成多语言测试集
通过 pipeline 提取证据
    ↓ 对比
计算 P/R/F1 + 分类别准确率
```

## Phase 1: Ground Truth 数据集构建

### 1.1 从 ClinGen CSV 提取评审条目

**输入**: `database/terminology_database/clingen/Clingen-Gene-Disease-Summary.csv`

**选取策略**（30 条）:
| 分类 | 数量 | 选取理由 |
|------|------|----------|
| Definitive | 10 | 基线：最明确的基因-疾病关系 |
| Strong | 5 | 中等确定性 |
| Moderate | 5 | 需要更多证据 |
| Limited | 5 | 低确定性，测试边界 |
| Refuted/Disputed | 5 | 测试反面证据识别 |

**选取标准**:
- 优先选择有 PMC 全文的条目（可通过 EuropePMC API 查询）
- 覆盖不同 MOI（AD/AR/XL）
- 覆盖不同 GCEP（不同疾病领域）

### 1.2 Ground Truth JSON 格式

每条 ClinGen 评审对应一个 `expected.json`:

```json
{
  "clingen_id": "CGGV:assertion_xxx",
  "gene_symbol": "AARS1",
  "hgnc_id": "HGNC:20",
  "disease_label": "Charcot-Marie-Tooth disease axonal type 2N",
  "mondo_id": "MONDO:0013212",
  "moi": "AD",
  "classification": "Definitive",
  "gcep": "Charcot-Marie-Tooth Disease Gene Curation Expert Panel",

  "expected_evidence": [
    {"field_id": "A.gene_symbol", "value": "AARS1"},
    {"field_id": "B.disease_diagnosis", "value": "Charcot-Marie-Tooth"},
    {"field_id": "A.gene_disease_relationship", "value": "causative"},
    {"field_id": "B.diagnosis_sufficiency", "value": "definitive"}
  ],

  "expected_entities": {
    "gene": {"text": "AARS1", "hgnc_id": "HGNC:20"},
    "disease": {"text": "Charcot-Marie-Tooth disease", "mondo_id": "MONDO:0013212"}
  },

  "expected_standardization": {
    "gene": "HGNC:20",
    "disease": "MONDO:0013212"
  },

  "source_pmid": null,
  "source_pmc": null,
  "notes": "To be filled after literature lookup"
}
```

### 1.3 文献获取

对每条选取的 ClinGen 条目：

1. **查询 EuropePMC**：用 gene + disease 关键词搜索，获取 PMC 全文 PDF
2. **备选方案**：如果无 PMC 全文，使用 PubMed abstract（文本输入）
3. **记录来源**：PMID/PMC ID 写入 expected.json

**API**: `https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={gene}+{disease}&format=json&pageSize=5`

### 1.4 多语言翻译

对每篇英文原文：
1. 通过 pipeline Phase 2 翻译功能生成 zh/ja/ko/es/pt/ru 版本
2. 保存翻译后的 JSON（pipeline 已有此功能）
3. 翻译质量抽检（人工审核 2-3 篇）

**产出**: 每条 ClinGen 条目 → 1 篇英文 + 6 篇翻译 = 7 个测试用例

## Phase 2: Pipeline 提取与对比

### 2.1 提取流程

```python
for each ground_truth entry:
    for each language (en, zh, ja, ko, es, pt, ru):
        # 提交 PDF/文本到 pipeline
        run_id = submit_to_pipeline(pdf_or_text)
        wait_for_completion(run_id)

        # 从 DB 查询提取结果
        evidence_items = query_evidence_items(run_id)

        # 与 ground truth 对比
        metrics = compare(evidence_items, ground_truth)
```

### 2.2 对比指标

| 指标 | 计算方式 | 说明 |
|------|----------|------|
| **Gene Precision** | TP / (TP + FP) | 提取的 gene 中正确的比例 |
| **Gene Recall** | TP / (TP + FN) | 应提取的 gene 中找到的比例 |
| **Disease Precision** | 同上 | |
| **Disease Recall** | 同上 | |
| **Key Field F1** | 2·P·R/(P+R) | 关键字段综合得分 |
| **Entity Standardization Accuracy** | 正确标准化数 / 总标准化数 | Phase 3 准确性 |
| **Cross-lingual Consistency** | 非英文 vs 英文结果一致率 | 翻译鲁棒性 |

### 2.3 匹配逻辑

```python
def compare(extracted_items, ground_truth):
    # Key field matching
    for expected in ground_truth.expected_evidence:
        field_id = expected.field_id
        matches = [item for item in extracted_items
                   if item.field_id == field_id and item.status == "found"]
        if matches:
            # Value matching (fuzzy for disease names)
            best_match = max(matches, key=lambda m: m.confidence)
            if fuzzy_match(best_match.value, expected.value):
                tp += 1
            else:
                fp += 1  # Found but wrong value
        else:
            fn += 1  # Not found

    # Entity standardization matching
    for entity_type, expected_id in ground_truth.expected_standardization.items():
        # Check if pipeline resolved to the correct external ID
        ...
```

## Phase 3: 评估报告

### 3.1 报告结构

```json
{
  "evaluation_id": "eval_clingen_20260606",
  "timestamp": "2026-06-06T...",
  "dataset": {
    "total_entries": 30,
    "languages": ["en", "zh", "ja", "ko", "es", "pt", "ru"],
    "total_test_cases": 210
  },
  "overall_metrics": {
    "gene_f1": 0.85,
    "disease_f1": 0.78,
    "key_field_f1": 0.72,
    "entity_standardization_accuracy": 0.65,
    "cross_lingual_consistency": 0.82
  },
  "by_language": { ... },
  "by_classification": { ... },
  "by_moi": { ... },
  "per_entry_details": [ ... ]
}
```

### 3.2 可视化

- 按语言的 P/R/F1 柱状图
- 按 ClinGen 分类的准确率热力图
- 关键字段覆盖率雷达图
- 跨语言一致性折线图

## 实现步骤

| # | 任务 | 产出 | 依赖 |
|---|------|------|------|
| 1 | 从 ClinGen CSV 选取 30 条代表性条目 | `benchmark/layer3/ground_truth/selection.json` | ✅ done |
| 2 | 查询 EuropePMC 获取 PMID/PMC ID | `ground_truth/{id}/expected.json` | ✅ done |
| 3 | 下载 PMC 全文 (JATS XML → markdown) | `ground_truth/{id}/source.md` | ✅ done (30/30) |
| 4 | 通过 pipeline 翻译生成多语言版本 | — | ⏭ deferred: pipeline Phase 2 内部已处理 cross-lingual，track consistency 指标已实现 |
| 5 | 实现对比评估脚本 (含实体标准化+轨道一致性) | `benchmark/layer3/evaluate.py` | ✅ done |
| 6 | 运行 pipeline 提取 | PG 数据 | ✅ done (5 entries, 3 ✓ 2 ✗ MinerU timeout) |
| 7 | 执行对比评估 | 评估报告 JSON | ✅ done (F1=94.1%, StdAcc=100%, TrackCons=86.8%) |
| 8 | 生成可视化报告 | `benchmark/layer3/visualize.py` (HTML + 5 PNG) | ✅ done |

## 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| PMC 全文不可用 | 无法获取 PDF | 使用 abstract 文本输入 |
| 翻译质量差 | 非英文准确率低 | 人工抽检 + cross-lingual 指标 |
| ClinGen 字段映射不完全 | 评估不完整 | 优先评估 A/B 类核心字段 |
| Pipeline LLM 超时 | 测试用例失败 | 已优化 timeout/chunk |

## 预期产出

- 30 条 ClinGen 评审 × 7 语言 = **210 个测试用例**
- 覆盖 **6 种语言**（en + 5 非英文）
- 评估 **关键字段 P/R/F1**、**实体标准化准确率**、**跨语言一致性**
- 自动化评估脚本，可持续运行
