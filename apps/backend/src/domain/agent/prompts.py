"""
医学证据处理工作流的提示词模板
包含翻译、图片描述、排版融合、证据提取、仲裁评分和反馈微调等步骤的提示词
支持11个标准化证据字段的结构化提取
"""
from typing import List, Dict, Any
import json


# ==================== 标准化证据字段定义 ====================
EVIDENCE_FIELDS = [
    "Gene",
    "Transcript_ID",
    "Reference_Genome_Version",
    "Experiment_Data",
    "Disease_CHPO",
    "Disease_ICD10",
    "Species",
    "Phenotype",
    "Variant",
    "Negative_Positive_Control",
    "Pedigree_Information",
]

EVIDENCE_FIELD_RULES = """
### STRUCTURED EVIDENCE FIELD EXTRACTION RULES

You MUST extract the following 11 standardized fields from the document. For each field, provide confidence (0-100) and the exact quote from the document supporting the extraction.

**1. Gene**
- Extract: gene symbol (e.g., BRCA1, TP53, VWF), full name, NCBI Gene ID, Ensembl ID
- Look for: gene names mentioned in title, abstract, methods, results
- Confidence: 95+ if explicitly stated with standard nomenclature; 70-94 if inferred; <70 if ambiguous

**2. Transcript_ID**
- Extract: RefSeq transcript ID (NM_xxxxxx.x) or Ensembl transcript ID (ENST...)
- Look for: methods section, variant nomenclature context
- Confidence: 95+ if explicitly listed; 50 if only gene name given (infer canonical); 0 if completely absent

**3. Reference_Genome_Version**
- Extract: GRCh37/hg19, GRCh38/hg38, or other assembly versions
- Look for: methods section, variant coordinates, supplementary materials
- Confidence: 95+ if explicitly stated; 50 if inferred from coordinate format; 0 if absent

**4. Experiment_Data**
- Extract: assay type, method description, key findings, statistical data (p-values, CI, effect sizes), sample size, cell line, model organism
- Look for: methods & results sections, figures, tables
- Confidence: 95+ if comprehensive methods with statistics; 70-94 if partial; <70 if vague

**5. Disease_CHPO** (Chinese Human Phenotype Ontology)
- Extract: disease name, CHPO ID if available, OMIM ID, inheritance pattern (AD/AR/XL/XD)
- Look for: introduction, discussion, clinical data sections
- Confidence: 90+ if standard disease terminology used; 60 if only phenotype described

**6. Disease_ICD10**
- Extract: ICD-10 code, disease classification
- Look for: clinical context, diagnosis information
- Confidence: 90+ if ICD-10 code explicitly given; 60 if mappable from disease name; 0 if not determinable

**7. Species**
- Extract: species name, whether human sample
- Look for: methods section, sample description
- Confidence: 95+ if explicitly stated; 80 if inferred from context (e.g., patient samples = human)

**8. Phenotype**
- Extract: phenotype description, HPO IDs, severity (mild/moderate/severe), onset age
- Look for: clinical presentation, patient description, case reports
- Confidence: 90+ if detailed phenotype with HPO terms; 60 if general description only

**9. Variant**
- Extract: HGVS cDNA (c.), protein (p.), genomic (g.) nomenclature, chromosome, position, ref/alt alleles, variant type, rsID, ClinVar ID
- Look for: title, abstract, results, variant tables
- Confidence: 95+ if full HGVS with coordinates; 70-94 if partial; <70 if ambiguous

**10. Negative_Positive_Control**
- Extract: presence of negative/positive controls, descriptions, control variant list, total count
- Look for: methods section, experimental design, control experiments
- Confidence: 90+ if both controls present with details; 60 if only one type; <60 if absent/unclear

**11. Pedigree_Information**
- Extract: presence of pedigree data, family size, affected count, segregation data, inheritance pattern
- Look for: family studies, pedigree figures, segregation analysis
- Confidence: 90+ if detailed pedigree; 50 if family history mentioned briefly; 0 if absent
"""


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


def get_ps3_evidence_extraction_prompt(
    translated_md: str,
    image_descriptions: List[str],
    knowledge_context: str = "",
) -> str:
    """
    生成 PS3 证据提取的提示词
    
    Args:
        translated_md: 翻译后的 Markdown 文档
        image_descriptions: 图片描述列表
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
    
    image_section = "\n".join(
        [f"### Image {i + 1} Description\n{desc}" for i, desc in enumerate(image_descriptions)]
    )

    return f"""You are a clinical genomics expert specialized in ACMG PS3 (Functional Evidence) classification.
