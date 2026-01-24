# User Guide: PS3 Evidence Extraction with Comprehensive PDF Processing

## Quick Start

### Basic Usage

Process a PDF file and extract PS3 evidence:

```bash
# Using main entry point
python main.py path/to/your/document.pdf

# With custom output directory
python main.py path/to/your/document.pdf --out-dir ./my_results
```

### Expected Output

For an input file `example.pdf`, you'll get:

```
outputs/
├── example_en.md                 # English translation of document
├── example_en_highlight.md       # Highlighted evidence spans
├── example_bbox.json            # Text-with-Bbox metadata
├── example_evidence.json        # PS3 evidence extraction
├── example_final.json          # Complete structured output
└── example_report.html         # Interactive bilingual HTML report
```

## Understanding the Output

### 1. Bilingual HTML Report (`*_report.html`)

Open this file in a web browser for an interactive review:

**Layout**:
- **Left Panel**: Original language document
- **Right Panel**: English translation
- **Right Sidebar**: Evidence summary

**Features**:
- Highlighted evidence spans with `<mark>` tags
- Side-by-side synchronized structure
- Evidence metadata (OddsPath, scores, sources)
- Responsive design for different screen sizes

**Data Attributes**:
Each text segment may include:
```html
<span data-page="5" data-bbox="[120,340,400,360]">
  pathogenic variants were present in 45 of 100 cases
</span>
```

These attributes enable:
- Precise coordinate tracking
- Cross-reference to original PDF
- JavaScript-based navigation (future enhancement)

### 2. Final Structured JSON (`*_final.json`)

Complete evidence extraction results:

```json
{
  "detected_language": "zh",              // Detected language code
  "odds_path": 3.5,                       // Calculated OddsPath value
  "evidence_strength": "PS3_supporting",  // ACMG evidence level
  "arbiter_score": 82.5,                  // Quality score (0-100)
  "ps3_criteria_met": true,               // Whether PS3 applicable
  
  "extracted_experimental_details": "Functional assay description...",
  
  "p1_source_location": "Table 2, row 3: pathogenic variants = 45/100",
  "p2_source_location": "Figure 3B: functional abnormality rate = 0.85",
  
  "p1_bbox": {"page": 5, "bbox": [120, 340, 400, 360]},
  "p2_bbox": {"page": 7, "bbox": [200, 450, 500, 480]},
  
  "control_variants_count": 8,            // Number of control variants used
  "odds_path_computable": true,           // Whether OddsPath could be calculated
  "reason_if_not_applicable": "",         // If PS3 not applicable, why?
  
  "findings": [                           // List of evidence spans
    "The variant showed 80% reduction in activity",
    "Wild-type controls were used for comparison",
    "Biological replicates (n=3) confirmed the finding"
  ],
  
  "arbiter_feedback": {                   // Quality evaluation feedback
    "overall_score": 82.5,
    "step_1_disease_mechanism": "Clear description...",
    "step_2_method_suitability": "Appropriate assay...",
    "step_3_experimental_validity": "All components present...",
    "step_4_oddspath_calculation": "Correctly calculated..."
  },
  
  "iterations_performed": 2               // Number of refinement iterations
}
```

### 3. Bbox Metadata JSON (`*_bbox.json`)

Text-with-Bbox metadata for every text fragment:

```json
[
  {
    "page": 1,                            // Page number (1-indexed)
    "bbox": [120, 340, 400, 360],        // [x0, y0, x1, y1] in pixels
    "text": "functional assay results",   // Actual text content
    "fragment_id": 0                      // Sequential fragment ID
  },
  {
    "page": 1,
    "bbox": [120, 370, 450, 390],
    "text": "showed significant reduction",
    "fragment_id": 1
  },
  // ... more fragments
]
```

**Coordinate System**:
- Origin (0,0) at top-left corner of page
- Units: pixels at OCR resolution (typically 300 DPI)
- bbox format: [left, top, right, bottom]

### 4. Evidence Extraction JSON (`*_evidence.json`)

Raw evidence extraction before final packaging:

```json
{
  "findings": ["list of evidence text spans"],
  "p1": 0.45,                             // Proportion in model data
  "p2": 0.85,                             // Proportion in abnormal group
  "odds_path": 3.5,
  "strength": "PS3_supporting",
  "rationale": "Detailed reasoning...",
  "experimental_details": "Assay description...",
  "p1_source_location": "Table 2...",
  "p2_source_location": "Figure 3B...",
  "ps3_criteria_met": true,
  "control_variants_count": 8,
  "odds_path_computable": true,
  "reason_if_not_applicable": "",
  "arbiter_score": 82.5
}
```

## Understanding PS3 Evaluation

### Four-Step SVI Framework

The system evaluates evidence using the ACMG/ClinGen SVI framework:

#### Step 1: Disease Mechanism Clarity
**Question**: Is the pathogenic mechanism clearly described?

**Requirements**:
- Molecular/cellular impact explained
- Tissue relevance specified
- Biochemical consequence described

**Result**:
- ✅ PASS → Continue to Step 2
- ❌ FAIL → PS3/BS3 not applicable

#### Step 2: Functional Assay Method Suitability
**Question**: Is the assay appropriate for this mechanism?

**Examples**:
- Loss of DNA binding → EMSA, ChIP-seq appropriate
- Trafficking defect → Immunofluorescence, cell fractionation appropriate
- Enzyme activity → Activity assay, kinetic studies appropriate

**Result**:
- ✅ PASS → Continue to Step 3
- ❌ FAIL → PS3/BS3 not applicable

#### Step 3: Experimental Validity
**Question**: Are all 4 experimental components adequate?

**Components**:

**a) Controls**
- Required: Normal/wild-type AND abnormal/pathogenic controls
- ❌ Missing → Max evidence level: PS3_supporting

**b) Replicates**
- Required: Biological or technical replicates
- ❌ Missing → Max evidence level: PS3_supporting

**c) Method Reliability**
- Required: Historically validated OR certified kit method
- ❌ Unknown/Unvalidated → PS3/BS3 not applicable

**d) Positive Controls**
- Optional: Known P/LP or B/LB variants as controls
- ✅ Present → Record count; max level: PS3_supporting

**Result**:
- ✅ All components pass → Continue to Step 4
- ❌ Any component fails → Limited evidence level

#### Step 4: Variant-Specific Application & OddsPath

**P1 Definition**: Proportion of pathogenic variants in model data
**P2 Definition**: Proportion of pathogenic variants in functionally abnormal group

**Calculation**:
```
OddsPath = [P2 × (1-P1)] / [(1-P2) × P1]
```

**Strength Mapping**:
```
OddsPath < 0.017     → BS3 (Strong Benign)
0.017 ≤ OddsPath < 0.05   → BS3_moderate
0.05  ≤ OddsPath < 0.33   → BS3_supporting
0.33  ≤ OddsPath < 3.0    → No classification
3.0   ≤ OddsPath < 20     → PS3_supporting
20    ≤ OddsPath < 60     → PS3_moderate
60    ≤ OddsPath          → PS3 (Strong Pathogenic)
```

**Result**:
- ✅ P1 and P2 explicit → Calculate OddsPath, map to strength
- ❌ P1/P2 missing → Record controls, limit to PS3_supporting

### Arbiter Quality Score

**Range**: 0-100

**Evaluation Dimensions**:
1. **Disease Mechanism** (20 points): Clarity and completeness
2. **Method Suitability** (15 points): Appropriateness for mechanism
3. **Experimental Validity** (30 points): All 4 components
   - Controls: 10 points
   - Replicates: 8 points
   - Method reliability: 7 points
   - Positive controls: 5 points
4. **OddsPath Accuracy** (20 points): Correct calculation and mapping
5. **Source Tracing** (15 points): P1/P2 location completeness

**Thresholds**:
- ≥75: High quality, accept
- 50-74: Medium quality, consider manual review
- <50: Low quality, reject or refine

**Iterative Refinement**:
- If score <75: Feedback provided, evidence re-extracted
- Max iterations: 3
- After 3 iterations: Accept best result, flag for manual review

## Advanced Features

### Coordinate-Level Evidence Tracing

The system tracks exact locations of P1/P2 data:

**Example P1 Source**:
```
"p1_source_location": "Table 2, row 3: pathogenic variants = 45/100",
"p1_bbox": {"page": 5, "bbox": [120, 340, 400, 360]}
```

