# Web Scraper Adapters (Archived)

**归档日期**: 2026-06-16  
**状态**: 已弃用，不再使用  
**原路径**: `backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/web/`

## 模块说明

此模块包含 9 个基于浏览器的 web 抓取适配器，用于处理需要 JavaScript 渲染的学术网站。这些适配器通过 crawl4ai + Playwright 实现自动化 UI 交互和结构化数据提取。

### 归档原因

- 维护成本高：每个站点需要独立的 XPath/CSS 定位器和 UI 交互流程
- 稳定性差：目标站点 UI 变更频繁导致定位器失效
- 性能瓶颈：浏览器自动化开销大，不适合大规模采集
- 替代方案：优先使用 Rust-based HTTP API 提供商（net_io）

### 原模块结构

```
web/
├── base.py           # 共享工具函数（crawl4ai_search、PDF下载、HTML解析）
├── locators.py       # XPath/CSS 选择器常量
├── pubscholar.py     # PubScholar（中文，中科院/国家科学图书馆）
├── chinaxiv.py       # ChinaXiv（中文预印本）
├── hans_publishers.py # Hans Publishers（中文期刊）
├── cyberleninka.py   # CyberLeninka（俄罗斯开放获取）
├── koreascience.py   # KoreaScience（韩国期刊）
├── redalyc.py        # Redalyc / La Referencia（西班牙语/葡萄牙语）
└── __init__.py
```

### 技术栈

- **crawl4ai** + **Playwright**: 浏览器自动化
- **selectolax**: HTML 解析备选方案
- **Rust net_io**: PDF 链接提取加速
- **LLMExtractionStrategy**: LLM 辅助结构化提取

### 迁移指南

如需恢复使用，可将此目录移回原位置：

```bash
mv docs/archive/deprecated-modules/web-scraper-adapters/web/ \
   backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/
```

但建议优先使用现有的 Rust-based 文献获取提供商（Crossref、OpenAlex、EuropePMC、PMC、DOAJ、JStage、Unpaywall）。

## 相关文档

- 原 README: `web/README.md`
- 文献获取网关: `backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/gateway.py`
- Rust I/O: `backend/libs/net-io/`
