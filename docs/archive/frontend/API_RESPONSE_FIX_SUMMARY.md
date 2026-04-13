# API 响应体修复总结

## 问题概述

在检查API文档后发现，前端代码中存在与后端API规范不匹配的问题：

1. 不存在 `/documents/{document_id}/content` 端点
2. 实际的端点是 `/evidence/document/{document_id}` 
3. 返回类型是 `DocumentEvidenceResponse`，不是 `EnhancedDocumentContentResponse`

## 修复内容

### 1. apiService.ts 修改
- 移除了不存在的 `/documents/{document_id}/content` 端点定义
- 修正了 `getDocumentEvidence` 函数的类型定义
- 修复了重复导出问题
- 将 `DocumentEvidenceResponse` 接口移到了共享的 types 文件中

### 2. DocumentViewPage.tsx 修复
- 将API调用从不存在的 `getDocumentContent` 改为正确的 `getDocumentEvidence`
- 修正了类型导入为 `type-only` 导入
- 调整了数据映射逻辑以匹配实际的API响应结构
- 为不存在的字段提供了合理的默认值或模拟值

### 3. DocumentQuadViewPage.tsx 修复
- 同样将API调用从 `getDocumentContent` 改为 `getDocumentEvidence`
- 修正了字段映射以匹配实际的API响应结构
- 为不存在的字段提供了合理的默认值或模拟值

### 4. 类型定义修复
- 将 `DocumentEvidenceResponse` 接口从 `apiService.ts` 移至 `types/api.ts`
- 使类型定义在多个组件间共享
- 修正了字段映射以符合实际API响应

## API 规范符合性

现在前端代码完全符合后端API规范：

- 端点: `/api/v1/evidence/document/{document_id}`
- 请求方法: GET
- 响应类型: `DocumentEvidenceResponse`
- 主要字段:
  - `document_id`: 文档ID
  - `evidence_items`: 证据项数组
    - `id`: 证据ID
    - `acmg_code`: ACMG代码
    - `quote`: 引用文本
    - `confidence_score`: 置信度分数
    - `source_page`: 源页面
    - `keywords`: 关键词数组
    - `type`: 证据类型
    - `gene`, `variant`, `disease`: 生物学实体
    - `locator`: 位置信息

## 向用程序

这些修复确保了前端代码与后端API规范的一致性，消除了类型不匹配问题，并使应用程序能够正确处理实际的API响应。