Evaluate the medical document following the PS3 SVI four-step decision framework below.
Additionally, extract all 11 standardized evidence fields from the document.
{knowledge_section}
{EVIDENCE_FIELD_RULES}

---

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
{translated_md}

## IMAGE DESCRIPTIONS
{image_section if image_section else "(none)"}

---

## INSTRUCTIONS
1. **Follow the decision tree strictly** - each step's outcome determines whether to proceed
2. **Use the provided tools** when calculating OddsPath or determining evidence strength
3. **Document your reasoning** at each step
4. **Extract all 11 standardized evidence fields** with confidence scores
5. **Return structured JSON output** with detailed assessments
6. **Strict JSON only**: use double quotes for keys/strings, no trailing commas, no extra text
7. **Evidence annotations**: every conclusion must cite evidence IDs; each evidence quote MUST be an exact substring from the medical document
8. **Confidence scoring**: For each extracted field, assign confidence 0-100; evidence with overall confidence >= 85 is considered valid

## OUTPUT FORMAT (valid JSON only)
{{{{
    "annotation_schema_version": "1.0",
    "source_documents": {{{{
        "en_md": {{{{ "path": "en_format.md" }}}},
        "image_descriptions": {{{{ "path": "image_descriptions.txt" }}}},
        "images": [{{{{
            "id": "fig1",
            "label": "Fig. 1",
            "path": "images/figure.jpg",
            "nearest_md_lines": {{{{
                "file": "en_format.md",
                "line_start": null,
                "line_end": null
            }}}}
        }}}}]
    }}}},
    "evidence_annotations": [{{{{
        "id": "E1",
        "type": "text|image",
        "purpose": "disease_mechanism|assay_setup|controls_replicates|assay_result",
        "locator": {{{{
            "file": "en_format.md",
            "char_start": null,
            "char_end": null,
            "line_start": null,
            "line_end": null
        }}}},
        "quote": "Exact substring from the document",
        "keywords": {{{{
            "raw": ["keyword1", "keyword2"],
            "normalized": ["keyword1", "keyword2"],
            "tex_wrapped": ["$n = 3$", "$44\\%$"]
        }}}},
        "image_ref": "fig1"
    }}}}],
  "ps3_step_1": {{{{
    "disease_mechanism_clarity": "clear|partial|unclear",
    "can_proceed": true|false,
    "explanation": "Detailed explanation of the pathogenic mechanism found in document",
        "evidence_refs": ["E1"],
    "score": 0-25
  }}}},
  "ps3_step_2": {{{{
    "assay_suitable": "yes|no",
    "can_proceed": true|false,
    "explanation": "Assessment of whether the functional assay matches the mechanism",
        "evidence_refs": ["E2"],
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
        "evidence_refs": ["E3", "E4"],
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
        "evidence_refs": ["E4"],
    "score": 0-25
  }}}},
  "extracted_fields": {{{{
    "gene": {{{{
      "symbol": "GENE_SYMBOL",
      "full_name": "Full gene name or null",
      "ncbi_gene_id": "NCBI ID or null",
      "ensembl_id": "Ensembl ID or null",
      "confidence": 0-100,
      "evidence_quote": "exact quote from document"
    }}}},
    "transcript_id": {{{{
      "transcript_id": "NM_xxxxxx.x or null",
      "source": "RefSeq|Ensembl|null",
      "confidence": 0-100,
      "evidence_quote": "exact quote or null"
    }}}},
    "reference_genome_version": {{{{
      "version": "GRCh37|GRCh38|hg19|hg38|null",
      "confidence": 0-100,
      "evidence_quote": "exact quote or null"
    }}}},
    "experiment_data": {{{{
      "assay_type": "type of functional assay",
      "method_description": "brief method description",
      "key_findings": ["finding 1", "finding 2"],
      "statistical_data": {{{{ "p_value": null, "effect_size": null, "confidence_interval": null }}}},
      "sample_size": "N or null",
      "cell_line": "cell line name or null",
      "model_organism": "organism or null",
      "confidence": 0-100,
      "evidence_quote": "exact quote"
    }}}},
    "disease_chpo": {{{{
      "disease_name": "disease name",
      "chpo_id": "CHPO ID or null",
      "omim_id": "OMIM ID or null",
      "inheritance_pattern": "AD|AR|XL|XD|null",
      "confidence": 0-100,
      "evidence_quote": "exact quote"
    }}}},
    "disease_icd10": {{{{
      "disease_name": "disease name",
      "icd10_code": "ICD-10 code or null",
      "confidence": 0-100,
      "evidence_quote": "exact quote or null"
    }}}},
    "species": {{{{
      "species_name": "Homo sapiens or other",
      "is_human": true|false,
      "confidence": 0-100,
      "evidence_quote": "exact quote"
    }}}},
    "phenotype": {{{{
      "phenotype_description": "description",
      "hpo_ids": ["HP:xxxxxxx"],
      "severity": "mild|moderate|severe|null",
      "onset_age": "age or null",
      "confidence": 0-100,
      "evidence_quote": "exact quote"
    }}}},
    "variant": {{{{
      "hgvs_c": "c.xxx or null",
      "hgvs_p": "p.xxx or null",
      "hgvs_g": "g.xxx or null",
      "chromosome": "chr or null",
      "position": null,
      "ref_allele": "ref or null",
      "alt_allele": "alt or null",
      "variant_type": "missense|nonsense|frameshift|splicing|other|null",
      "rs_id": "rsID or null",
      "clinvar_id": "ClinVar ID or null",
      "confidence": 0-100,
      "evidence_quote": "exact quote"
    }}}},
    "negative_positive_control": {{{{
      "has_negative_control": true|false,
      "has_positive_control": true|false,
      "negative_control_description": "description or null",
      "positive_control_description": "description or null",
      "control_variants": [{{{{ "variant": "name", "type": "pathogenic|benign" }}}}],
      "total_control_count": 0,
      "confidence": 0-100,
      "evidence_quote": "exact quote or null"
    }}}},
    "pedigree_information": {{{{
      "has_pedigree": true|false,
      "family_size": null,
      "affected_count": null,
      "segregation_data": "description or null",
      "inheritance_pattern": "AD|AR|XL|XD|null",
      "confidence": 0-100,
      "evidence_quote": "exact quote or null"
    }}}}
  }}}},
  "evidence_quality": {{{{
    "overall_confidence": 0-100,
    "is_valid_evidence": true|false,
    "evidence_classification": "Pathogenic|Strong Pathogenic|Moderate Pathogenic|Likely Pathogenic|Uncertain Significance|Likely Benign|Benign",
    "classification_reasoning": "Explanation of how the classification was determined"
  }}}},
  "overall_assessment": {{{{
    "total_score": 0-100,
    "final_recommendation": "approved|needs_refinement|rejected",
    "key_strengths": ["strength 1", "strength 2"],
    "key_weaknesses": ["weakness 1", "weakness 2"],
        "improvement_suggestions": ["suggestion 1", "suggestion 2"],
        "evidence_refs": ["E1", "E2"]
  }}}}
}}}}

