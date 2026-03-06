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
### ⚠️ CRITICAL CORE FIELDS (MANDATORY) ⚠️

The following 4 fields are CRITICAL for downstream graph synchronization and evidence record integrity. You MUST exhaustively search the entire document (title, abstract, methods, results, tables, figures, supplementary data) for these fields before reporting them as absent or with low confidence.

**CRITICAL FIELD 1: Gene Symbol (gene_symbol)**
- Why Critical: Required for variant annotation and gene-disease linking in graph database
- Exhaustive Search Strategy:
  - Check TITLE: gene names explicitly mentioned
  - Check ABSTRACT: genes in study context
  - Check METHODS & RESULTS: gene nomenclature in variant descriptions
  - Check VARIANT NOMENCLATURE: Extract from HGVS strings (e.g., "BRCA1 c.68_69delAG" → gene = BRCA1)
  - Check FIGURE LEGENDS: genes mentioned in figure descriptions
  - Check TABLES: gene columns in variant summary tables
  - Check SUPPLEMENTARY DATA: gene annotations if provided
- Fallback Inference: If gene not explicitly stated but variant HGVS available, extract gene symbol from HGVS string
- Confidence Rule: 0 ONLY if gene is genuinely absent from entire document after exhaustive search; otherwise ≥60

**CRITICAL FIELD 2: Transcript ID (transcript_id)**
- Why Critical: Essential for variant curation and protein effect interpretation
- Exhaustive Search Strategy:
  - Check METHODS SECTION: often specifies transcript used (e.g., "using RefSeq NM_000527.4")
  - Check VARIANT NOMENCLATURE: HGVS strings often contain transcript ID (e.g., "NM_000527.4:c.1234C>T" → transcript = NM_000527.4)
  - Check VARIANT TABLES: dedicated transcript ID column
  - Check SUPPLEMENTARY DATA: variant annotation tables with transcript information
  - Check FIGURE ANNOTATIONS: variant descriptions in figures may include transcript
  - Check RESULTS TEXT: variant descriptions may reference specific transcripts
- Fallback Inference: If HGVS is available (c. nomenclature), extract transcript ID from HGVS string format
- Fallback Strategy: If no explicit transcript but gene + variant available, use gene's canonical transcript (RefSeq or Ensembl canonical)
- Confidence Rule: 95+ if explicitly listed with NM_ or ENST prefix; 60-70 if inferred from HGVS; 50 if using canonical fallback; 0 ONLY after exhaustive search

**CRITICAL FIELD 3: Variant HGVS (variant_hgvs) - c. and p. nomenclature**
- Why Critical: Foundation for all variant-level analyses and phenotype association
- Exhaustive Search Strategy:
  - Check TITLE: variant designation often in title
  - Check ABSTRACT: variant nomenclature in study summary
  - Check RESULTS SECTION: primary source for variant descriptions
  - Check VARIANT TABLES: dedicated columns for c. (cDNA) and p. (protein) nomenclature
  - Check FIGURE ANNOTATIONS: variants described in figure captions
  - Check METHODS: sometimes reference variants as examples
  - Check SUPPLEMENTARY TABLES: extended variant lists with HGVS
  - Extract BOTH c. (cDNA) and p. (protein) forms when both are available
- Fallback Strategy: If only one form available, attempt to infer the other using genetic code and reference sequence
- Confidence Rule: 95+ if full HGVS with both c. and p. forms; 80-94 if only one form clear; 0 only after exhaustive search fails

**CRITICAL FIELD 4: Disease Name (disease_name)**
- Why Critical: Essential for variant-disease association and clinical context in graph
- Exhaustive Search Strategy:
  - Check TITLE: disease name usually in title
  - Check ABSTRACT INTRODUCTION: clinical context established early
  - Check INTRODUCTION SECTION: disease description and background
  - Check CLINICAL DESCRIPTION: patient phenotypes and disease manifestations
  - Check PATIENT COHORT DESCRIPTION: disease criteria and clinical features
  - Check Discussion: disease interpretation and clinical implications
  - Cross-reference with: Disease_CHPO and Disease_ICD10 fields (extract disease name from these if explicit)
  - Check TABLES: disease columns or patient characteristics
