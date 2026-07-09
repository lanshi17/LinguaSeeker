# Annotation Layer

> 文档段落划线标注层：把用户标注的文本偏移映射成可点击覆盖层，并提供创建、字段分配、编辑和删除入口。

## Quick Start

```typescript
import { AnnotationLayer } from "@/features/evidence-search/components/annotationLayer";

<div ref={contentRef} style={{ position: "relative" }}>
  <p>{paragraph.text}</p>
  <AnnotationLayer
    containerRef={contentRef}
    paragraphId={paragraph.id}
    track="original"
    annotations={annotations}
  />
</div>;
```

## Architecture

```
consumer paragraph container
        |
        v
AnnotationLayer
  |-- useAnnotationOverlays
  |     `-- geometry.ts: offsets -> DOM Range -> overlay rects
  |-- useAnnotationSelection
  |     `-- geometry.ts: DOM Selection -> flattened offsets
  |-- AnnotationOverlayRects
  |-- AnnotationSelectionToolbar
  `-- AnnotationEditor
```

数据流：

1. 调用方提供 `containerRef`、`paragraphId`、`track` 和当前 `UserAnnotation[]`。
2. `useAnnotationOverlays` 在渲染后读取容器内所有文本节点，把后端保存的 `start_offset` / `end_offset` 转为 `Range.getClientRects()`。
3. `AnnotationOverlayRects` 渲染绝对定位的半透明覆盖层，点击后打开编辑 Popover。
4. `useAnnotationSelection` 监听文档 `mouseup`，把用户选区转换为扁平文本偏移。
5. `AnnotationSelectionToolbar` 调用 `onCreateAnnotation` 或 `onAssignField`，成功后清除浏览器选区。

## Public API

### `AnnotationLayer`

| API | Signature | Description |
| --- | --- | --- |
| Component | `export function AnnotationLayer({...}: AnnotationLayerProps)` | 渲染文本标注覆盖层、创建工具条和编辑弹窗。 |
| Props | `export interface AnnotationLayerProps` | 稳定调用契约；通过 `components/annotationLayer.tsx` 兼容导出。 |
| Create payload | `export interface AnnotationCreatePayload` | 创建标注时提交 `paragraph_id`、`track`、偏移和颜色。 |
| Update payload | `export interface AnnotationUpdatePayload` | 更新颜色和备注。 |
| Operation | `export type AnnotationOperation = void \| Promise<void>` | 回调可同步或异步完成。 |

### Geometry Helpers

这些函数从内部模块导出，主要用于测试和精确维护坐标逻辑。

| Function | Signature | Description |
| --- | --- | --- |
| `collectTextNodeOffsets` | `collectTextNodeOffsets(container: HTMLElement): TextNodeOffset[]` | 按 DOM 顺序收集非空文本节点及其扁平起始偏移。 |
| `offsetToPoint` | `offsetToPoint(offsets: TextNodeOffset[], offset: number): { node: Text; localOffset: number } \| null` | 把扁平偏移转换为具体文本节点和节点内偏移。 |
| `findPointForNode` | `findPointForNode(offsets: TextNodeOffset[], node: Node, offset: number): number \| null` | 把 Selection 的 DOM 端点转换为扁平偏移。 |
| `selectionInContainer` | `selectionInContainer(container: HTMLElement): SelectionInfo \| null` | 读取当前浏览器选区并返回可保存的标注范围。 |
| `computeAnnotationOverlays` | `computeAnnotationOverlays(container: HTMLElement, annotations: UserAnnotation[]): OverlayRect[]` | 计算每个标注对应的一组覆盖矩形。 |

## Internal Design

### Coordinate Model

标注坐标不是 Markdown 源码偏移，也不是后端字段偏移，而是段落容器内所有 descendant text nodes 的 `textContent` 扁平偏移。这个模型允许证据 `<mark>`、Markdown 节点和普通文本共存，因为标注层只渲染覆盖 div，不改写正文 DOM。

### Overlay Computation

`computeAnnotationOverlays` 对每条标注执行：

1. 调用 `offsetToPoint` 找到起止文本节点。
2. 创建 DOM `Range` 并设置起止点。
3. 读取 `range.getClientRects()`，过滤宽高小于 1px 的无效矩形。
4. 将 viewport 坐标转换为容器内坐标：`rect - containerRect + scrollOffset`。

### Selection Handling

`useAnnotationSelection` 只在存在创建或字段分配回调时启用。它会忽略三类点击来源：

- 当前选择工具条内部；
- Ant Design `Select` 的 portal 下拉层；
- 带 `data-reviewable` 的审阅字段标记。

### Error Handling

组件级回调错误会被吞掉并恢复 loading 状态，避免工具条或编辑器卡住。用户可见错误提示应由上层 mutation/service 负责处理。

## Usage Patterns

### Creating User Annotations

```typescript
<AnnotationLayer
  containerRef={contentRef}
  paragraphId={paragraph.id}
  track={track}
  annotations={annotations}
  onCreateAnnotation={(payload) => createAnnotation(sourceDocumentId, payload)}
