# NAR Benchmark 数据准备 - 执行状态

**创建日期:** 2026-08-09
**最后更新:** 2026-08-09 22:20

---

## 执行进度

### Phase A: 数据基础准备 ✅ DONE

| 步骤 | 状态 | 说明 |
|------|------|------|
| A1: 符号链接 benchmark/data | ✅ | NAR 工作树 -> 主仓库 |
| A2: 符号链接 database/terminology_database | ✅ | NAR 工作树 -> 主仓库 |
| A3: 符号链接 backend/config/vault | ✅ | 复制 development.yaml |
| A4: 修复 select_fused_entries.py 路径 | ✅ | `/data/[redacted-user]/...` -> `_REPO_ROOT` |
| A5: 修复所有 clinvar_fused 脚本的 OUTPUT_DIR | ✅ | 6 个文件改为 `benchmark/data/ground_truth/clinvar_fused` |
| A6: 下载 ClinGen CSV | ✅ | 1.1MB, 2367 Definitive+Strong 条目 |
| A7: 下载 ClinVar TSV | ✅ | 421MB 压缩 -> 3.7GB 解压, 193564 高置信度变异 |

### Phase B: 重建 Fused-75 金标数据集 ✅ DONE (翻译进行中)

| 步骤 | 状态 | 说明 |
|------|------|------|
| B1: select_fused_entries.py | ✅ | 75 条, 1512 候选中选 75 |
| B2: fetch_variant_literature.py | ✅ | 75/75 PMC 文献命中 |
| B3: download_articles.py | ✅ | 75/75 source.md 下载完成 |
| B4: 合并 20 条裁定标注 | ✅ | 10 dev + 10 test, source_visible gold |
| B5: 中文翻译 (translate_to_multilingual) | 🔄 | 2/75 完成, 预计 2-3 小时 |

### Phase C: 构建统一数据集 manifest ⏳ PENDING

| 步骤 | 状态 | 依赖 |
|------|------|------|
| C1: 从 fused-75 映射到 unified 条目 | ⏳ | 需要确定映射关系 |
| C2: 生成 manifest.json | ⏳ | C1 |

### Phase D: 批量运行 Pipeline ⏳ PENDING

| 步骤 | 状态 | 依赖 |
|------|------|------|
| D1: 启动后端服务 | ⏳ | 需要用户操作 |
| D2: 运行批量 pipeline (75 条) | ⏳ | D1 + B5 |
| D3: 运行多语言评估 | ⏳ | D2 + B5 |

### Phase E: 评估与报告 ⏳ PENDING

| 步骤 | 状态 | 依赖 |
|------|------|------|
| E1: 运行 evaluate_fused.py | ⏳ | D2 |
| E2: 跨语言对比评估 | ⏳ | D3 |
| E3: 生成论文图表 | ⏳ | E1 + E2 |

---

## 数据集统计

### Fused-75 选样分布

| 维度 | 分布 |
|------|------|
| ClinGen Classification | Definitive: 74, Strong: 1 |
| MOI | AR: 26, AD: 24, MT: 17, XL: 6, SD: 2 |
| Review Stars | 3★: 73, 4★: 2 |
| 变异数/条目 | 3 variants: 74, 1 variant: 1 |
| 文献来源 | 75/75 PMC OA (100%) |
| 裁定标注 | 20/75 (10 dev + 10 test) |

### 基因覆盖 (部分)

CFTR, ABCA4, ACADVL, ACTA1, ADA, APC, ATM, BMPR2, BRCA1, BRCA2,
CDKL5, CYP1B1, DCLRE1C, DICER1, DNM2, F8, F9, FOXG1, FOXN1,
GAA, GJB2, GP1BA, GP1BB, GP9, GUCY2D, HBB, HNF4A, HTT, IDUA,
IL2RG, IL7R, ITGA2B, JAK3, KCNQ1, KCNQ4, LDLR, MECP2, MLH1,
MSH2, MSH6, MT-ATP6, MT-CO2, MT-CO3, MT-CYB, MT-ND1, MT-ND3,
MT-ND5, MT-ND6, MT-TK, MT-TL1, MT-TN, MT-TS1, MT-TW, MTM1,
MTOR, MYBPC3, MYH7, MYO15A, MYO7A, MYOC, NEB

---

## 下一步行动

1. **等待中文翻译完成** (~2-3h, 后台运行中)
2. **启动后端服务** (用户操作): `cd backend && uv run uvicorn app.main:app --reload`
3. **运行批量 pipeline**: `PYTHONPATH=.:backend python -m benchmark.datasets.clinvar_fused.run_nar_benchmark --base-url http://localhost:8000 --concurrency 3 --write`
4. **生成评估报告**: 上一步会自动输出三层指标
