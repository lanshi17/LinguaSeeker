# 完整改进实现路线图

## 已完成 ✅ (约1120行代码)

### P0: Arbiter评分模型重设
- [x] 创建`ArbiterFeedback`和`DimensionScore`值对象
- [x] Arbiter接口改为返回`ArbiterFeedback`而非`float`
- [x] 实现PS3四步详细评分提示词（每步0-100分）
- [x] 修改orchestrator支持反馈驱动的迭代循环
- [x] 更新Evidence提取器接收反馈参数

**关键输出**:
```json
{
  "overall_score": 0-100,
  "dimensions": [
    {"name": "disease_mechanism", "score": 0-25, "status": "pass|fail|partial"},
    {"name": "method_suitability", "score": 0-20, "status": "pass|fail|na"},
    {"name": "experimental_validity", "score": 0-50, "status": "pass|fail|partial"},
    {"name": "odds_path_validity", "score": 0-20, "status": "pass|fail"}
  ],
  "key_issues": [...],
  "recommendations": [...],
  "should_iterate": boolean
}
```

### P1: PS3四步详细评估强化
- [x] 创建`PS3EvaluationFramework`模块
- [x] 实现4个Step Result类（疾病机制→方法→实验→应用）
- [x] 强化evidence提取提示词包含所有维度检查
- [x] 强制源位置引用

**关键输出**:
```python
- Step 1: 疾病机制是否清晰（pass/fail/partial）
- Step 2: 方法是否适用于机制（pass/fail/na）
- Step 3: 实验有效性4个子组件
  - 3a) 对照组设置（pass/fail）
  - 3b) 重复性（pass/fail）
  - 3c) 方法可靠性（pass/fail/na）
  - 3d) 已知对照变异（pass/fail）
- Step 4: OddsPath有效性和应用（pass/fail）
```

### P1.1: P1/P2数据二次检索
- [x] 创建`P1P2SearchEngine`类
- [x] 实现关键词搜索（控制组、野生型、良性/致病变异、统计学指标）
- [x] 返回匹配位置的bbox和页码
- [x] 整合到orchestrator中

**关键输出**:
```python
p1_candidates = [
  {"matched_text": "...", "context": "...", "bbox": [...], "page": 5}
]
p2_candidates = [...]
```

---

## 待完成 ⏳

### P2: 图表自动检测与截图 (✏️ 框架已建)

**新增文件**: `src/domain/services/figure_table_detector.py`

#### 实现步骤:

1. **集成到PDF仓库**
   ```python
   # src/infrastructure/repositories/pdf_repository_impl.py
   def extract_figures_and_tables(self, pdf_path: str, bbox_fragments: List[Dict]):
       detector = FigureTableDetector()
       figures, tables = detector.detect_figure_table_locations(bbox_fragments)
       # 保存图表元数据和截图
       return figures, tables
   ```

2. **保存图表图像**
   - 基于bbox坐标截取PDF页面
   - 保存为PNG/JPG文件
   - 关联图表标题文本

3. **集成到orchestrator**
   ```python
   # Phase 1 中添加
   figures, tables = self.pdf_repo.extract_figures_and_tables(...)
   state.figures_metadata = figures
   state.tables_metadata = tables
   ```

4. **最终输出**
   ```json
   {
     "figures": [
       {
         "title": "Figure 1: LDL internalization pathway",
         "caption": "...",
         "image_path": "outputs/fig_1.png",
         "page": 3,
         "bbox": [100, 200, 500, 400]
       }
     ],
     "tables": [...]
   }
   ```

---

### P3: HTML双语侧边栏升级 (✏️ 框架已建)

**新增文件**: `src/infrastructure/rendering/bilingual_html_generator.py`

#### 实现步骤:

1. **更新HTMLGenerator**
   ```python
   # src/infrastructure/rendering/html_generator.py
   from bilingual_html_generator import BilingualHTMLGenerator
   
   def generate_bilingual_report(
       self,
       original_markdown: str,
       english_markdown: str,
       evidence_summary: Dict
   ) -> str:
       generator = BilingualHTMLGenerator(original_language="ja")
       return generator.generate_bilingual_html(...)
   ```

