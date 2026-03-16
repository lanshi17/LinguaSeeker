# Multi-ACMG 前端项目修复建议

## 当前状态
- 前端开发服务器运行正常（端口5173）
- 后端服务连接正常（端口8000）
- 可以进行开发工作，但生产构建失败

## 构建错误分析及修复方案

### 1. D3.js 类型错误修复

**错误示例**：
```
src/components/graph/ForceGraph/ForceGraph.tsx(94,5): error TS2322: Type 'Simulation<NodeWithPosition, undefined>' is not assignable to type 'Simulation<SimulationNodeDatum, undefined>'
```

**修复方法**：
```typescript
// 在 ForceGraph.tsx 文件中，修改类型声明
import { SimulationNodeDatum } from 'd3';

// 将 NodeWithPosition 接口扩展 SimulationNodeDatum
interface NodeWithPosition extends SimulationNodeDatum {
  id: string;
  label: string;
  type: string;
  // 其他必要属性
}
```

### 2. DOM 元素类型错误修复

**错误示例**：
```
Argument of type 'EventTarget | null' is not assignable to parameter of type 'string'
```

**修复方法**：
```typescript
// 添加类型检查
const target = event.target as HTMLElement;
if (target instanceof Element) {
  // 安全地使用 target
  d3.select(target);
}
```

### 3. DocumentData 属性访问错误修复

**错误示例**：
```
Property 'parsed_data' does not exist on type 'DocumentData'
```

**修复方法**：
```typescript
// 在类型定义文件中添加相应属性
interface DocumentData {
  parsed_data?: any; // 或更具体的类型定义
  author?: string;
  journal?: string;
  year?: number;
  // 其他相关属性
}
```

### 4. NodeJS 类型错误修复

**错误示例**：
```
Cannot find namespace 'NodeJS'
```

**修复方法**：
```bash
npm install @types/node --save-dev
```

然后在 tsconfig.json 中确保包含 node 类型：
```json
{
  "compilerOptions": {
    "types": ["vite/client", "node"]
  }
}
```

### 5. 通用修复步骤

1. **更新类型定义**：
```bash
npm install @types/node --save-dev
```

2. **修复类型定义文件** (`types/index.ts`)：
   - 确保 EntityType 定义一致
   - 添加缺失的接口定义

3. **修复 ForceGraph 组件**：
   - 解决 D3.js 类型不匹配问题
   - 修正事件处理中的类型转换

4. **修复 API 相关组件**：
   - 为 API 响应对象添加正确的类型注解
   - 使用类型守卫安全访问属性

## 临时运行建议

如果需要立即运行项目，可以：
1. 继续使用 `npm run dev` 进行开发（开发模式会忽略这些类型错误）
2. 或者暂时修改 tsconfig.json，设置 `"noEmitOnError": false` 来允许构建

## 长期维护建议

1. 建立严格的类型定义规范
2. 定期更新依赖包和对应的类型定义
3. 实施代码审查流程确保类型安全