**How to use**:
1. Open the bilingual HTML report
2. Find highlighted P1/P2 data in the document
3. Use bbox coordinates to locate in original PDF
4. Cross-reference with extracted values

**Fallback Behavior**:
If P1/P2 not explicitly reported:
- System searches for keywords: "control group", "wild-type", "benign variant", "pathogenic variant"
- Reports their locations as potential data sources
- Sets `odds_path_computable: false`
- Limits evidence level to PS3_supporting

### Figure and Table Detection

**Detection Method**:
- Pattern matching for "Figure X" and "Table Y" keywords
- Bbox-based boundary detection
- Caption extraction from surrounding text

**Output Format**:
```json
{
  "type": "figure",
  "title": "Figure 1",
  "caption": "Functional assay results showing reduced activity",
  "page": 3,
  "bbox": [100, 200, 500, 600],
  "image_path": null  // Lazy loading supported
}
```

**Usage**:
- Figures and tables are listed in final JSON
- Can be extracted as separate images
- Captions preserved for evidence tracing

### Language Support

**Supported Languages**:
1. **Chinese** (zh): Simplified and Traditional
2. **Japanese** (ja): Kanji, Hiragana, Katakana
3. **English** (en): Primary language
4. **Russian** (ru): Cyrillic script
5. **German** (de): Latin script with umlauts
6. **French** (fr): Latin script with accents

**Detection Method**:
- Heuristic scoring based on character ranges
- Fallback to langdetect library
- Confidence threshold: 0.25

**Translation**:
- All documents translated to English for evidence extraction
- Original language preserved in bilingual HTML
- Glossary terms maintained for consistency

### PDF Type Handling

**Native Searchable PDF**:
- Text extracted directly using PyPDFLoader
- Fast processing
- High accuracy for well-structured PDFs
- Bbox metadata from PDF structure

**Scanned PDF (Image-based)**:
- Converted to images (300 DPI)
- OCR using Qwen-OCR (primary) or pytesseract (fallback)
- Slower processing
- Bbox metadata from OCR output
- May have lower accuracy for poor quality scans

**Detection Criteria**:
- Any page with <50 characters → scanned
- Low text confidence → scanned
- Otherwise → native searchable

## Troubleshooting

### Issue: Low Arbiter Score

**Causes**:
- P1/P2 data not found or unclear
- Missing experimental details (controls, replicates)
- Method reliability not established
- OddsPath calculation incorrect

**Solutions**:
1. Check `reason_if_not_applicable` field
2. Review `p1_source_location` and `p2_source_location`
3. Manually verify experimental details in PDF
4. Check arbiter_feedback for specific issues

### Issue: PS3 Not Applicable

**Common Reasons**:
1. **Disease mechanism unclear**: Paper doesn't explain pathogenic mechanism
2. **Method not suitable**: Assay doesn't match mechanism
3. **Method not validated**: Unestablished or novel method
4. **Missing controls**: No normal/wild-type controls

**What to do**:
- Review `reason_if_not_applicable` field
- Check Step 1-3 evaluation in arbiter_feedback
- Consider if evidence truly supports PS3
- May need manual literature review

### Issue: P1/P2 Data Not Found

**Indicators**:
- `odds_path_computable: false`
- `p1_source_location: "P1/P2 data not explicitly reported"`
- Evidence limited to PS3_supporting

**Solutions**:
1. Check if paper reports quantitative data
2. Look for keywords in highlighted sections
3. Check figures and tables for numerical data
4. May need to extract from graphs or plots manually

### Issue: Bbox Coordinates Missing

**Causes**:
- PDF extraction failed
- OCR skipped
- Text not matched to bbox metadata

**Solutions**:
1. Check if `*_bbox.json` file exists
2. Verify PDF quality (scanned PDFs may have issues)
3. Re-run with `extract_text_with_bbox()` forced
4. Check OCR language setting matches document

## API Usage

### Python API

```python
from src.domain.interfaces import run_pipeline_refactored

# Process a PDF
result = run_pipeline_refactored(
    pdf_path="path/to/document.pdf",
    out_dir="outputs"
)

# Access results
print(f"Language: {result['detected_language']}")
print(f"Arbiter Score: {result['arbiter_score']}")
print(f"Evidence: {result['evidence']}")
print(f"HTML Report: {result['html_report_path']}")
```