2. **修改orchestrator输出**
   ```python
   # Phase 7 中替换
   bilingual_html = self.html_generator.generate_bilingual_report(
       original_md=japanese_md,
       english_md=english_md,
       evidence_summary=state.arbiter_feedback
   )
   ```

3. **支持的功能**
   - 左侧原文（日/中/俄/德/法/英）
   - 右侧英文翻译
   - 同步高亮标记
   - 下方/侧边证据总结面板
   - 响应式设计（桌面/平板/手机）

4. **最终输出**
   ```
   outputs/
   └── sample_pdf_report.html
       ├─ 左列：原日文文档（含<mark>高亮）
       ├─ 右列：英文翻译（含<mark>高亮）
       └─ 侧栏：PS3四步评分、OddsPath、数据源、控制变异数
   ```

---

## 文件清单

### 新增文件 (6个)
1. `src/domain/value_objects/arbiter_feedback.py` - 结构化反馈值对象
2. `src/domain/services/ps3_framework.py` - PS3四步评估框架
3. `src/domain/services/p1p2_search.py` - P1/P2关键词搜索
4. `src/domain/services/figure_table_detector.py` - 图表检测（P2框架）
5. `src/infrastructure/rendering/bilingual_html_generator.py` - 双语HTML生成（P3框架）
6. `IMPROVEMENTS_SUMMARY.md` - 改进总结文档

### 修改文件 (6个)
1. `src/domain/services/arbiter.py` - 接口改为返回ArbiterFeedback
2. `src/infrastructure/llm/arbiter_impl.py` - 实现PS3四步评分
3. `src/domain/services/evidence_extractor.py` - 接口添加feedback参数
4. `src/infrastructure/llm/evidence_extractor_impl.py` - 强化提示词
5. `src/application/services/pipeline_orchestrator.py` - 反馈循环 + P1/P2搜索
6. `src/domain/entities/pipeline_state.py` - 添加arbiter_feedback字段

### 其他改动 (2个)
1. `src/domain/value_objects/__init__.py` - 导出新值对象
2. `main.py` - 修复导入路径

---

## 测试计划

### 现阶段测试 (P0-P1.1完成后)
```bash
# 运行单一PDF完整流程
uv run python main.py inputs/sample.pdf --out-dir outputs/test_p0_p1

# 验证输出:
# ✓ arbiter_feedback.json - 含PS3四步评分
# ✓ evidence.json - 含p1/p2二次搜索候选位置
# ✓ 迭代日志 - 显示3轮反馈循环
```

### P2测试 (图表检测)
```bash
# 使用含多个figure/table的论文
uv run python main.py inputs/complex_paper.pdf --out-dir outputs/test_p2

# 验证输出:
# ✓ figures_metadata.json - 图表坐标和标题
# ✓ outputs/fig_1.png, fig_2.png, ... - 截取的图表图像
```

### P3测试 (双语HTML)
```bash
# 运行完整流程
uv run python main.py inputs/japanese_paper.pdf --out-dir outputs/test_p3

# 验证输出:
# ✓ report.html - 打开后显示左日文/右英文对照布局
# ✓ 侧边栏显示PS3四步评分
# ✓ 高亮标记同步出现在两列
```

---

## 预期改进效果

| 指标 | 改进前 | 改进后 |
|------|--------|--------|
| Arbiter评分精确性 | 0-100分（无结构） | PS3四步详细评分 |
| 反馈驱动改进 | ❌ 无 | ✅ 3轮迭代 |
| P1/P2数据覆盖 | ~60% | ~85% |
| 图表识别 | ❌ 无 | ✅ 自动检测 |
| 用户体验 | 单一文本输出 | 双语对照报告 |

---

## 后续优化 (Future)

1. **缓存KB embeddings** - 加速后续运行
2. **批量处理** - 支持多PDF并行处理
3. **API端点** - RESTful服务化
4. **数据库集成** - 持久化存储证据
5. **可视化仪表板** - 证据统计分析

---

**总代码行数**: ~1120行 (已完成) + ~400行框架 (P2/P3) = ~1520行