- Fallback Strategy: If disease not explicitly named, extract from phenotype descriptions and clinical features
- Confidence Rule: 95+ if explicit disease name with standard terminology; 70-80 if inferred from phenotypes; 0 ONLY after exhaustive search

**General Confidence Guidance for Core Fields**:
- Assign confidence 0 ONLY after documented exhaustive search of entire document
- If field found but context unclear, assign confidence 50-70 with clear reasoning
- Prefer fallback/inferred values (confidence 50-80) over missing/null (confidence 0)
- Document all search locations and fallback logic in reasoning field

---

### STRUCTURED EVIDENCE FIELD EXTRACTION RULES

You MUST extract the following 11 standardized fields from the document. For each field, provide confidence (0-100) and the exact quote from the document supporting the extraction.

**1. Gene** (CORE FIELD - see Critical Core Fields section above)
- Extract: gene symbol (e.g., BRCA1, TP53, VWF), full name, NCBI Gene ID, Ensembl ID
- Look for: gene names mentioned in title, abstract, methods, results
- Confidence: 95+ if explicitly stated with standard nomenclature; 70-94 if inferred; <70 if ambiguous

**2. Transcript_ID** (CORE FIELD - see Critical Core Fields section above)
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

**9. Variant** (CORE FIELD - see Critical Core Fields section above)
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


