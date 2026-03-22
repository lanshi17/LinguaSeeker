# src/utils 说明（代码对齐版）

本目录放置跨层通用工具，覆盖异常、日志、文件处理、计时、清洗与任务辅助。

## 目录结构

```text
utils/
├── exceptions.py
├── logger.py
├── file_utils.py
├── sanitizers.py
├── timer.py
├── pipeline_utils.py
├── evidence_annotation.py
├── celery_config.py
└── celery_tasks.py
```

## 模块概览

- `exceptions.py`
  - 统一异常类型（`ACMGException` 等）与安全执行辅助
- `logger.py`
  - 基于 loguru 的 `Logger` 包装
- `file_utils.py`
  - 下载、解压、目录扫描、临时目录维护
- `sanitizers.py`
  - 文件名、元数据、对象存储 key 清洗
- `timer.py`
  - 计时器/性能档案（支持装饰器与上下文）
- `pipeline_utils.py`
  - bbox 元数据、术语提取、结构化 payload 组装
- `evidence_annotation.py`
  - 证据引用定位与标注增强
- `celery_config.py` / `celery_tasks.py`
  - Celery 配置与 PDF 处理任务

## 说明

`utils` 同时服务新流程与历史兼容逻辑；改动通用工具时需评估跨模块影响。
