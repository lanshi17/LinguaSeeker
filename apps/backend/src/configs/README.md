# src/configs 说明（代码对齐版）

`src/configs` 当前主要是兼容层（wrapper），用于兼容旧导入路径。

## 目录结构

```text
configs/
├── app_config.py
├── database_config.py
└── __init__.py
```

## 模块职责

- `app_config.py`
  - 兼容导出：`AppConfig`, `app_config`
  - 实际来源：`src.config`
- `database_config.py`
  - 兼容导出：`DatabaseConfig`, `MinIOConfig`, `database_config`
  - 实际来源：`src.config`
- `__init__.py`
  - 汇总导出上述兼容对象

## 推荐

新代码优先直接使用 `src.config`（`Settings` / `get_settings()` / `app_config`）。
