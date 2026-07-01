# BIBM Main Paper TeX Draft

> **状态：** in-progress
> **创建日期：** 2026-06-15

## 概述

本目录包含 BIBM 主论文的 IEEEtran 格式 TeX 手稿："LinguaSeeker: Source-Grounded Cross-Lingual Evidence Extraction for Clinical Genetics Literature"。

## 文件列表

| 文件 | 描述 |
|------|------|
| `main.tex` | 匿名双栏 IEEE 会议草稿。包含摘要、引言、相关工作、方法、实验和结果章节。报告统一 150 条目基准上的默认宽工作流：P=65.5%、R=33.6%、F1=44.4%，150/150 完成。还包含外部系统定位表和范围敏感性分析。 |
| `refs.bib` | BibTeX 参考文献 |
| `figures/method_figure.tex` | TikZ 矢量方法图：宽工作流的源文档和翻译输入分支、主提取、审查验证、标准化/源定位、实体标准化和读模型 |
| `figures/source_dataset_metrics.tex` | TikZ 分组柱状图：按来源数据集的精确率、召回率和 F1 |

## 构建说明

- 使用 `\documentclass[conference]{IEEEtran}` 适配 BIBM 提交格式
- 方法名宏：`\methodname` 展开为 `LinguaSeeker`；`\bmode` 展开为 `broad`
- 表格保持紧凑和科学风格
- 图表为灰度友好、示意性设计
- 范围敏感性数据由 `benchmark/analysis/paper_artifacts/summarize_unified_b8_scope.py` 生成
