"""
医学证据处理工作流的提示词模板
包含翻译、图片描述、排版融合、证据提取、仲裁评分和反馈微调等步骤的提示词
"""
from typing import List, Dict, Any
import json


def get_translation_prompt(markdown_content: str) -> str:
    """
    生成翻译 Markdown 为英文的提示词
    
    Args:
        markdown_content: 待翻译的 Markdown 内容
    
    Returns:
        格式化的提示词
    """
    return f"""请将以下医学 Markdown 内容翻译为英文，保留所有医学术语的准确性和格式：

{markdown_content}

仅返回翻译后的 Markdown 内容，不需要额外说明。"""


def get_image_description_prompt(image_index: int) -> str:
    """
    生成图片描述的提示词
    
    Args:
        image_index: 图片索引（从1开始）
    
    Returns:
        格式化的提示词
    """
    return f"""请详细描述这张医学/临床图片的内容。注意：
1. 识别图片中的关键元素（图表、数据、解剖结构等）
2. 用英文输出描述
3. 描述应该简洁但全面

输出格式：
[Image {image_index} Description]
<描述内容>"""


def get_layout_fusion_prompt(translated_md: str, image_descriptions: List[str]) -> str:
    """
    生成排版融合的提示词
    
    Args:
        translated_md: 翻译后的 Markdown 内容
        image_descriptions: 图片描述列表
    
    Returns:
        格式化的提示词
    """
    image_section = "\n".join([
        f"### Image {i+1} Description\n{desc}"
        for i, desc in enumerate(image_descriptions)
    ])
    
    return f"""请将以下内容融合为一份格式清晰、结构完整的医学文档：

## Translated Medical Document
{translated_md}

## Image Descriptions
{image_section}

请求：
1. 整合所有内容为单一、连贯的 Markdown 文档
2. 在适当位置引用图片描述
3. 保持医学术语的准确性
4. 使用清晰的章节组织

返回整合后的 Markdown（保留所有结构标记）"""


