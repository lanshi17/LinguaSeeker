# src/tools 说明（代码对齐版）

`src/tools` 当前定位为“工具导出层”，多数文件不直接实现逻辑，而是对 `domain`/`infrastructure` 的统一 re-export。

## 目录结构

```text
tools/
├── db/
│   ├── neo4j_tool.py
│   ├── postgres_tool.py
│   └── qdrant_tool.py
├── external/
│   ├── clinvar_tool.py
│   └── translation_api.py
└── file/
    ├── minio_tool.py
    └── pdf_parser.py
```

## 导出内容

- `db/*`
  - 导出 `Neo4jClient`、`PostgresClient`、`QdrantManager` 及初始化函数
- `external/clinvar_tool.py`
  - 导出 `VariationDataService`、`ClinVarClient`
- `external/translation_api.py`
  - 导出翻译相关入口（来自 parsing translation 工具）
- `file/minio_tool.py`
  - 导出 `MinIOClient`
- `file/pdf_parser.py`
  - 导出 `DocumentParsingAgent`、`MinerUComponent`、`run_paddleocr_fallback`

## 说明

如果需要看真实实现，请顺着导出路径进入 `src/domain/*` 或 `src/infrastructure/*`。
