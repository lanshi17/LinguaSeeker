# 多语种文献证据提取平台

## 项目简介

这是一个用于多语种文献证据提取的研究平台，旨在帮助研究人员从不同语言的学术文献中自动提取和整理相关证据。

## 目录结构

```
├── apps/                 # [核心代码] 具体的应用程序
│   ├── backend/          # 后端服务 (API, 微服务)
│   ├── frontend/         # 前端应用 (Web, Admin)
├── libs/                 # [共享库] 跨应用共享的代码 (工具类, UI组件库, 类型定义)
├── docs/                 # [文档中心] 架构图, API文档, 需求说明
├── deploy/               # [运维基础设施] Docker, K8s, Nginx配置
├── scripts/              # [自动化工具] CI/CD脚本, 数据库迁移脚本, 本地启动脚本
├── tests/                # [测试] 端到端测试 (E2E), 性能测试脚本
├── .gitignore            # Git忽略文件
├── README.md             # 项目入口说明书
└── docker-compose.yml    # 本地开发环境编排
```

## 开发环境搭建

### 环境要求

- Node.js >= 16.x
- Python >= 3.8
- Docker & Docker Compose
- PostgreSQL >= 13.x
- Redis >= 6.x

### 快速开始

1. 克隆项目代码
2. 安装依赖
3. 配置环境变量
4. 启动开发服务器

```bash
# 启动所有服务
docker-compose up -d
```

## 技术栈

- 前端: React + TypeScript + Ant Design
- 后端: Node.js/Python + Express/FastAPI
- 数据库: PostgreSQL + Redis
- 部署: Docker + Kubernetes

## 团队成员

- [lanshi] - [Architect] - [yhvguk@foxmail.com]

## 许可证

本项目采用 [MIT[ 许可证。详细信息请参阅 [LICENSE](LICENSE) 文件。