**IMPORTANT**: Assign overall_confidence >= 85 to mark evidence as valid. Classification rules:
- Score 85-100 → Pathogenic
- Score 80-84 → Strong Pathogenic  
- Score 70-79 → Moderate Pathogenic
- Score 60-69 → Likely Pathogenic
- Score 40-59 → Uncertain Significance
- Score 20-39 → Likely Benign
- Score 0-19 → Benign

**Return only valid JSON. No additional text.**"""


def get_ps3_evidence_feedback_prompt(
    translated_md: str,
    image_descriptions: List[str],
    ps3_evidence: Dict[str, Any],
    arbitration_feedback: str,
    knowledge_context: str = "",
) -> str:
    """
    生成基于仲裁反馈的 PS3 证据修订提示词
    
    Args:
        translated_md: 翻译后的 Markdown 文档
        image_descriptions: 图片描述列表
        ps3_evidence: 当前 PS3 证据评估结果
        arbitration_feedback: 仲裁反馈
        knowledge_context: 可选的知识库检索结果上下文
    """
    knowledge_section = ""
    if knowledge_context:
        knowledge_section = f"""
## REFERENCE KNOWLEDGE BASE DOCUMENTS
{knowledge_context}

---
"""

    image_section = "\n".join(
        [f"### Image {i + 1} Description\n{desc}" for i, desc in enumerate(image_descriptions)]
    )

    return f"""You are a clinical genomics expert specialized in ACMG PS3 (Functional Evidence) classification.
Revise the PS3 evidence JSON using the arbitration feedback while keeping the medical document unchanged.
{knowledge_section}
## MEDICAL DOCUMENT TO EVALUATE
{translated_md}

## IMAGE DESCRIPTIONS
{image_section if image_section else "(none)"}

