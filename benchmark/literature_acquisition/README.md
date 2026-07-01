# Literature Acquisition Benchmark

> **状态：已弃用垫片。** 本包（`benchmark/literature_acquisition/`）仅包含 2026-06-18 框架重构后的向后兼容导入垫片。所有运行器代码已移至 `benchmark.runners.*`。垫片将在重构 Phase 6 移除。

## 概述

多语言文献下载基准测试，评估 LinguaSeeker 在线获取管线的提供商覆盖、下载成功率和文献类型分类，覆盖 7 种语言。

## 文件

| 文件 | 描述 |
|------|------|
| `__init__.py` | 已弃用垫片，`__getattr__` 重定向到 `benchmark.runners.*` |
| `downloads/` | 下载的 PDF（按语言子目录）+ 报告 JSON |

## 新模块位置

| 旧路径 | 新路径 | 用途 |
|--------|--------|------|
| `benchmark.literature_acquisition.benchmark` | `benchmark.runners.literature_acquisition` | 通用癌症/基因组学基准 |
| `benchmark.literature_acquisition.rett_download` | `benchmark.runners.literature_rett` | 疾病特定（Rett/MECP2）基准 |

实际运行器代码位于 `benchmark/runners/`：

| 文件 | 描述 |
|------|------|
| `benchmark/runners/literature_acquisition.py` | 通用基准：7 种语言、查询驱动、下载+分析+多语言 |
| `benchmark/runners/literature_rett.py` | Rett/MECP2 基准：配置驱动查询、清理、重命名、多语言 |

## 快速开始

```bash
cd backend

# 通用基准：按语言下载 PDF
uv run python -m benchmark.runners.literature_acquisition download

# 单语言
uv run python -m benchmark.runners.literature_acquisition download --lang zh

# 分析结果
uv run python -m benchmark.runners.literature_acquisition analyze
uv run python -m benchmark.runners.literature_acquisition analyze --llm-classify

# Rett 综合征 / MECP2（配置驱动）
uv run python -m benchmark.runners.literature_rett download --config rett_config_02.json

# Rett：种子查询生成
uv run python -m benchmark.runners.literature_rett seed-queries

# Rett：干运行
uv run python -m benchmark.runners.literature_rett download --config rett_config_02.json --dry-run

# Rett：清理 + 重命名
uv run python -m benchmark.runners.literature_rett cleanup --dry-run
uv run python -m benchmark.runners.literature_rett rename --dry-run
```

## 语言覆盖

通用基准覆盖 7 种语言，使用母语查询：

| 语言 | 查询类别 |
|------|---------|
| zh（中文） | 队列研究、功能实验、遗传/癌症、技术、遗传性癌症家系 |
| ja（日文） | 队列研究、功能实验、遗传/癌症、技术、遗传性癌症家系 |
| ko（韩文） | 队列研究、功能实验、遗传/癌症、技术、遗传性癌症家系 |
| en（英文） | 队列研究、功能实验、遗传/癌症、技术、遗传性癌症家系 |
| es（西班牙文） | 队列研究、功能实验、遗传/癌症、技术、遗传性癌症家系 |
| pt（葡萄牙文） | 队列研究、功能实验、遗传/癌症、技术、遗传性癌症家系 |
| ru（俄文） | 队列研究、功能实验、遗传/癌症、技术、遗传性癌症家系 |

## 提供商覆盖

| 语言 | 提供商 |
|------|--------|
| zh | crossref、unpaywall、doaj、pmc |
| ja | jstage、cinii、crossref、unpaywall、doaj、pmc |
| ko | crossref、unpaywall、doaj |
| es、pt | scielo、crossref、unpaywall |
| en | pmc、crossref、arxiv、biorxiv、medrxiv、openaire、base、core、unpaywall、doaj |