# ==================== Agent 问题模板 ====================
QUESTION_TEMPLATE_5 = """
**Instruction:**
You are a highly skilled scientific text analysis and gene variant assessment assistant. Your primary task is to:
1.  **Extract relevant functional evidence details** from the provided scientific paper text for *each variant* mentioned that has functional data.
2.  **Parse variant identification information** to populate the specific fields: "Gene", "Protein Change" (ref, alt, position), and a combined "variant_string_id".
3.  **Apply the ACMG functional evidence evaluation flowchart** to the extracted information for each variant.
4.  **Determine the strength of the functional evidence** (PS3 for pathogenic, BS3 for benign) for each variant.
5.  **Output the results in a pyJSON format**, including the step-by-step judgment process and the final strength rating for each variant.

**Output Format:**
Your final output MUST be a JSON object. The top-level key will be `functional_evidence_assessment`. Its value will be an array of objects, where each object represents the assessment for a single variant. Each variant object should have the following structure:

```json
{
  "variant_id": {
    "Gene": "Extracted_Gene_Symbol", // E.g., "EGFR", "CFTR"
    "Protein_Change": {
      "ref": "Extracted_Reference_Amino_Acid", // E.g., "L", "R"
      "alt": "Extracted_Alternate_Amino_Acid", // E.g., "R", "H"
      "position": "Extracted_Amino_Acid_Position" // E.g., "858", "117"
    },
    "variant_string_id": "Gene RefPosAlt" // E.g., "EGFR L858R", "CFTR R117H"
  },
  "functional_evidence_aim": "Pathogenic", // or "Benign", derived from the paper's context of what the functional assay aims to show
  "assessment_steps": [
    {
      "step_name": "Step 1: Define the disease mechanism",
      "extracted_paper_info": "Quote or concise summary of the relevant text from the paper.",
      "judgment": "Yes", // or "No"
      "reasoning": "Explanation based on extracted info and flowchart logic."
    },
    {
      "step_name": "Step 2: Evaluate applicability of general classes of assay used in the field",
      "extracted_paper_info": "Quote or concise summary of the relevant text from the paper.",
      "judgment": "Yes", // or "No"
      "reasoning": "Explanation based on extracted info and flowchart logic.",
      "next_step_or_outcome": "Proceed to Step 3" // or "Do not use PS3/BS3"
    }
    // ... (Include all relevant sub-steps taken according to the flowchart,
    //     each with "step_name", "extracted_paper_info", "judgment", "reasoning", and "next_step_or_outcome" if applicable)
  ],
  "final_evidence_strength": {
    "type": "Pathogenic", // or "Benign"
    "strength": "PS3_very_strong" // or "PS3", "PS3_moderate", "PS3_supporting", "BS3_very_strong", "BS3", "BS3_moderate", "BS3_supporting", "inconclusive" (return "N/A" only if PS3/BS3 cannot be applied)
  },
  "overall_conclusion": "Brief summary of why this strength was assigned for this variant, referencing key findings."
}
```

**ACMG Functional Evidence Evaluation Flowchart (Reference Standard for LLM's Internal Logic):**

**Step 1: Define the disease mechanism.**
* **Internal Question:** Does the paper clearly define the disease mechanism relevant to the functional assay being described for this variant?
* **Internal Judgment Basis:** Extract explicit statements or strong inferences about the disease's molecular basis and how the gene/protein functions within it.

**Step 2: Evaluate applicability of general classes of assay used in the field.**
* **Internal Question:** Does the *general class* of assay used for this variant (e.g., enzyme activity assay, protein interaction assay, gene expression assay, cell phenotype rescue assay, etc.) effectively model or reflect the disease pathogenesis/mechanism defined in Step 1?
* **Internal Decision Logic:**
    * If **NO**: Then **Do not use PS3/BS3**. (Functional evidence not applicable).
    * If **YES**: Proceed to Step 3.

**Step 3: Evaluate validity of specific instances of assays.**
* **Sub-step 3a: Basic Controls and Replicates.**
    * **Internal Question 1:** Were basic controls included for this assay? Specifically, were *both* "Normal/Negative/Wild type" **AND** "Abnormal/Positive/Null" controls used?
    * **Internal Question 2:** Did the paper explicitly state that multiple replicates were used for the experiments?
    * **Internal Judgment Basis:** Search "Materials and Methods" and "Results" for descriptions of controls (e.g., "wild-type protein," "empty vector," "known loss-of-function mutant," "known gain-of-function mutant") and details on experimental repetition (e.g., "performed in triplicate," "n=3 independent experiments").
    * **Internal Decision Logic (for 3a):**
        * If **NO** (either condition not met): Proceed to Sub-step 3b.
        * If **YES** (both conditions met): Proceed to Sub-step 3c.

* **Sub-step 3b: Accepted/Validated Assay (if basic controls/replicates were insufficient in 3a).**
    * **Internal Question:** Has the specific instance of the assay been:
        * a) Broadly accepted historically (e.g., standard technique in the field)? **OR**
        * b) Previously validated in other studies (cited)? **OR**
        * c) Provided as a commercial kit with defined performance metrics, *but* where controls/replicates are not documented for the specific instance of the assay in *this* paper?
    * **Internal Judgment Basis:** Look for statements on assay novelty, references to prior validation, or mentions of commercial kits/standards.
    * **Internal Decision Logic (for 3b):**
        * If **NO** (all conditions not met): Then **Do not use PS3/BS3**.
        * If **YES** (any condition met): The functional evidence strength is **Max PS3_supporting / Max BS3_supporting**.

* **Sub-step 3c: Variant Controls (if basic controls/replicates were sufficient in 3a).**
    * **Internal Question:** Were variant controls used in the assay for this variant? Specifically, were:
        * Known pathogenic variants used as controls? **OR**
        * Known benign variants used as controls? **OR**
        * Were variants tested that reach P/LP (Pathogenic/Likely Pathogenic) or B/LB (Benign/Likely Benign) criteria *without* relying on PS3/BS3 evidence themselves?
    * **Internal Judgment Basis:** Identify lists of variants used as positive/negative controls and their stated classifications or known status.
    * **Internal Decision Logic (for 3c):**
        * If **NO** (all conditions not met): The functional evidence strength is **Max PS3_supporting / Max BS3_supporting**.
        * If **YES** (any condition met): Proceed to Step 4.

**Step 4: Apply evidence to individual variant interpretation.**
* **Sub-step 4a: Statistical Analyses.**
    * **Internal Question:** Are the statistical analyses in the paper sufficient to estimate or calculate OddsPath for the functional data for this variant? (OddsPath refers to a quantitative measure of pathogenicity likelihood from functional assays).
    * **Internal Judgment Basis:** Look for mentions of statistical tests, p-values, effect sizes, confidence intervals, or direct calculation/reporting of OddsPath.
    * **Internal Decision Logic (for 4a):**
        * If **NO**: Proceed to Sub-step 4b.
        * If **YES**: Proceed to Sub-step 4c.

* **Sub-step 4b: No OddsPath Calculation (if statistical analyses were insufficient).**
    * **Internal Question:** How many total benign/pathogenic variant controls were used across the entire study (as applicable to this variant's assay)?
    * **Internal Judgment Basis:** Count the number of explicitly identified benign and pathogenic control variants used in the assays related to this variant.
    * **Internal Decision Logic (for 4b):**
        * If **10 or less** in total: The functional evidence strength is **Max PS3_supporting / Max BS3_supporting**.
        * If **At least 11** in total: The functional evidence strength is **Max PS3_moderate / Max BS3_moderate**.

* **Sub-step 4c: Correlate OddsPath (if statistical analyses were sufficient).**
    * **Internal Information:** Extract the OddsPath value calculated in the paper for this variant. If a direct OddsPath is not given but robust statistics are, infer the strength.
    * **Internal Judgment Basis:** Apply ACMG guidelines for OddsPath interpretation (project thresholds): PS3 supporting when OddsPath > 1.0 and <= 4.3, PS3 moderate when > 4.3 and <= 18.7, PS3 strong when > 18.7 and <= 350, PS3 very strong when > 350; BS3 supporting when OddsPath >= 0.23 and <= 1.0, BS3 moderate when >= 0.053 and < 0.23, BS3 strong when >= 0.0029 and < 0.053, BS3 very strong when < 0.0029.
    * **Internal Decision Logic (Typical Outcomes):**
        * For PS3 (Pathogenic):
            * OddsPath very high (e.g., > 18.7 and especially > 350): **PS3_very_strong**
            * OddsPath strong (e.g., > 18.7 but not yet meeting very-strong lab policies): **PS3**
            * OddsPath moderate (e.g., > 4.3 and <= 18.7): **PS3_moderate**
            * OddsPath supporting (e.g., > 1.0 and <= 4.3): **PS3_supporting**
        * For BS3 (Benign):
            * OddsPath very low (e.g., < 0.0029): **BS3_very_strong**
            * OddsPath strong (e.g., >= 0.0029 and < 0.053): **BS3**
            * OddsPath moderate (e.g., >= 0.053 and < 0.23): **BS3_moderate**
            * OddsPath supporting (e.g., >= 0.23 and <= 1.0): **BS3_supporting**
"""

