# ACMG 多语种代码级三臂实验

**Status:** in-progress

**Created:** 2026-08-14

**Scope:** 以同一原生非英语全文及其人工审校的英文全文为固定输入，衡量原文、英文 pivot 与双轨融合对可追溯 ACMG 准则事件恢复的影响。该实验不把抽取字段或 `assigned_acmg_codes` 当作正式临床裁决。

## 当前状态

实验基础设施和去重候选清单已经完成；正式模型运行尚未开始。当前本地 Rett 语料没有任何冻结、段落/表格对齐且经人工审校的英文全文译本，因此严格三臂可运行样本为 0。作者提供的英文摘要可以做质量锚点，但不能替代内容等价的英文全文臂。

这一停门是设计要求，不是失败：若直接比较英文摘要与中文全文，语言、篇幅和证据可见性会同时变化，无法归因给多语种能力。

## 已冻结的三臂

| Arm | 固定输入 | 测量的作用 |
|---|---|---|
| `english_pivot` | 同一原生全文的审校英文全文 | 内容等价英文阅读基线 |
| `native_only` | 原生非英语全文 | 原生语言直接阅读增益 |
| `dual_track` | 同一原生全文 + 同一审校英文全文 | 双轨融合增益 |

运行器将一次性物化 `original.json` 与 `translated.json`，随后复用同一双轨工件执行后端已有的 `original_only`、`english_pivot` 与 `dual` 模式。它不会为每个 arm 重新翻译文献。

## 代码级金标与分母

- 主单位：`目标变异 × 疾病断言 × ACMG 准则家族 × 独立来源/家系簇`。
- 每个 `source_family_id` 只贡献一个预先选择的 `index_assertion`；重复 PDF、文章别名和同一病例系列不能扩充分母。
- 金标与每个 arm 的决定分别保存。每个正式代码必须含规则前提、来源跨度、审阅者与强度。
- 每条 `SourceSpan` 必须标明其冻结输入工件：`original` 或 `translated`。`language` 只描述引文语言，不能替代工件归属；因此原文中的英文图注仍可被 `native_only` 合法引用。
- `source_eligibility` 和正式 `outcome` 分开：父母阴性但没有亲子关系确认可记录为 PM6-eligible 来源事实，但不能自动计为 PS2 或正式代码恢复。
- 主要报告精确正式代码/强度的 paired recall；同时报告 precision、false positive、配对 gained/lost event。统计推断须按去重来源/家系簇进行，不能把同一病例系列的多条变异当独立样本。

本期主终点代码家族为 `PS2_PM6`、`PM3`、`PP1_BS4`、`PS3_BS3` 与 `PS4`。PVS1 等依赖转录本、机制或外部数据库的准则不作为“仅凭当前文章即可确定”的主要终点。

## Pilot 候选与门禁

[候选清单](../../benchmark/experiments/acmg_multilingual/pilot_candidates.json) 固定了六个去重来源及其 `source.md` SHA-256：

| Canonical source | 语言 | 角色 | 别名 |
|---|---|---|---|
| `rett_006` | 中文 | 英文摘要已包含关键信息的负对照 | `rett_082` |
| `rett_007` | 中文 | 中文全文补充病例/父母阴性事实的正对照 | `rett_083` |
| `rett_011` | 中文 | 中文全文补充父母野生型事实的正对照 | `rett_087` |
| `rett_084` | 中文 | 英文摘要已含关键信息的负对照 | — |
| `rett_066` | 韩文 | 跨语种正对照 | — |
| `rett_004` | 中文 | 无作者英文摘要、须全译后才能纳入 | `rett_080` |

前五篇中的父母阴性记录都尚未报告亲子身份确认；第六篇也不应自动产生正式代码。它们当前均为 `needs_translation_review`，因此 CLI 会明确阻止物化、模型运行和裁决模板生成。

## 本地原文完整性复核

2026-08-14 对外部本地语料根执行了只读 `verify-sources`，其所属仓库版本为 `5b1f7673e7f4ea7922f3ad7efb79f25fdbfedab7`。六个候选的 `source.md` 都存在，且 SHA-256 与候选清单逐项相符；该结果由清单指纹 `f9879a49d67e32ccfec825799893fba7a66aa121945121af36543e879ad062b6` 绑定。

这只证明原生输入没有漂移，不证明译文或临床终点合格。审计未发现任一候选的英文全文译本、段落/表格对齐 JSON、两名审校者和日期。`approved/`、`draft/` 或 `ground_truth/` 等目录名，以及由模型生成的草稿元数据，均不构成人工译文审校证据。因此结果仍为 6 个原文已验证、0 个 `ready`，不得运行三臂模型或报告代码提升。

语料文件故意不纳入当前仓库；换环境时在拥有相同原文的本地 `<annotation-root>` 上重跑以下命令，并以清单中的内容哈希判定一致性：

```bash
cd backend
PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli verify-sources \
  --manifest ../benchmark/experiments/acmg_multilingual/pilot_candidates.json \
  --source-root <annotation-root> \
  --source-revision <external-corpus-revision> \
  --report <source-verification-report.json>
```

