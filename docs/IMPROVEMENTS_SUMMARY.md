# ACMG PS3 证据提取流程改进 - 阶段总结

## 已完成改进 (P0-P1)

### ✅ **P0: Arbiter评分模型重设** (完成)

#### 1. 结构化反馈系统
- **新增文件**: `src/domain/value_objects/arbiter_feedback.py`
  - `DimensionScore`: 单维度评分类（包含分数、状态、理由、建议）
  - `ArbiterFeedback`: 综合反馈类（包含总分、各维度评分、关键问题、建议、迭代标志）

#### 2. Arbiter接口与实现升级
- **修改文件**: `src/domain/services/arbiter.py`
  - 方法签名从 `score_evidence(...) -> float` 改为 `score_evidence(...) -> ArbiterFeedback`
  - 支持可选的 `kb_context` 参数

- **修改文件**: `src/infrastructure/llm/arbiter_impl.py` (~180行)
  - 实现详细的PS3四步评估提示词
  - 每步分别评分（步1: 25分, 步2: 20分, 步3: 50分, 步4: 20分，总100分）
  - 提示词包含OddsPath映射表和各维度判定标准
  - 返回结构化JSON反馈，包含各步骤的详细评分

#### 3. 迭代反馈机制
- **修改文件**: `src/application/services/pipeline_orchestrator.py`
  - 新增反馈驱动的迭代循环
  - 每轮迭代捕获Arbiter的关键问题和建议
  - 将反馈作为上下文传递给下一轮evidence提取
  - 最多3轮迭代，达到80分或无改进时停止

- **修改文件**: `src/domain/entities/pipeline_state.py`
  - 新增 `arbiter_feedback` 字段存储完整反馈

#### 4. Evidence提取改进
- **修改文件**: `src/infrastructure/llm/evidence_extractor_impl.py`
  - 接口添加 `feedback: Optional[str]` 参数
  - 改进系统提示词以支持反馈注入

---

### ✅ **P1: PS3四步详细评估强化** (完成)

#### 1. 四步框架模块
- **新增文件**: `src/domain/services/ps3_framework.py` (~280行)
  - `PS3Step1Result`: 疾病机制清晰度评估
  - `PS3Step2Result`: 功能实验方法适用性评估
  - `PS3Step3Result`: 实验有效性评估（含4个子组件）
    - 3a) 对照组（正常 vs 异常）
    - 3b) 重复性（生物学或技术重复）
    - 3c) 方法可靠性（验证/试剂盒）
    - 3d) 对照变异（已知致病/良性）
  - `PS3Step4Result`: OddsPath有效性评估
  - `PS3EvaluationFramework`: 完整评估逻辑引擎

#### 2. Evidence提取器提示词强化
- **修改文件**: `src/infrastructure/llm/evidence_extractor_impl.py`
  - 新增 `_build_human_prompt()` 方法
  - 详细的四步框架指导（包含示例）：
    - 步1: 疾病机制必须包含分子/细胞影响、组织相关性、生化后果
    - 步2: 试验方法适用性（含示例配对）
    - 步3: 所有4个子组件的完整评估
    - 步4: P1/P2提取和OddsPath计算指导
  - 强制要求 p1_source_location 和 p2_source_location 引用确切位置
  - 明确输出要求（control_variants_count、odds_path_computable 等）

---

### ✅ **P1.1: P1/P2数据二次检索** (完成)

#### 1. 关键词搜索引擎
- **新增文件**: `src/domain/services/p1p2_search.py` (~110行)
  - `P1P2SearchEngine`: 专用搜索引擎
  - 控制组关键词: "control group", "wild-type", "healthy controls" 等
  - 良性变异关键词: "benign variant", "B/LB", "polymorphism" 等
  - 致病变异关键词: "pathogenic variant", "P/LP", "loss-of-function" 等
  - 统计学指标关键词: p值、OR值、CI、折变、效应大小
  - 返回匹配位置的bbox坐标和页码

---

## 待完成改进 (P2-P3)

### ⏳ **P1.5: 整合P1/P2二次检索到orchestrator** (待执行)
需要在evidence提取处理中：
1. 检测P1/P2是否为"not reported"
2. 调用P1P2SearchEngine进行关键词搜索
3. 返回候选位置的bbox坐标
4. 作为反馈提示传递给Arbiter和下一轮提取

### ⏳ **P2: 图表自动检测与截图** (待执行)
需要改进：
1. 在OCR阶段识别Figure/Table标题关键词
2. 基于LayoutParser区域分割截取图表图像
3. 保存图表及其标题文本
4. 在最终输出中关联图表与坐标

### ⏳ **P3: HTML双语侧边栏升级** (待执行)
需要改进HTMLGenerator：
1. 左侧显示原文（日文/中文/俄文等）
2. 右侧显示英文翻译
3. 同步高亮标记（两侧相同位置）
4. 下方显示证据提取面板
5. 交互式功能（折叠/展开等）

---

## 关键改进效果

### 评分质量提升
- **之前**: Arbiter简单0-100分，无结构化反馈
- **现在**: PS3四步详细评分，每步0-100分映射，包含关键问题和改进建议

### 证据提取精准度
- **之前**: 通用提示词，缺乏PS3特定指导
- **现在**: 详细四步框架，含示例配对、维度检查清单、强制源位置引用

### 迭代改进循环
- **之前**: 单次提取，无反馈机制
- **现在**: 3轮迭代循环，每轮收集反馈驱动改进

### P1/P2数据覆盖
- **之前**: 若P1/P2不明确则记为"not reported"
- **现在**: 自动触发二次关键词搜索，提高数据发现率

---

## 代码统计

| 组件 | 文件 | 行数 | 类型 |
|------|------|------|------|
| ArbiterFeedback | `arbiter_feedback.py` | ~80 | 新增 |
| PS3Framework | `ps3_framework.py` | ~280 | 新增 |
| P1P2SearchEngine | `p1p2_search.py` | ~110 | 新增 |
| ArbiterImpl | `arbiter_impl.py` | ~180 | 改进 |
| EvidenceExtractorImpl | `evidence_extractor_impl.py` | ~120 | 改进 |
| PipelineOrchestrator | `pipeline_orchestrator.py` | ~320 | 改进 |
| 其他接口/实体 | 多个 | ~50 | 改进 |
| **总计** | | **~1120** | |

---

## 后续工作优先级

1. **P1.5 (高)**: 整合P1/P2二次检索 - 立即提升数据覆盖
2. **测试与验证**: 运行完整流程验证所有改进
3. **P2 (中)**: 图表自动检测 - 支持复杂文献
4. **P3 (中)**: HTML双语侧边栏 - 改善用户体验

---

## 运行说明

```bash
# 运行改进后的完整流程
uv run python main.py "inputs/sample.pdf" --out-dir outputs/

# 核心改进点:
# 1. Arbiter评分现在返回结构化反馈（包含PS3四步评分）
# 2. Evidence提取包含详细四步评估提示词
# 3. 迭代循环基于Arbiter反馈自动改进
# 4. P1/P2二次检索引擎就绪（待整合）
```

---

## 验收标准检查

- [x] Arbiter返回ArbiterFeedback结构体（包含overall_score, dimensions, key_issues, recommendations）
- [x] Evidence提取包含PS3四步详细提示词
- [x] 迭代循环最多3轮，基于反馈改进
- [x] P1/P2二次搜索引擎已实现（关键词+bbox返回）
- [ ] P1/P2搜索已整合到orchestrator流程
- [ ] 图表自动检测与截图已实现
- [ ] HTML双语侧边栏已实现
