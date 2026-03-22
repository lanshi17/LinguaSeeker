# ACMG-Lingua 多语种文献证据提取平台 - 文档中心

本目录包含 ACMG-Lingua 多语种文献证据提取平台的所有技术文档、设计文档和使用指南。

## 目录结构

```
docs/
├── README.md                     # 本文件
├── plans/                        # 实施计划和设计文档
│   ├── 2026-03-17-ignore-minio-data-design.md
│   └── ...
└── ...                           # 其他文档
```

## 文档分类

### 1. 产品文档

- **PRD.md** - 产品需求文档
- **APP_FLOW.md** - 应用流程图和说明
- **IMPLEMENTATION_PLAN.md** - 实施计划

### 2. 技术文档

- **TECH_STACK.md** - 技术栈说明
- **BACKEND_STRUCTURE.md** - 后端架构说明
- **FRONTEND_GUIDELINES.md** - 前端开发指南
- **EVALUATION_FRAMEWORK.md** - 评估框架文档

### 3. 开发指南

- **DEVELOPMENT_GUIDELINES.md** - 开发指南
- **TROUBLESHOOTING.md** - 故障排查指南
- **QUICKSTART.md** - 快速入门指南

### 4. API 文档

- **API 文档**: http://localhost:8000/docs (Swagger/OpenAPI)
- **OpenAPI Spec**: `/api_docs/openapi.json`

### 5. 实施计划

位于 `plans/` 子目录：

| 文档 | 日期 | 说明 |
|------|------|------|
| `2026-03-17-ignore-minio-data-design.md` | 2026-03-17 | MinIO 数据忽略设计 |

## 核心文档说明

### PRD.md - 产品需求文档

包含：
- 产品定位和目标
- 用户故事和使用场景
- 功能需求和非功能需求
- 验收标准

### TECH_STACK.md - 技术栈说明

包含：
- 前端技术栈 (React, TypeScript, Ant Design)
- 后端技术栈 (FastAPI, LangGraph, Python, uv)
- 数据库技术栈 (PostgreSQL, Neo4j, Qdrant, Redis, MinIO)
- LLM 架构 (8 个专用 Agent + 主力/仲裁双 LLM)
  - 8 个 Agent：retrieval, parsing, mt, format, vlm, evidence, classification, arbitration
  - 默认模型：Qwen 系列（qwen3.5-flash/plus/max, qwen-mt, qwen-vl）
  - 主力 LLM（可选）：DeepSeek
  - 仲裁 LLM（可选）：Claude
- 基础设施 (Docker, Kubernetes, MinIO)
- 语言检测：lingua-language-detector

### BACKEND_STRUCTURE.md - 后端架构说明

包含：
- 六边形架构说明
- 目录结构和模块划分
- 数据流和调用链
- 设计模式和最佳实践

### FRONTEND_GUIDELINES.md - 前端开发指南

包含：
- 组件开发规范
- 状态管理指南
- API 集成规范
- 样式和主题规范

### EVALUATION_FRAMEWORK.md - 评估框架文档

包含：
- ACMG-PS3 证据标准说明
- 评估流程和算法
- 质量控制指标
- 测试数据集

## 文档维护

### 文档更新流程

1. **创建/更新文档**
   - 使用 Markdown 格式
   - 遵循文档模板
   - 添加更新日期

2. **代码审查**
   - 文档变更需要代码审查
   - 确保信息准确
   - 检查链接有效性

3. **版本管理**
   - 文档与代码版本同步
   - 重大变更添加版本说明
   - 保留历史版本记录

### 文档命名规范

- 使用大写字母和下划线：`FEATURE_NAME.md`
- 计划文档添加日期前缀：`YYYY-MM-DD-description.md`
- 使用英文文件名（便于版本控制）

### 文档模板

```markdown
# 文档标题

## 概述

简要说明文档目的和范围。

## 背景

相关背景和上下文信息。

## 详细说明

详细内容，可包含：
- 架构图
- 流程图
- 代码示例
- 配置示例

## 使用指南

如何使用或实施。

## 相关文档

链接到相关文档。

---

**最后更新**: YYYY-MM-DD
```

## 文档检索

### 按主题查找

| 主题 | 文档 |
|------|------|
| 快速入门 | `QUICKSTART.md` |
| 开发环境搭建 | `README.md` (根目录) |
| API 使用 | http://localhost:8000/docs |
| 故障排查 | `TROUBLESHOOTING.md` |
| 架构说明 | `BACKEND_STRUCTURE.md` |

### 按角色查找

**开发者**:
- `DEVELOPMENT_GUIDELINES.md`
- `TECH_STACK.md`
- `BACKEND_STRUCTURE.md`
- `FRONTEND_GUIDELINES.md`

**产品经理**:
- `PRD.md`
- `APP_FLOW.md`
- `IMPLEMENTATION_PLAN.md`

**运维人员**:
- `deploy/README.md`
- `TROUBLESHOOTING.md`
- `docker-compose.yml`

## 外部资源

### 技术文档

- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
- [React 文档](https://react.dev/)
- [TypeScript 文档](https://www.typescriptlang.org/)
- [Ant Design 文档](https://ant.design/)

### 数据库文档

- [PostgreSQL 文档](https://www.postgresql.org/docs/)
- [Neo4j 文档](https://neo4j.com/docs/)
- [Qdrant 文档](https://qdrant.tech/documentation/)
- [Redis 文档](https://redis.io/docs/)

### LLM API 文档

- [Qwen API 文档](https://help.aliyun.com/zh/dashscope/)
- [DeepSeek API](https://platform.deepseek.com/docs)
- [Anthropic API](https://docs.anthropic.com/)

### 其他工具

- [MinerU 文档](https://github.com/opendatalab/MinerU)
- [Firecrawl 文档](https://docs.firecrawl.dev/)
- [lingua-language-detector](https://github.com/pemistahl/lingua-py)

## 贡献指南

欢迎贡献文档！请遵循以下步骤：

1. **Fork 项目**
2. **创建分支**: `git checkout -b feature/doc-update`
3. **提交变更**: `git commit -m 'docs: update XXX documentation'`
4. **推送分支**: `git push origin feature/doc-update`
5. **创建 Pull Request**

### 文档质量标准

- **准确性**: 信息准确无误
- **完整性**: 覆盖所有必要内容
- **清晰性**: 表达清晰易懂
- **一致性**: 格式和风格统一
- **时效性**: 及时更新过时内容

## 反馈与支持

如有文档相关问题，请：

1. 查看现有文档是否已有答案
2. 提交 Issue 描述问题
3. 提交 PR 修复文档

---

**最后更新**: 2026-03-22 (v3.0)