## CURRENT PS3 EVIDENCE JSON
{json.dumps(ps3_evidence, ensure_ascii=False, indent=2)}

## ARBITRATION FEEDBACK
{arbitration_feedback}

## INSTRUCTIONS
1. Apply the feedback to correct or refine the PS3 evidence assessment.
2. Keep the JSON schema identical to the extraction output format.
3. Update scores and explanations as needed based on the feedback.
4. Strict JSON only: use double quotes for keys/strings, no trailing commas, no extra text.
5. Keep evidence annotations and evidence_refs consistent with the document content.

**Return only valid JSON. No additional text.**"""


def get_arbitration_prompt(
    translated_md: str,
    image_descriptions: List[str],
    ps3_evidence: Dict[str, Any],
    calculated_score: float,
  final_recommendation: str,
  knowledge_context: str = "",
) -> str:
    """
    生成仲裁评分的提示词
    
    Args:
        translated_md: 翻译后的 Markdown 文档
        image_descriptions: 图片描述列表
        ps3_evidence: PS3 证据评估结果
        calculated_score: 计算得到的分数
        final_recommendation: 初步建议
    
    Returns:
        格式化的提示词
    """
    knowledge_section = ""
    if knowledge_context:
      knowledge_section = f"""
  ## REFERENCE KNOWLEDGE BASE DOCUMENTS
  {knowledge_context}

  ---
  """

    image_section = "\n".join(
        [f"### Image {i + 1} Description\n{desc}" for i, desc in enumerate(image_descriptions)]
    )

    return f"""作为医学证据仲裁专家，你只负责核查证据 LLM 输出是否符合 ACMG PS3 的定义与评分逻辑，并给出置信度：
  {knowledge_section}

## 翻译后的文档
{translated_md}

## 图片描述
{image_section if image_section else "(none)"}

## 提取的 PS3 证据评估
{json.dumps(ps3_evidence, ensure_ascii=False, indent=2)}

## 当前评估状态
- 计算得分: {calculated_score}/100
- 初步建议: {final_recommendation}

请作为独立仲裁者，评估以下方面（仅验证，不做重评分或重写证据）：
1. **四步法执行完整性**: 是否严格按照 PS3 四步法进行评估？
2. **证据强度合理性**: 最终证据强度是否符合 PS3/BS3 定义与阈值？
3. **实验质量评估**: 对照组、重复实验、方法可靠性评估是否充分？
4. **OddsPath/对照变异数**: 若使用 OddsPath 或对照数，计算与映射是否正确？

请返回以下格式的评价：
{{{{
  "confidence": <0-1之间的置信度，表示证据是否符合ACMG PS3定义与评分>,
  "agreement_with_initial": true|false,
  "feedback": "详细的改进建议",
  "strengths": ["优点1", "优点2"],
  "weaknesses": ["缺点1", "缺点2"],
  "critical_issues": ["需要立即解决的问题"],
  "final_decision": "approved|reject"
}}}}

仅返回 JSON，不需要额外说明。要求使用双引号，不能有尾随逗号。
当 confidence >= 0.85 时，final_decision 设为 "approved"，否则为 "reject"。"""


def get_feedback_refinement_prompt(
    translated_md: str,
    image_descriptions: List[str],
    arbitration_feedback: str,
  arbitration_confidence: float,
    weaknesses: List[str],
    improvements: List[str]
) -> str:
    """
    生成反馈微调的提示词
    
    Args:
        translated_md: 翻译后的 Markdown 文档
        image_descriptions: 图片描述列表
        arbitration_feedback: 仲裁反馈
        arbitration_confidence: 仲裁置信度
        weaknesses: 关键弱点列表
        improvements: 改进建议列表
    
    Returns:
        格式化的提示词
    """
    weaknesses_str = ', '.join(weaknesses) if weaknesses else '未指明'
    improvements_str = '\n'.join(f'- {sugg}' for sugg in improvements) if improvements else '请根据仲裁反馈进行改进'
    
    image_section = "\n".join(
        [f"### Image {i + 1} Description\n{desc}" for i, desc in enumerate(image_descriptions)]
    )

    return f"""基于 PS3 四步法评审反馈，改进医学文档以提高证据质量：

## 当前文档
{translated_md}

## 图片描述
{image_section if image_section else "(none)"}

## 仲裁反馈
{arbitration_feedback}

## 主要问题
- 仲裁置信度: {arbitration_confidence:.2f}
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

ARBITRATION_CONFIDENCE_THRESHOLD = 0.85  # 仲裁置信度及格线
