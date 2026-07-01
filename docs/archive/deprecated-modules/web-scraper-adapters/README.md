# Web Scraper Adapters（已归档）

> **归档日期：** 2026-06-16
> **状态：** 已弃用，不再使用
> **原始路径：** `backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/web/`

## 概述

本模块包含 9 个基于浏览器的网页抓取适配器，用于需要 JavaScript 渲染的学术网站。适配器使用 crawl4ai + Playwright 进行自动化 UI 交互和结构化数据提取。

### 弃用原因

- **维护成本高：** 每个站点需要独立的 XPath/CSS 选择器和 UI 交互流程
- **稳定性差：** 目标站点 UI 变更频繁导致选择器失效
- **性能瓶颈：** 浏览器自动化开销使大规模获取不切实际
- **替代方案：** Rust 实现的 HTTP API 提供商（`net_io`）更可靠地处理相同站点

### 原始模块结构

```
web/
├── base.py           # 共享工具（crawl4ai_search、PDF 下载、HTML 解析）
├── locators.py       # XPath/CSS 选择器常量
├── pubscholar.py     # PubScholar（中文，CNIC/CAS）
├── chinaxiv.py       # ChinaXiv（中文预印本）
├── hans_publishers.py # Hans Publishers（中文期刊）
├── cyberleninka.py   # CyberLeninka（俄文开放获取）
├── koreascience.py   # KoreaScience（韩文期刊）
├── redalyc.py        # Redalyc / La Referencia（西/葡文）
└── __init__.py
```

### 技术栈

- **crawl4ai** + **Playwright**：浏览器自动化
- **selectolax**：HTML 解析备选
- **Rust net_io**：PDF 链接提取加速
- **LLMExtractionStrategy**：LLM 辅助结构化提取

### 迁移指南

如需恢复这些适配器，将归档目录移回原始位置：

```bash
mv docs/archive/deprecated-modules/web-scraper-adapters/web/ \
   backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/
```

但建议优先使用现有的 Rust 基础文献提供商（Crossref、OpenAlex、EuropePMC、PMC、DOAJ、JStage、Unpaywall）。

## 相关文档

- 提供商 README：`web/README.md`
- 文献获取网关：`backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/gateway.py`
- Rust I/O：`backend/libs/net-io/`