def get_ps3_evidence_extraction_prompt(middleware_md: str, knowledge_context: str = "") -> str:
    """
    生成 PS3 证据提取的提示词
    
    Args:
        middleware_md: 中间处理后的 Markdown 文档
        knowledge_context: 可选的知识库检索结果上下文
    
    Returns:
        格式化的提示词
    """
    # 如果有知识库上下文，添加到提示词中
    knowledge_section = ""
    if knowledge_context:
        knowledge_section = f"""
## REFERENCE KNOWLEDGE BASE DOCUMENTS
The following documents from the knowledge base may provide relevant guidance for PS3/BS3 evaluation:

{knowledge_context}

**Use these references to support your evaluation, especially for interpretation of criteria and thresholds.**

---
"""
    
    return f"""You are a clinical genomics expert specialized in ACMG PS3 (Functional Evidence) classification.
Evaluate the medical document following the PS3 SVI four-step decision framework below.
{knowledge_section}
## PS3 EVALUATION FRAMEWORK (四步法评估流程)

### STEP ① 明确疾病的致病机制
**Objective**: Determine if the pathogenic mechanism of the disease is clearly described.

**Assessment Criteria**:
- Is the molecular/cellular pathogenic mechanism clearly explained?
- Is the biological pathway or functional impact well-defined?

**Decision**:
- ✓ CLEAR (明确) → Proceed to Step ②
- ⚠ PARTIAL (部分明确) → Proceed with caution, note limitations
- ✗ UNCLEAR (不明确) → **STOP: Do NOT use PS3/BS3**

---

### STEP ② 评估功能实验方法的适用性
**Objective**: Evaluate whether the functional assay type is suitable for the disease mechanism.

**Assessment Criteria**:
- Does the experimental model match the pathogenic mechanism identified in Step ①?
- Is the assay type commonly accepted for this disease type?

**Decision**:
- ✓ YES (符合) → Proceed to Step ③
- ✗ NO (不符合) → **STOP: Do NOT use PS3/BS3**

---

### STEP ③ 评估具体案例中功能实验的有效性
**Objective**: Validate experimental quality through multiple checkpoints.

**Checkpoint 3A - Basic Controls & Replicates**:
- ✓ Are BOTH types of controls present?
  - Normal/Negative/Wild-type control
  - Abnormal/Positive/Non-functional control
- ✓ Are multiple replicates used (biological or technical)?

**Decision 3A**:
- ✗ NO → **STOP: Do NOT use PS3/BS3**
- ✓ YES → **Maximum: PS3_supporting / BS3_supporting**, proceed to 3B

**Checkpoint 3B - Method Reliability (Alternative Path)**:
If controls/replicates are not documented, check:
- Is the method historically widely accepted?
- Has it been previously validated?
- Is a certified kit with clear parameters used?

**Decision 3B**:
- ✗ NO → **STOP: Do NOT use PS3/BS3**
- ✓ YES → **Maximum: PS3_supporting / BS3_supporting**, proceed to 3C

**Checkpoint 3C - Positive Control Variants**:
- Are known pathogenic variants (P/LP) or benign variants (B/LB) used as positive controls?

**Decision 3C**:
- ✗ NO → Proceed to Step ④
- ✓ YES → **Maximum: PS3_supporting / BS3_supporting**, proceed to Step ④

---

### STEP ④ 将证据应用于特定变异的解读
**Objective**: Determine final evidence strength based on statistical analysis or control variant count.

**Path A - OddsPath Calculation (Preferred)**:
Can you calculate OddsPath from the reported statistics?

**If YES**:
1. Extract P1 (probability for wild-type/normal) and P2 (probability for variant)
2. Call tool: `OddsPath_Calculator(P1, P2)`
3. Call tool: `determine_evidence_strength_from_oddspath(oddspath)`
4. Verify the mapping using this table:

| OddsPath Range | Evidence Strength |
|----------------|-------------------|
| < 0.053        | BS3              |
| 0.053 - 0.23   | BS3_moderate     |
| 0.23 - 0.48    | BS3_supporting   |
| 0.48 - 2.1     | Inconclusive (不明确) |
| 2.1 - 4.3      | PS3_supporting   |
| 4.3 - 18.7     | PS3_moderate     |
| 18.7 - 350     | PS3              |
| > 350          | PS3_very_strong  |

**If NO** → Proceed to Path B

**Path B - Control Variant Count**:
Count the total number of control variants (benign + pathogenic) used:
- Call tool: `determine_max_evidence_from_controls(control_variants_count)`

**Decision**:
- ≤ 10 variants → **Maximum: PS3_supporting / BS3_supporting**
- ≥ 11 variants → **Maximum: PS3_moderate / BS3_moderate**

---

## MEDICAL DOCUMENT TO EVALUATE
{middleware_md}

---

## INSTRUCTIONS
1. **Follow the decision tree strictly** - each step's outcome determines whether to proceed
2. **Use the provided tools** when calculating OddsPath or determining evidence strength
3. **Document your reasoning** at each step
4. **Return structured JSON output** with detailed assessments

## OUTPUT FORMAT (valid JSON only)
{{{{
  "ps3_step_1": {{{{
    "disease_mechanism_clarity": "clear|partial|unclear",
    "can_proceed": true|false,
    "explanation": "Detailed explanation of the pathogenic mechanism found in document",
    "score": 0-25
  }}}},
  "ps3_step_2": {{{{
    "assay_suitable": "yes|no",
    "can_proceed": true|false,
    "explanation": "Assessment of whether the functional assay matches the mechanism",
    "score": 0-20
  }}}},
  "ps3_step_3": {{{{
    "checkpoint_3a": {{{{
      "basic_controls_present": true|false,
      "replicates_used": true|false,
      "controls_detail": "Description of controls found"
    }}}},
    "checkpoint_3b": {{{{
      "method_validated": true|false,
      "method_detail": "Description of method reliability"
    }}}},
    "checkpoint_3c": {{{{
      "positive_controls_used": true|false,
      "control_variants_detail": "Description of P/LP or B/LB variants used"
    }}}},
    "max_evidence_level": "none|supporting|moderate",
    "can_proceed": true|false,
    "score": 0-30
  }}}},
  "ps3_step_4": {{{{
    "path": "oddspath|control_count|none",
    "oddspath_data": {{{{
      "computable": true|false,
      "P1": null|float,
      "P2": null|float,
      "oddspath": null|float,
      "evidence_strength": "BS3|BS3_moderate|BS3_supporting|inconclusive|PS3_supporting|PS3_moderate|PS3|PS3_very_strong"
    }}}},
    "control_count_data": {{{{
      "total_variants": null|int,
      "pathogenic_count": null|int,
      "benign_count": null|int,
      "max_evidence_level": "supporting|moderate"
    }}}},
    "final_evidence_strength": "none|BS3|BS3_moderate|BS3_supporting|PS3_supporting|PS3_moderate|PS3|PS3_very_strong",
    "score": 0-25
  }}}},
  "overall_assessment": {{{{
    "total_score": 0-100,
    "final_recommendation": "approved|needs_refinement|rejected",
    "key_strengths": ["strength 1", "strength 2"],
    "key_weaknesses": ["weakness 1", "weakness 2"],
    "improvement_suggestions": ["suggestion 1", "suggestion 2"]
  }}}}
}}}}

**Return only valid JSON. No additional text.**"""