## 执行顺序

1. 用 `verify-sources` 确认本地原文与清单哈希一致；这一步不改变条目状态。
2. 在语料根目录下为每篇候选建立英文全文、逐段/表格对齐 JSON、译文 SHA-256 和两名审校者记录。
3. 为每个去重来源选择一个 index assertion，并预先指定待裁决的代码家族。
4. 将该条目改为 `ready`，物化固定输入并运行三臂。
5. 协调员从完整 arm 输出生成三个中性审阅包；只将 `reviewer-output-root` 交付 arm 决策审阅者，将 gold 模板和密封映射保留在独立的 `coordinator-output-root`。
6. 两名临床审阅者独立完成 gold，另行完成每个审阅包的正式代码决定；协调员收回三个完整包后，使用密封映射解盲并计分。

从仓库根目录运行时，所有 Python 命令都通过 backend 的 `uv` 环境：

```bash
cd backend
PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli verify-sources \
  --manifest ../benchmark/experiments/acmg_multilingual/pilot_candidates.json \
  --source-root <annotation-root> --source-revision <external-corpus-revision> \
  --report <source-verification-report.json>

PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli check-manifest \
  --manifest ../benchmark/experiments/acmg_multilingual/pilot_candidates.json

PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli materialize \
  --manifest <ready-manifest.json> --source-root <annotation-root> \
  --output-root <frozen-input-root> --report <materialization-report.json>

PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.run \
  --manifest <ready-manifest.json> --input-root <frozen-input-root> \
  --output-root <arm-output-root> --report <arm-run-report.json>

PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli create-templates \
  --manifest <ready-manifest.json> --arm-output-root <arm-output-root> \
  --reviewer-output-root <reviewer-packet-root> \
  --coordinator-output-root <coordinator-only-root>

PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli score \
  --manifest <ready-manifest.json> --gold <coordinator-only-root/gold_adjudication.json> \
  --reviewer-packet <reviewer-packet-root/packet-.../review_packet.json> \
  --reviewer-packet <reviewer-packet-root/packet-.../review_packet.json> \
  --reviewer-packet <reviewer-packet-root/packet-.../review_packet.json> \
  --coordinator-blinding-map <coordinator-only-root/blinding_map.json> \
  --report <code-recovery-report.json>
```

模型运行是显式命令，避免在配置、预算或人工审校未完成时发生外部调用。

## 审阅分配遮蔽的边界

审阅包的目录名、文件名、JSON 契约和协调员 CLI 均不含 arm 标签；包内模型输出也会拒绝含有 `english_pivot`、`native_only` 或 `dual_track` 的显式标签。包与密封 `BlindingMap` 必须位于互不嵌套的根目录，且映射还绑定每包的证据文件哈希。

这不是不可推断的完全盲法。为了让专家核对来源，输出中的引文语言、原始/译文轨迹或单/双轨内容可能使其推测分配。因此研究应把它报告为**分配标签遮蔽**；gold 审阅者尤其不得接触任何 arm 输出，主要保护来自独立 gold、预先冻结终点和可审计来源，而不是声称语言内容本身被隐藏。

## 已实现的保障

- `verify-sources` 在任何 pending 条目被提升前校验原文内容哈希，并输出绑定清单指纹的只读收据；它不能替代译文审校门禁。
- `SourceArtifact` 校验相对路径和 SHA-256；输入物化前再次验证内容、英文译文与对齐文件哈希。
- 物化或 arm 输出一律拒绝覆盖既有目录。
- 完整 manifest 强制全部三臂，并拒绝重复 `source_family_id`、断言 ID 和别名记录。
- `PS2` 只有在 `parentage_status=confirmed` 时才可被标为 qualified；所有 qualified 决定均要求事实 ID、来源跨度、前提完整性、准则和强度。
- 协调员将带 arm 标签的运行目录重打包为随机 `packet-<hex>` 审阅目录；结果哈希、包 ID 和密封映射必须一一对应，缺包、重复包、未完成决定或证据漂移都会阻止解盲和计分。
- 评分只接受三个完整中性审阅包经密封映射解盲后的人工正式代码决定，完全忽略 pipeline 的 `assigned_acmg_codes`。

## 验证

新增单元测试覆盖：pending 原文哈希验证、翻译审校门禁、PS2 亲子关系门禁、输入哈希漂移、物化输出、审阅包/密封映射隔离、输出标签泄漏、完整包解盲、三臂模式选择，以及精确代码/强度的 paired scoring。设置 `ACMG_MULTILINGUAL_ANNOTATION_ROOT` 后还会执行对忽略本地语料的 opt-in 集成验证。

```bash
cd backend
uv run ruff check ../benchmark/experiments/acmg_multilingual tests/benchmark/experiments/test_acmg_multilingual.py
PYTHONPATH=.. uv run --all-groups -- python -m pytest tests/benchmark/experiments/test_acmg_multilingual.py -q
```