/>;
```

### Recomputing After DOM Shape Changes

```typescript
<AnnotationLayer
  containerRef={contentRef}
  paragraphId={paragraphId}
  track={track}
  annotations={annotations}
  recomputeDeps={[markdown, highlights, alignmentHighlights]}
/>;
```

### Assigning Selected Text To A Field

```typescript
<AnnotationLayer
  containerRef={contentRef}
  paragraphId={paragraph.id}
  track="translated"
  annotations={annotations}
  fieldTypes={fieldTypes}
  onAssignField={(selectedText, fieldId) => patchEvidenceField(fieldId, selectedText)}
/>;
```

## Extension Guide

- 新增标注动作时，优先扩展 `AnnotationSelectionToolbar`，不要把工具条交互塞回 `AnnotationLayer`。
- 修改坐标算法时，同步更新 `annotationLayerGeometry.test.tsx`，尤其是跨文本节点选区和多行覆盖层。
- 如果正文 DOM 新增会改变 `textContent` 的包装层，把对应数据放进 `recomputeDeps`。
- 如果需要新的后端字段，先扩展 `types/annotations.ts` 或调用方 payload，再把 `contracts.ts` 作为组件边界同步更新。

## Performance Notes

- 覆盖层计算是 `annotations * textNodes` 级别，适合段落级容器；不要把整篇长文共用一个超大容器。
- `ResizeObserver` 会在容器尺寸变化时重算覆盖层；无 `ResizeObserver` 的测试环境会跳过监听，但仍执行首次计算。
- `Range.getClientRects()` 是布局读取，避免在高频输入事件里触发；当前只在注释数据、依赖数据或容器尺寸变化时触发。

## Dependencies

| Dependency | Version | Purpose |
| --- | --- | --- |
| `react` | `^18.3.0` | Hooks、refs 和 JSX 组件。 |
| `antd` | `^6.4.3` | `Popover`、`Select`、`Tooltip`、`Button`、`Input.TextArea`。 |
| `@ant-design/icons` | `6.2.5` in `bun.lock` | `DeleteOutlined` 图标。 |
| `vitest` | `^4.1.8` | 几何逻辑和调用方回归测试。 |

## Testing

```bash
cd frontend
bun run test tests/evidence-search/annotationLayerGeometry.test.tsx
bun run test tests/evidence-db/DocumentReaderAnnotations.test.tsx tests/evidence-search/BilingualCompareView.test.tsx
bun run type-check
```

当前覆盖：

- 文本节点扁平偏移收集；
- 跨文本节点 Selection 到标注偏移的映射；
- 覆盖矩形相对容器坐标计算；
- `DocumentReader` / `BilingualCompareView` 对兼容导出路径的调用。