def get_arbitration_prompt(
    middleware_md: str,
    ps3_evidence: Dict[str, Any],
    calculated_score: float,
    final_recommendation: str
) -> str:
    """
    生成仲裁评分的提示词
    
    Args:
        middleware_md: 中间处理后的 Markdown 文档
        ps3_evidence: PS3 证据评估结果
        calculated_score: 计算得到的分数
        final_recommendation: 初步建议
    
    Returns:
        格式化的提示词
    """
    return f"""作为医学证据仲裁专家，请评估以下 PS3 功能证据的质量和完整性：

## 中间文档
{middleware_md}

## 提取的 PS3 证据评估
{json.dumps(ps3_evidence, ensure_ascii=False, indent=2)}

## 当前评估状态
- 计算得分: {calculated_score}/100
- 初步建议: {final_recommendation}

请作为独立仲裁者，评估以下方面：
1. **四步法执行完整性**: 是否严格按照 PS3 四步法进行评估？
2. **证据强度合理性**: 最终确定的证据强度是否合理？
3. **实验质量评估**: 对照组、重复实验、方法可靠性评估是否充分？
4. **OddsPath 计算**: 如果涉及 OddsPath，计算和映射是否正确？

请返回以下格式的评价：
{{{{
    "arbitration_score": <0-100的最终评分>,
    "agreement_with_initial": true|false,
    "score_adjustment": <正数表示提高分数，负数表示降低分数>,
    "feedback": "详细的改进建议",
    "strengths": ["优点1", "优点2"],
    "weaknesses": ["缺点1", "缺点2"],
    "critical_issues": ["需要立即解决的问题"],
    "final_decision": "approved|needs_refinement|reject"
}}}}

仅返回 JSON，不需要额外说明。"""


def get_feedback_refinement_prompt(
    middleware_md: str,
    arbitration_feedback: str,
    arbitration_score: float,
    weaknesses: List[str],
    improvements: List[str]
) -> str:
    """
    生成反馈微调的提示词
    
    Args:
        middleware_md: 当前的 Markdown 文档
        arbitration_feedback: 仲裁反馈
        arbitration_score: 仲裁评分
        weaknesses: 关键弱点列表
        improvements: 改进建议列表
    
    Returns:
        格式化的提示词
    """
    weaknesses_str = ', '.join(weaknesses) if weaknesses else '未指明'
    improvements_str = '\n'.join(f'- {sugg}' for sugg in improvements) if improvements else '请根据仲裁反馈进行改进'
    
    return f"""基于 PS3 四步法评审反馈，改进医学文档以提高证据质量：

## 当前文档
{middleware_md}

## 仲裁反馈
{arbitration_feedback}

## 主要问题
- 仲裁得分: {arbitration_score}/100
- 关键弱点: {weaknesses_str}

## 具体改进建议
{improvements_str}

## 改进要点
根据 PS3 四步法，重点改进以下方面：
1. **致病机制清晰度**: 确保疾病的分子/细胞致病机制有清晰描述
2. **实验方法适用性**: 确认功能实验方法与致病机制相匹配
3. **实验有效性**: 补充对照组、重复实验、方法可靠性等信息
4. **统计分析**: 如可能，补充 OddsPath 计算所需的统计数据（P1, P2值）

请根据上述反馈改进文档，返回改进后的完整 Markdown。
**只返回改进后的文档内容，不要添加额外说明。**"""


# ==================== PS3 评分标准常量 ====================

ODDSPATH_THRESHOLDS = {
    "BS3": 0.053,
    "BS3_moderate": 0.23,
    "BS3_supporting": 0.48,
    "inconclusive_upper": 2.1,
    "PS3_supporting": 4.3,
    "PS3_moderate": 18.7,
    "PS3": 350,
}

CONTROL_VARIANTS_THRESHOLDS = {
    "max_supporting": 10,  # ≤10个对照变异，最高 supporting
    "max_moderate": 11,    # ≥11个对照变异，最高 moderate
}

ARBITRATION_SCORE_THRESHOLD = 85  # 仲裁评分及格线