QUESTION_TEMPLATE_3 = """
- Role: Professional Scientific Literature Miner and Data Standardization Expert
- Background: The user requires the extraction of detailed information related to genetic variants, diseases, and experimental methods from specific scientific literature. The extracted information needs to be structured and returned in JSON format. The user emphasizes the need to standardize HGVS nomenclature via relevant APIs and retrieve disease terms from the Monarch Disease Ontology (MONDO) database, indicating a high demand for data accuracy and consistency. Additionally, the user specifies that the "Readout description" should include all previously extracted variants, and "Approved assay" should refer to whether the experimental method is generally used for studying the disease.
- Profile: You are an experienced expert in biomedical literature mining and data standardization, familiar with genetic variants, disease associations, and experimental methods. You can accurately extract key information from literature and standardize data using APIs and databases.
- Skills: You possess the ability to accurately extract information, understand and apply HGVS nomenclature and MONDO terms, and are well-versed in various biomedical experimental methods. You can accurately judge key elements of experimental design, such as biological and technical replicates, control settings, and determine normal and abnormal result thresholds based on literature content or your own knowledge. Additionally, you can call relevant APIs for data standardization and retrieve information from databases.
- Goals: Extract all relevant variant information from the literature and standardize the HGVS nomenclature via API; identify the disease studied in the literature and retrieve the corresponding terms from the MONDO database; list all experimental methods mentioned in the literature and extract detailed information about each method, including material sources, readout types, result descriptions, experimental replicates, control settings, statistical analysis methods, and thresholds for normal and abnormal results; determine whether the experimental methods are generally used for studying the disease.
- Constrains: Strictly follow the user-provided JSON format to extract and fill in the information. For content not mentioned in the literature, use "N.D." to indicate. Ensure the extracted information is accurate and conforms to scientific literature standards. Standardize HGVS nomenclature via API and retrieve disease terms from the MONDO database.
- OutputFormat: JSON format, containing variant information, disease description, experimental methods, and their detailed information. The filling method and requirements for each field are as follows:
    {
        "Variants Include": [
            {
                "Gene": "Gene name, e.g., TP53",
                "variants": [
                    {
                        "HGVS": "Variant HGVS nomenclature, in the format (transcript number:cDNA variation), e.g., NM_001126112.3:c.248G>A. Standardize via API.",
                        "cDNA Change": {
                            "transcript": "Transcript number, e.g., NM_001126112.3",
                            "ref": "Reference nucleotide, e.g., G",
                            "alt": "Alternative nucleotide, e.g., A",
                            "position": "Variant position, e.g., 248"
                        },
                        "Protein Change": {
                            "ref": "Reference amino acid, e.g., G",
                            "alt": "Alternative amino acid, e.g., D",
                            "position": "Variant position, e.g., 83"
                        },
                        "Description in input context": "Description of the variant in the literature, e.g., c.248G>A (p.G83D)"
                    }
                ]
            }
        ],
        "Described Disease": {
            "Described Disease": "Disease name studied in the functional experiments in the literature, e.g., Hereditary Myopathy",
            "MONDO": "MONDO term number corresponding to the disease, e.g., MONDO:0012345. Retrieve from MONDO database."
        },
        "Experiment Method": [
            {
                "Assay Method": "Name of the experimental method, e.g., Western Blot",
                "Material used": {
                    "Material Source": "Source of the material, e.g., Cell line/Animal Model/Patients Derived Material",
                    "Material Name": "Name of the material in the literature, e.g., HEK293",
                    "Description": "Original text from the literature describing the material, e.g., 'The experiment was conducted using the HEK293 cell line.'"
                },
                "Readout type": "Type of experimental result readout, e.g., Qualitative/Quantitative",
                "Readout description":"This descriptions should contain all the variants mentioned in Variants Include section"
                [
                    {
                        "Variant": "HGVS nomenclature of the variant from 'Variants Include', in the format (transcript number:cDNA variation)",
                        "Conclusion": "Conclusion of the experimental result, e.g., Abnormal/Normal",
                        "Molecular Effect": "Molecular effect of the variant, e.g., complete loss-of function/partial loss-of-function/intermediate effect/gain-of-function/dominant-negative/No Effect/N.D.",
                        "Result Description": "Specific description of the experimental result for each variant mentioned in the literature or listed in 'Variants Include'."
                    }
                ],
                "Biological replicates": {
                    "Biological replicates": "Whether biological replicate experiments were performed, e.g., Yes/No/N.D.",
                    "Description": "Original text from the literature describing biological replicates, e.g., 'Three biological replicates were performed.'"
                },
                "Technical replicates": {
                    "Technical replicates": "Whether technical replicate experiments were performed, e.g., Yes/No/N.D.",
                    "Description": "Original text from the literature describing technical replicates, e.g., 'Each sample was run in triplicate.'"
                },
                "Basic positive control": {
                    "Basic positive control": "Whether a basic positive control was set up, e.g., Yes/No/N.D.",
                    "Description": "Original text from the literature describing the positive control, e.g., 'Wild-type cDNA was used as a positive control.'"
                },
                "Basic negative control": {
                    "Basic negative control": "Whether a basic negative control was set up, e.g., Yes/No/N.D.",
                    "Description": "Original text from the literature describing the negative control, e.g., 'Empty vector was used as a negative control.'"
                },
                "Validation controls P/LP": {
                    "Validation controls P/LP": "Whether validation controls for pathogenic/likely pathogenic variants were included, e.g., Yes/No/N.D.",
                    "Counts": "Number of validation controls, e.g., 2"
                },
                "Validation controls B/LB": {
                    "Validation controls B/LB": "Whether validation controls for benign/likely benign variants were included, e.g., Yes/No/N.D.",
                    "Counts": "Number of validation controls, e.g., 1"
                },
                "Statistical analysis method": {
                    "Statistical analysis method": "Description of the statistical analysis method used in the experimental protocol, e.g., 'ANOVA was used for statistical analysis.'"
                },
                "Threshold for normal readout": {
                    "Threshold for normal readout": "Threshold for normal results in the literature, e.g., 'Protein expression greater than 80% on day 7.' If not described in the literature, determine the standard for normal results based on your own knowledge.",
                    "Source": "Source of the threshold, e.g., Literature/Custom"
                },
                "Threshold for abnormal readout": {
                    "Threshold for abnormal readout": "Threshold for abnormal results in the literature, e.g., 'Protein expression less than 50% on day 7.' If not described in the literature, determine the standard for abnormal results based on your own knowledge.",
                    "Source": "Source of the threshold, e.g., Literature/Custom"
                },
                "Approved assay": {
                    "Approved assay": "Whether the experimental protocol used in the literature is generally used for studying this disease, e.g., Yes/No/N.D."
                }
            }
        ]
    }
- Workflow:
  1. Read the literature and extract all relevant variant information, including gene name, preliminary HGVS nomenclature, cDNA changes, and protein changes.
  2. Standardize the HGVS nomenclature of the variants via relevant API.
  3. Identify the disease studied in the literature and retrieve the corresponding terms from the MONDO database.
  4. List all experimental methods mentioned in the literature and extract detailed information about each method, including material sources, readout types, result descriptions, experimental replicates, control settings, statistical analysis methods, and thresholds for normal and abnormal results.
  5. Determine whether the experimental methods are generally used for studying the disease.
  6. Organize the extracted and standardized information according to the predefined JSON framework.
- Examples:
  - Example 1: Assume the literature mentions a variant in the TP53 gene, c.248G>A (p.G83D), described as "This variant causes a structural change in the protein, affecting its function." The disease studied is "Hereditary Myopathy," with the corresponding MONDO term "MONDO:0012345."
    {
        "Variants Include": [
            {
                "Gene": "TP53",
                "variants": [
                    {
                        "HGVS": "NM_001126112.3:c.248G>A",
                        "cDNA Change": {
                            "transcript": "NM_001126112.3",
                            "ref": "G",
                            "alt": "A",
                            "position": "248"
                        },
                        "Protein Change": {
                            "ref": "G",
                            "alt": "D",
                            "position": "83"
                        },
                        "Description in input context": "c.248G>A (p.G83D)"
                    }
                ]
            }
        ],
        "Described Disease": {
            "Described Disease": "Hereditary Myopathy",
            "MONDO": "MONDO:0012345"
        },
        "Experiment Method": [
            {
                "Assay Method": "Western Blot",
                "Material used": {
                    "Material Source": "Cell line",
                    "Material Name": "HEK293",
                    "Description": "The experiment was conducted using the HEK293 cell line."
                },
                "Readout type": "Quantitative",
                "Readout description": [
                    {
                        "Variant": "NM_001126112.3:c.248G>A",
                        "Conclusion": "Abnormal",
                        "Molecular Effect": "partial loss-of-function",
                        "Result Description": "Protein expression was reduced by 50% for the variant NM_001126112.3:c.248G>A."
                    }
                ],
                "Biological replicates": {
                    "Biological replicates": "Yes",
                    "Description": "Three biological replicates were performed."
                },
                "Technical replicates": {
                    "Technical replicates": "Yes",
                    "Description": "Each sample was run in triplicate."
                },
                "Basic positive control": {
                    "Basic positive control": "Yes",
                    "Description": "Wild-type cDNA was used as a positive control."
                },
                "Basic negative control": {
                    "Basic negative control": "Yes",
                    "Description": "Empty vector was used as a negative control."
                },
                "Validation controls P/LP": {
                    "Validation controls P/LP": "Yes",
                    "Counts": "2"
                },
                "Validation controls B/LB": {
                    "Validation controls B/LB": "Yes",
                    "Counts": "1"
                },
                "Statistical analysis method": {
                    "Statistical analysis method": "ANOVA was used for statistical analysis."
                },
                "Threshold for normal readout": {
                    "Threshold for normal readout": "Protein expression greater than 80% on day 7.",
                    "Source": "Literature"
                },
                "Threshold for abnormal readout": {
                    "Threshold for abnormal readout": "Protein expression less than 50% on day 7.",
                    "Source": "Literature"
                },
                "Approved assay": {
                    "Approved assay": "Yes"
                }
            }
        ]
    }
"""

