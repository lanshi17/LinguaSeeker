"""
================================================================================
5阶段结构化PDF处理流程 - 完整实现指南
================================================================================

本文档定义了五阶段结构化处理PDF文献的完整流程，确保各阶段目标清晰、
依赖明确、验收可追踪，并完整保留原始变量占位符。

================================================================================
架构概览
================================================================================

┌─────────────────────┐
│ 阶段一: MinerU提取   │  输入：PDF
│ 原文→HTML(无翻译)    │  输出：{{original_structured_html}}
│                     │         {{detected_language}}
│                     │         {{bbox_metadata}}
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 阶段二: 翻译LLM      │  输入：{{original_structured_html}}
│ HTML→英文(无结构变)  │  输出：{{translated_english_html}}
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 阶段三: RAG+PS3      │  输入：{{translated_english_html}}
│ 证据提取+OddsPath    │         {{bbox_metadata}}
│                     │  输出：{{ps3_evidence_result}}
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 阶段四: 仲裁评审     │  输入：{{ps3_evidence_result}}
│ 质量评分+迭代(≤3)    │  输出：{{arbiter_score}}
│                     │         {{iterations_performed}}
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 阶段五: 结构化+高亮  │  输入：所有前期输出
│ JSON+高亮HTML       │  输出：{{final_evidence_json}}
│                     │         {{final_annotated_doc}}
│                     │         {{dual_language_view}}
└─────────────────────┘

================================================================================
分阶段详细说明
================================================================================

## 阶段一：MinerU HTML提取（Stage1MinerUHTMLExtractionStep）

**验收标准**：
✓ 所有文本块均含准确 data-bbox 坐标属性（像素单位）
✓ 表格保留HTML table结构，图表区域含 <img> 及标题
✓ 后续阶段可直接通过 querySelectorAll('[data-bbox]') 定位内容
✓ 文档可读、排版合理，逻辑顺序与原文一致
✓ 所有图表均有标题文本和对应截图
✓ JSON元数据完整覆盖全文，无大段缺失、乱码或顺序错乱
✓ Bbox坐标为像素单位，整体字符级精度 ≥99.3%
✓ 语言变量 {{detected_language}} 已正确生成
✓ 超长文档（>30页）启用分段处理且术语一致
✓ 所有输出文件已本地持久化，路径可被后续阶段直接引用
✓ MinerU SDK 仅执行PDF→HTML转换，未执行任何翻译操作，无英文HTML输出

**关键变量**：
- {{original_structured_html}}: str  # 原文结构化HTML的文件路径
- {{detected_language}}: str          # 检测到的源语言（中文、英文等）
- {{bbox_metadata}}: List[Dict]       # bbox元数据列表
  格式：[{"page_num": int, "bbox": [x0,y0,x1,y1], "text": str, "region_type": str}]
- {{bbox_metadata_path}}: str         # JSON元数据文件路径

**实现细节**：
class Stage1MinerUHTMLExtractionStep(IPipelineStep):
    - validate_prerequisites(): 检查PDF路径和输出目录
    - execute(): 调用MinerU API (enable_translation=False)
    - _load_and_validate_bbox_metadata(): 加载并验证bbox数据
    - _validate_html_structure(): 检查HTML包含必需的bbox属性和元素

---

## 阶段二：HTML翻译为英文（Stage2HTMLTranslationStep）

**验收标准**：
✓ {{translated_english_html}} 与 {{original_structured_html}} DOM结构完全一致
✓ 所有 data-bbox 属性保留且未被修改
✓ 仅文本内容被翻译，无额外标签或结构变更
✓ 翻译后文档可读、术语准确，符合学术语境
✓ 文件已本地持久化，路径可被阶段三直接引用

**关键变量**：
- {{translated_english_html}}: str  # 英文翻译HTML的文件路径

**实现细节**：
class Stage2HTMLTranslationStep(IPipelineStep):
    - validate_prerequisites(): 检查原文HTML存在且有效
    - execute(): 
      1. 提取HTML中的所有文本块
      2. 调用Qwen-MT-Plus翻译（支持8K token限制的分段翻译）
      3. 重构HTML，仅替换文本节点
    - _extract_text_blocks(): 从HTML提取纯文本
    - _translate_text_blocks(): 批量翻译（尊重token限制）
    - _reconstruct_html(): 重新组装HTML（保留结构）
    - _validate_dom_equivalence(): 验证DOM结构等价性

**Qwen-MT-Plus配置**：
- API: qwen-mt-plus (OpenAI兼容)
- Token限制: 8,192
- 策略: 按语义边界分段翻译
- 保留: <mark>, data-bbox, 元素顺序

---

## 阶段三：RAG检索与PS3证据提取（Stage3RAGAndPS3ExtractionStep）

**验收标准**：
✓ 所有输出字段必须存在且类型正确
✓ 若标注为 PS3/BS3 及其子类，必须提供有效的 P1/P2 坐标或明确说明"not reported"
✓ OddsPath 计算仅在 P1 和 P2 均可量化时执行
✓ 证据等级必须严格匹配 OddsPath 数值区间或支持性条件
✓ reasoning_summary 需引用原文位置（页码 + bbox）或关键词上下文
✓ RAG检索必须优先使用向量知识库，仅在未命中时回退至静态PDF实时向量化

**关键变量**：
- {{ps3_evidence_result}}: Dict  # 完整证据JSON

**输出JSON格式**：
{
  "ps3_evidence_level": "PS3 | PS3_moderate | PS3_supporting | BS3 | BS3_moderate | BS3_supporting | none",
  "odds_path_value": float or null,
  "p1_source": {"page": int, "bbox": [x0,y0,x1,y1]} or "not reported",
  "p2_source": {"page": int, "bbox": [x0,y0,x1,y1]} or "not reported",
  "reasoning_summary": "明确说明判断依据"
}

**OddsPath映射表**：
| OddsPath范围      | 证据强度           |
|-------------------|-------------------|
| < 0.017           | BS3               |
| 0.017 – 0.05      | BS3_moderate      |
| 0.05 – 0.33       | BS3_supporting    |
| 0.33 – 3.0        | —（无意义）       |
| 3.0 – 20          | PS3_supporting    |
| 20 – 60           | PS3_moderate      |
| ≥ 60              | PS3               |

**实现细节**：
class Stage3RAGAndPS3ExtractionStep(IPipelineStep):
    - execute(): 
      1. 检索PS3指南 (_retrieve_ps3_guidance)
      2. 定位P1/P2数据及坐标 (_locate_p1_data, _locate_p2_data)
      3. 详细评估PS3标准①→④ (_evaluate_ps3_criteria)
      4. 计算OddsPath (_calculate_odds_path)
      5. 确定证据强度等级 (_determine_evidence_level)
    - _retrieve_ps3_guidance(): RAG检索 → 向量DB（阈值0.65） → 回退实时向量化
    - _locate_p1_data(): 识别致病变异比例，返回页码+bbox
    - _locate_p2_data(): 识别异常组中致病变异比例，返回页码+bbox
    - _secondary_p1p2_search(): 关键词搜索（control, wild-type等）
    - _evaluate_ps3_criteria(): 评估4个维度
      ① 致病机制是否明确？
      ② 功能实验方法是否适用？
      ③ 具体案例的实验有效性？
         - 对照设置 (positive/negative/wildtype)
         - 重复数 (≥3)
         - 方法可靠性 (已验证/试剂盒)
         - 已知对照变异使用
      ④ 特定变异解读
         - OddsPath可计算？
         - 统计数据充分？

---

## 阶段四：仲裁评审与迭代优化（Stage4ArbiterReviewStep）

**验收标准**：
✓ {{arbiter_score}} ≥ 80 或已达最大迭代次数
✓ 每次迭代均有明确修改依据
✓ 溯源信息完整性与评分机制合规性是评分关键维度

**关键变量**：
- {{arbiter_score}}: int (0-100)          # 质量评分
- {{arbiter_feedback}}: str               # 评审反馈
- {{iterations_performed}}: int           # 实际迭代次数

**评分标准（总分100）**：
1. 致病机制清晰度（0-20分）
   - 明确 → 20分
   - 不明确 → 0分

2. 实验方法适用性（0-20分）
   - 适用 + 可靠 → 20分
   - 适用但不可靠 → 10分
   - 不适用 → 0分

3. 对照和重复设计（0-20分）
   - 对照充分 + ≥3重复 → 20分
   - 对照不足或重复< 3 → 5-15分
   - 无对照无重复 → 0分

4. 溯源信息完整性（0-20分）
   - P1和P2坐标完整 → 20分
   - 仅有P1或P2 → 10分
   - 无坐标 → 0分

5. 推理完整性（0-20分）
   - 包含所有关键维度 → 20分
   - 缺少部分维度 → 5-15分
   - 空白或不充分 → 0分

**迭代策略**：
- 最多3轮迭代
- 评分 ≥ 80 → 接受
- 评分 < 80 → 反馈给主力LLM修正
- 3轮后仍不达标 → 标记"证据不足"，输出当前最优结果

---

## 阶段五：结果结构化与文档高亮（Stage5ResultStructuringAndHighlightingStep）

**验收标准**：
✓ JSON 字段完整、类型正确
✓ 高亮内容与证据提取结果严格对应
✓ 高亮位置由 bbox 元数据驱动，确保空间准确性
✓ 所有变量占位符 {{…}} 均保留未替换
✓ 最终呈现形式为 HTML 页面，左侧为原文，右侧为对照英文翻译

**关键变量**：
- {{final_evidence_json}}: Dict         # 完整最终结果JSON
- {{final_annotated_doc}}: str          # 高亮后的英文HTML路径
- {{dual_language_view}}: str           # 双语对照HTML路径

**最终JSON格式**：
{
  "detected_language": "{{detected_language}}",
  "odds_path": float or null,
  "evidence_strength": "PS3 | PS3_moderate | ...",
  "arbiter_score": int,
  "ps3_criteria_met": bool,
  "extracted_experimental_details": str,
  "p1_source_location": str,
  "p2_source_location": str,
  "control_variants_count": int,
  "odds_path_computable": bool,
  "reason_if_not_applicable": str,
  "variable_placeholders": {
    "original_structured_html": "{{original_structured_html}}",
    "translated_english_html": "{{translated_english_html}}",
    ...
  }
}

**双语对照HTML**：
- 左列：原文（含语言）
- 右列：英文翻译（含高亮）
- 同步滚动
- 橙色高亮标注证据区域

**实现细节**：
class Stage5ResultStructuringAndHighlightingStep(IPipelineStep):
    - execute():
      1. 生成最终结构化JSON (_generate_final_json)
      2. 识别高亮位置 (_identify_highlight_locations)
      3. 生成高亮HTML (_generate_highlighted_html)
      4. 生成双语对照视图 (_generate_dual_language_view)
      5. 持久化所有输出
    - _generate_final_json(): 合并所有输出，保留{{占位符}}
    - _identify_highlight_locations(): 从证据中提取关键短语，映射bbox
    - _generate_highlighted_html(): 注入<mark>标签（不改变结构）
    - _generate_dual_language_view(): 生成完整HTML页面（左原文，右英文译本）

================================================================================
实现清单
================================================================================

已实现的文件：
✓ src/application/services/stage1_mineru_html_extraction.py
✓ src/application/services/stage2_html_translation.py
✓ src/application/services/stage3_rag_and_ps3_extraction.py
✓ src/application/services/stage4_arbiter_review.py
✓ src/application/services/stage5_result_structuring_and_highlighting.py
✓ src/application/services/complete_five_stages_pipeline.py

使用说明：

1. 导入CompleteFiveStagesPipelineOrchestrator
2. 初始化：orchestrator = CompleteFiveStagesPipelineOrchestrator(
     pdf_repository=repo,
     rag_repository=rag_repo,
     mt_llm_client=mt_client,
     arbiter_llm_client=arbiter_client
   )
3. 处理PDF：response = orchestrator.process_pdf(request)
4. 检查结果：response.results 包含所有{{占位符}}变量

================================================================================
测试和验证
================================================================================

需要进行的测试：
1. Stage-1: 验证bbox准确性、语言检测、图表提取
2. Stage-2: 验证DOM结构等价性、bbox保留、翻译质量
3. Stage-3: 验证P1/P2定位、OddsPath计算、PS3评分
4. Stage-4: 验证评分机制、迭代流程、反馈质量
5. Stage-5: 验证JSON完整性、高亮对应性、HTML可读性

关键测试用例：
- 中文论文 → 英文翻译 → PS3评分
- 长文档（>30页）处理
- 缺少P1/P2数据的处理
- 多轮迭代的收敛性

================================================================================
依赖项配置
================================================================================

.env.development 中的必需配置：

# MinerU配置
MINERU_MODE="api"
MINERU_API_URL="https://mineru.net/api/v4/extract/task"
MINERU_API_TOKEN="your_token"

# 翻译LLM (Qwen-MT-Plus)
MT_LLM_API_KEY="sk-..."
MT_LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
MT_LLM_MODEL="qwen-mt-plus"

# 仲裁LLM (Claude)
CLAUDE_API_KEY="sk-..."
ANTHROPIC_BASE_URL="https://yunwu.ai/v1"

# 向量库 (Qdrant)
QDRANT_HOST="https://..."
QDRANT_API_KEY="..."
QDRANT_COLLECTION_NAME="acmg_history"

================================================================================
"""

print(__doc__)
