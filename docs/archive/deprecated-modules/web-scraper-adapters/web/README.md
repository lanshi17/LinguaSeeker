# Web Scrapers

> 缺少公共 API 或需要 JavaScript 渲染的学术网站的基于浏览器的网页抓取器。每个抓取器实现特定区域学术出版商的搜索和下载功能。
>
> **状态：** 已弃用（2026-06-16 归档）。已被 Rust 实现的 `net_io` HTTP 提供商替代。

## 概述

本模块为 6 个区域学术平台提供浏览器自动化抓取能力。采用双层策略：优先尝试直接 HTTP（httpx，最快），失败时回退到浏览器自动化（crawl4ai）。

## 架构

```
web/
├── base.py           # 共享工具：crawl4ai_search、download_pdf_from_candidates、
│                     #   extract_pdf_links_from_html、scrape_html_elements、safe_json_loads
├── locators.py       # 每个站点 UI 元素的 XPath/CSS 选择器
├── pubscholar.py     # PubScholar（中文，CNIC/CAS）
├── chinaxiv.py       # ChinaXiv（中文预印本）
├── hans_publishers.py # Hans Publishers（中文期刊）
├── cyberleninka.py   # CyberLeninka（俄文开放获取）
├── koreascience.py   # KoreaScience（韩文期刊）
├── redalyc.py        # Redalyc / La Referencia（西/葡文）
└── __init__.py
```

## 公共 API

### `base.py` — 共享工具

| 函数 | 描述 |
|------|------|
| `safe_json_loads` | 解析 JSON，从混合内容中提取 |
| `extract_pdf_links_from_html` | 在 `<a href>` 和 `<meta citation_pdf_url>` 中查找 PDF URL |
| `scrape_html_elements` | 按 CSS 选择器提取元素 |
| `download_pdf_from_candidates` | 尝试候选 URL，验证 `%PDF` 魔术字节，保存首个有效 PDF |

### 提供商函数

每个提供商模块导出 `_search()` 和可选的 `_download()` 函数：

| 模块 | 提供商 | 语言 |
|------|--------|------|
| `pubscholar.py` | PubScholar | 中文 |
| `chinaxiv.py` | ChinaXiv | 中文 |
| `hans_publishers.py` | Hans Publishers | 中文 |
| `cyberleninka.py` | CyberLeninka | 俄文 |
| `koreascience.py` | KoreaScience | 韩文 |
| `redalyc.py` | Redalyc | 西/葡文 |

## 内部设计

- **Rust 优先 I/O**：所有 HTTP 调用优先通过 `rust_io.net`（连接池、异步 I/O），缺失时回退到 `httpx`
- **PDF 验证**：写入磁盘前检查 `%PDF` 魔术字节，无效下载静默跳过
- **Crawl4ai 集成**：对 JS 渲染站点，启动无头浏览器渲染页面后使用 `LLMExtractionStrategy` 提取结构化数据

## 依赖

| 依赖 | 用途 |
|------|------|
| `httpx` | 异步 HTTP 备选 |
| `selectolax` | 快速 HTML 解析（备选） |
| `crawl4ai` | JS 渲染站点的无头浏览器自动化 |
| `rust_io.net` | 主 HTTP I/O（Rust/PyO3） |