QUESTION_TEMPLATE_6 = """
- Role: Professional Medical Literature Data Mining Expert
- Background: The user needs to extract information related to mutations from paragraphs of medical literature, which may involve complex biomedical terminology and specific mutation descriptions. The user aims to quickly and accurately identify whether the literature contains mutation information and extract relevant details.
- Profile: You are an expert with extensive experience in the field of medical literature data mining, familiar with the structure and terminology of biomedical literature, and skilled at precisely extracting key information from large volumes of text.
- Skills: You possess strong text analysis capabilities, a deep understanding of biomedical terminology, and proficient use of data mining techniques, enabling you to quickly identify and extract mutation information from literature.
- Goals: Determine whether the input text paragraph contains information related to mutations. If it does, extract relevant details; if not, return "N.D.".
- Constraints: Extract only information directly related to mutations, ensure the extracted information is accurate, and use "N.D." to supplement content that is not mentioned.
- Output Format: Return the extracted information in the specified JSON format.
- Workflow:
  1. Carefully read the input text paragraph and identify whether it contains mutation-related terms or descriptions.
  2. If mutation information is found, extract specific gene names, cDNA changes, protein changes, and mutation descriptions.
  3. For content not mentioned, supplement with "N.D." to ensure the returned information is complete and meets the format requirements.
- Examples:
  - Example 1: Input text paragraph: "In a study of lung cancer patients, it was found that the c.248G>A (p.G83D) mutation in the TP53 gene is associated with tumor progression."
    Extracted Information:
    ```json
    {
        "Gene": "TP53",
        "variants": [
            {
                "cDNA Change": {
                    "transcript": "N.D.",
                    "ref": "G",
                    "alt": "A",
                    "position": "248"
                },
                "Protein Change": {
                    "ref": "G",
                    "alt": "D",
                    "position": "83"
                },
                "Description in input context": "c.248G>A (p.G83D)"
            }
        ]
    }
    ```
    Generate the JSON output exactly once and stop. Do not include additional explanations or repeated JSON structures.
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
    image_section = "\n".join(
        [f"### Image {i + 1} Description\n{desc}" for i, desc in enumerate(image_descriptions)]
    )

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
| < 0.0029       | BS3_very_strong  |
| 0.0029 - 0.053 | BS3              |
| 0.053 - 0.23   | BS3_moderate     |
| 0.23 - 1.0     | BS3_supporting   |
| 1.0 - 4.3      | PS3_supporting   |
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
9. **Entity/Relation/Experiment extraction**: provide `entity_extractions`, `relation_extractions`, and `experiment_info_extractions` arrays when evidence is available
10. **Position-ready spans**: every `text` in those arrays must be an exact substring and should include `evidence_ref` to anchor offsets

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
    "entity_extractions": [{{{{
        "id": "ENT1",
        "type": "gene|variant|protein|disease|transcript|experiment",
        "text": "Exact substring from the document",
        "evidence_ref": "E1",
        "locator": {{{{
            "file": "en_format.md",
            "start": null,
            "end": null,
            "char_start": null,
            "char_end": null,
            "line_start": null,
            "line_end": null
        }}}}
    }}}}],
    "relation_extractions": [{{{{
        "id": "REL1",
        "type": "gene_variant|variant_disease|gene_disease|custom",
        "evidence_ref": "E1",
        "arguments": [{{{{
            "entity_id": "ENT1",
            "type": "gene|variant|disease|protein|transcript",
            "text": "Exact substring from the document",
            "locator": {{{{
                "file": "en_format.md",
                "start": null,
                "end": null,
                "char_start": null,
                "char_end": null,
                "line_start": null,
                "line_end": null
            }}}}
        }}}}],
        "locator": {{{{
            "file": "en_format.md",
            "start": null,
            "end": null,
            "char_start": null,
            "char_end": null,
            "line_start": null,
            "line_end": null
        }}}}
    }}}}],
    "experiment_info_extractions": [{{{{
        "id": "EXP1",
        "category": "method|result|conclusion",
        "text": "Exact substring from the document",
        "evidence_ref": "E1",
        "locator": {{{{
            "file": "en_format.md",
            "start": null,
            "end": null,
            "char_start": null,
            "char_end": null,
            "line_start": null,
            "line_end": null
        }}}}
    }}}}],
  "ps3_step_1": {{{{
    "disease_mechanism_clarity": "yes|no",
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
      "max_evidence_level": "not_applicable|supporting|moderate",
    "can_proceed": true|false,
        "evidence_refs": ["E3", "E4"],
    "score": 0-30
  }}}},
  "ps3_step_4": {{{{
    "path": "oddspath|control_count|not_applicable",
    "oddspath_data": {{{{
      "computable": true|false,
      "P1": null|float,
      "P2": null|float,
      "oddspath": null|float,
      "evidence_strength": "BS3_very_strong|BS3|BS3_moderate|BS3_supporting|inconclusive|PS3_supporting|PS3_moderate|PS3|PS3_very_strong"
    }}}},
    "control_count_data": {{{{
      "total_variants": null|int,
      "pathogenic_count": null|int,
      "benign_count": null|int,
      "max_evidence_level": "supporting|moderate"
    }}}},
    "final_evidence_strength": "BS3_very_strong|BS3|BS3_moderate|BS3_supporting|inconclusive|PS3_supporting|PS3_moderate|PS3|PS3_very_strong",
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
       "evidence_quote": "exact quote from document",
       "_note": "CORE FIELD - See 'Critical Core Fields' section. Exhaustively search title, abstract, variant nomenclature, figures before reporting absent."
     }}}},
     "transcript_id": {{{{
       "transcript_id": "NM_xxxxxx.x or null",
       "source": "RefSeq|Ensembl|null",
       "confidence": 0-100,
       "evidence_quote": "exact quote or null",
       "_note": "CORE FIELD - See 'Critical Core Fields' section. Extract from HGVS or methods. Infer from canonical transcript if needed."
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
       "evidence_quote": "exact quote",
       "_note": "disease_name is CORE FIELD - See 'Critical Core Fields' section. Search title, abstract, clinical description, patient cohort exhaustively. Also check Disease_ICD10."
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
       "evidence_quote": "exact quote",
       "_note": "CORE FIELD - See 'Critical Core Fields' section. Extract BOTH c. (cDNA) and p. (protein) nomenclature. Search title, abstract, results, variant tables, figures exhaustively."
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
    improvements: List[str],
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
    weaknesses_str = ", ".join(weaknesses) if weaknesses else "未指明"
    improvements_str = (
        "\n".join(f"- {sugg}" for sugg in improvements)
        if improvements
        else "请根据仲裁反馈进行改进"
    )

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
    "BS3_very_strong": 0.0029,
    "BS3": 0.053,
    "BS3_moderate": 0.23,
    "BS3_supporting": 1.0,
    "PS3_supporting": 4.3,
    "PS3_moderate": 18.7,
    "PS3": 350,
    "PS3_very_strong": 350,
}

CONTROL_VARIANTS_THRESHOLDS = {
    "max_supporting": 10,  # ≤10个对照变异，最高 supporting
    "max_moderate": 11,  # ≥11个对照变异，最高 moderate
}

ARBITRATION_CONFIDENCE_THRESHOLD = 0.85  # 仲裁置信度及格线
ARBITRATION_SCORE_THRESHOLD = 85.0  # 仲裁得分（0-100）及格线
