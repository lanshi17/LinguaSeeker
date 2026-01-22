# 文档翻译前端应用

基于React+TypeScript+Ant Design的文档翻译前端界面

## 功能特性

1. **PDF文档翻译**
   - 支持PDF文件上传（最大50MB）
   - 自动检测文档语言
   - 实时翻译进度跟踪
   - 翻译结果预览和下载

2. **直接文本翻译**
   - 在线文本输入和即时翻译
   - 支持多种语言对
   - 快速响应

3. **任务管理**
   - 翻译任务状态监控
   - 进度条显示
   - 自动轮询更新
   - 任务取消功能

## 支持的翻译语言

- English (en)
- Chinese (zh)
- Japanese (ja)
- Korean (ko)
- French (fr)
- German (de)
- Spanish (es)

## 技术栈

- **前端框架**: React 18
- **开发语言**: TypeScript
- **UI组件库**: Ant Design 5
- **HTTP客户端**: Axios
- **路由**: React Router 6
- **构建工具**: Create React App

## 项目结构

```
frontend/
├── public/                  # 静态资源
├── src/
│   ├── components/         # 通用组件
│   ├── pages/             # 页面组件
│   ├── services/          # API服务
│   ├── utils/             # 工具函数
│   ├── hooks/             # 自定义Hook
│   ├── App.tsx            # 主应用组件
│   ├── index.tsx          # 应用入口
│   └── index.css          # 全局样式
├── package.json           # 依赖配置
└── tsconfig.json         # TypeScript配置
```

## 快速开始

### 1. 安装依赖

```bash
cd apps/frontend
npm install
```

### 2. 环境配置

确保后端服务运行在 `http://localhost:8000` 或修改 `package.json` 中的代理配置：

```json
{
  "proxy": "http://localhost:8000"
}
```

### 3. 启动开发服务器

```bash
npm start
```

应用将在 `http://localhost:3000` 启动

### 4. 构建生产版本

```bash
npm run build
```

## 开发指南

### API接口

前端与后端交互的主要API端点：

- `POST /api/translations/upload` - 上传PDF文件并创建翻译任务
- `GET /api/translations/tasks/{task_id}` - 获取翻译任务状态
- `POST /api/translations/translate-text` - 直接翻译文本
- `GET /api/translations/users/{user_id}/tasks` - 获取用户任务列表
- `DELETE /api/translations/tasks/{task_id}` - 取消翻译任务

### 关键组件

1. **PDFUploader组件**
   - 支持拖拽上传
   - 文件类型和大小验证
   - 上传进度显示

2. **TranslationTask组件**
   - 任务状态实时更新
   - 进度条动画
   - 错误处理

3. **LanguageSelector组件**
   - 语言选择器
   - 多语言支持

### 状态管理

应用使用React状态管理：

- **本地状态**: 使用 `useState` 管理组件内部状态
- **API状态**: 使用异步函数处理API请求
- **轮询机制**: 使用 `setInterval` 实现任务状态轮询

## 样式指南

### 颜色方案

- 主色: `#1890ff` (Ant Design Blue)
- 成功色: `#52c41a` (Green)
- 警告色: `#fa8c16` (Orange)
- 错误色: `#f5222d` (Red)
- 文本色: `#000000e0` (Primary), `#00000073` (Secondary)

### 响应式设计

- **桌面端**: 1200px以上 - 两栏布局
- **平板端**: 768px-1199px - 自适应布局
- **移动端**: 767px以下 - 单栏垂直布局

## 开发脚本

| 命令 | 说明 |
|------|------|
| `npm start` | 启动开发服务器 |
| `npm run build` | 构建生产版本 |
| `npm test` | 运行测试 |
| `npm run eject` | 弹出配置 |

## 与后端集成

1. **代理配置**: 开发时通过代理访问后端API，避免跨域问题
2. **API调用**: 使用 `fetch` 或 `axios` 发送HTTP请求
3. **错误处理**: 统一错误处理机制，显示用户友好的错误信息
4. **认证**: 目前使用简单的用户ID标识，可按需扩展JWT认证

## 浏览器支持

- Chrome 80+
- Firefox 75+
- Safari 13+
- Edge 80+

## 性能优化

- 代码分割：按需加载组件
- 图片优化：使用合适格式和尺寸
- API请求：请求合并和缓存
- 渲染优化：避免不必要的重渲染

## 扩展建议

1. **国际化**：添加i18n支持多语言界面
2. **主题切换**：支持暗黑模式
3. **离线功能**：使用PWA技术
4. **批量处理**：支持多个文件批量翻译
5. **历史记录**：保存用户翻译历史

## 问题排查

### 常见问题

1. **无法连接到后端**
   - 检查后端服务是否运行
   - 确认代理配置正确
   - 查看浏览器控制台网络请求

2. **文件上传失败**
   - 检查文件大小限制
   - 确认文件格式为PDF
   - 查看服务器日志

3. **样式异常**
   - 检查Ant Design版本兼容性
   - 确认CSS导入顺序
   - 查看浏览器兼容性

## 许可证

MIT License