### Programmatic Access

```python
from src.application.services import (
    PipelineFactory,
    PipelineContext,
    ResultAccumulator
)

# Create pipeline
processor = PipelineFactory.create_processor_with_defaults()

# Execute
result = processor.process_pdf(
    pdf_path="document.pdf",
    out_dir="outputs"
)

# Access accumulated results
accumulated = processor.get_accumulated_results()
summary = processor.get_execution_summary()
```

## Configuration

### Environment Variables

Create a `.env` file:

```bash
# LLM Configuration
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4
OPENAI_TEMPERATURE=0.2

# OCR Configuration
OCR_BATCH_SIZE=5
OCR_LANGUAGE=auto

# RAG Configuration
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=acmg_knowledge

# Arbiter Configuration
ARBITER_MODEL=gpt-4
ARBITER_TEMPERATURE=0.1
MAX_ITERATIONS=3
QUALITY_THRESHOLD=75
```

### Customization

**Adjust OddsPath Thresholds**:
Edit `src/domain/value_objects/odds_path.py`:
```python
class EvidenceStrength(str, Enum):
    BS3 = "BS3"              # < 0.017
    BS3_MODERATE = "BS3_moderate"  # 0.017-0.05
    # ... adjust as needed
```

**Change Arbiter Scoring**:
Edit `src/infrastructure/llm/arbiter_impl.py`:
```python
# Adjust scoring weights
MECHANISM_WEIGHT = 20
METHOD_WEIGHT = 15
VALIDITY_WEIGHT = 30
ODDSPATH_WEIGHT = 20
TRACING_WEIGHT = 15
```

**Modify HTML Styling**:
Edit `src/infrastructure/rendering/bilingual_html_generator.py`:
```python
# Customize CSS in generate_bilingual_html()
# Change colors, fonts, layout, etc.
```

## Best Practices

### For Best Results

1. **Use High-Quality PDFs**:
   - Native searchable PDFs preferred
   - If scanned, 300+ DPI resolution
   - Clear text, minimal noise

2. **Ensure Complete Papers**:
   - Include methods section
   - Include figures and tables
   - Include supplementary materials if relevant

3. **Check Output Files**:
   - Review HTML report for highlighting accuracy
   - Verify bbox.json for coordinate coverage
   - Check evidence.json for P1/P2 sources

4. **Iterate if Needed**:
   - If arbiter score <75, review feedback
   - Manual verification recommended for borderline cases
   - Consider reprocessing with better quality PDF

### Common Patterns

**Pattern 1: Clear PS3 Evidence**
```
✅ Disease mechanism: clearly described
✅ Method: appropriate functional assay
✅ Controls: wild-type and pathogenic
✅ Replicates: biological n=3
✅ P1/P2: explicitly reported in Table 2
✅ OddsPath: 8.5 → PS3_supporting
✅ Arbiter score: 88
```

**Pattern 2: Limited Evidence**
```
✅ Disease mechanism: described
✅ Method: appropriate
⚠️  Controls: only wild-type (no pathogenic)
❌ Replicates: not mentioned
✅ P1/P2: estimated from text
➡️  Limited to PS3_supporting
⚠️  Arbiter score: 65
```

**Pattern 3: Not Applicable**
```
❌ Disease mechanism: unclear
➡️  PS3/BS3 not applicable
➡️  reason_if_not_applicable: "mechanism unclear"
➡️  Arbiter score: N/A
```

## Support and Feedback

For issues or questions:
1. Check this user guide
2. Review `docs/PS3_EXTRACTION_ENHANCEMENTS.md`
3. Examine example outputs in `outputs/` directory
4. Open an issue on GitHub with:
   - Input PDF characteristics
   - Output JSON files
   - Error messages or unexpected behavior

## Version History

**v1.0** (Current):
- Initial implementation with 4-stage pipeline
- PS3 four-step framework
- Coordinate-level evidence tracing
- Bilingual HTML with bbox attributes
- Arbiter iterative refinement

**Planned Enhancements**:
- RAG fallback to static PDF vectorization
- Automatic secondary P1/P2 retrieval
- Advanced figure/table image extraction
- Interactive HTML with scroll synchronization
- Batch processing for multiple PDFs
