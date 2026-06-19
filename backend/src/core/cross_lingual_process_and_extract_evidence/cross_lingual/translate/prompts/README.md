# Translate Prompts

> LLM prompt templates for the 3-stage translation pipeline: terminology extraction, segment translation, and document formatting.

## Public API

### `terminology.py`

| Function | Signature | Description |
|----------|-----------|-------------|
| `get_terminology_prompt` | `(markdown_content: str) -> str` | Terminology extraction stage prompt. Asks LLM to extract bilingual term pairs. |
| `get_system_prompt_generation_prompt` | `(markdown_sample, source_language) -> str` | Meta-prompt: generate optimal translation system prompt for the document. |

### `translate.py`

| Function | Signature | Description |
|----------|-----------|-------------|
| `get_translate_prompt` | `(markdown_segment, terminology, prev_context="", next_context="") -> str` | Human message for translating one segment. Assembles context, terminology, and rules. Adds `«BLK»` preservation directive if markers detected. |
| `get_full_document_translate_prompt` | `(marked_source, terminology, *, strict=False) -> str` | Full-document block-mode translation prompt with `[BLOCK_N]` markers. When `strict=True`, appends an English-only directive for retry after per-block language check failure. |
| `get_self_review_prompt` | `(source, translated) -> str` | Self-review stage: compare source vs translation for 13 quality checks (untranslated text, placeholders, title conventions, author names, evidence strength, product names, etc.). |

### `format.py`

| Function | Signature | Description |
|----------|-----------|-------------|
| `get_prescan_prompt` | `(source_text: str) -> str` | LLM prescan to identify and mark missing/redacted values with `[REDACTED]`. |
| `get_format_prompt` | `(markdown_content: str) -> str` | Document formatting: structure normalization + redacted value marking. |

## Internal Design

All prompts are pure functions returning strings. No side effects, no LLM calls.

### `terminology.py`

- `get_terminology_prompt()` prefixes the prompt with `TERMINOLOGY_STAGE` marker (used by artifact stripping). Instructs the LLM to extract bilingual term pairs, preserve HGVS/gene symbols/protein names/accession IDs/DOI/PMID.
- `get_system_prompt_generation_prompt()` is a meta-prompt that asks an LLM to generate a document-tailored system prompt. Embeds critical constraints: literal translation, evidence strength mapping, variant/mutation distinction, `[REDACTED]` preservation, no ACMG language.

### `translate.py`

Both translation prompts embed detailed biomedical translation rules:

- **Evidence strength:** 提示->suggestive of, 支持->supportive of, 考虑->consistent with, 明确->confirmed
- **Variant terminology:** 变异->variant (default), 突变->mutation (only when source explicitly says 突变)
- **Medical English:** 'suspected' not 'suspicious' for 疑似/可疑; 'family screening' for 家系筛查
- **Chinese patterns:** Title pattern 'X病N例' -> 'A case of X'; '包括X在内' -> 'including X' (spell out noun)
- **Author names:** Space-separated pinyin with given name before surname (杜涓 -> Du Juan)
- **Preservation:** All `[REDACTED]` markers, `«BLK»` paragraph separators, `[BLOCK_N]` markers, product names, vector names, strain designations, catalog numbers, accession IDs
- **`strict` mode** (`get_full_document_translate_prompt`): Appends directive requiring output to be entirely English, no bilingual format, only allowing pinyin names and established English scientific terms as non-English content

The self-review prompt (`get_self_review_prompt`) checks 13 quality issues: untranslated text, placeholder artifacts (bare dates, 'blank'), redundant section prefixes, title conventions, author spacing, evidence strength terms, medical terminology, dangling modifiers, keyword capitalization, email placeholders, product name fidelity, and no-added-inference constraint.

### `format.py`

- `get_prescan_prompt()` instructs the LLM to scan for missing/blank/redacted values and insert `[REDACTED]` markers
- `get_format_prompt()` combines three tasks: structure normalization, `[REDACTED]` marker insertion for missing values, and OCR truncation repair (e.g., '长 间期' -> '长 R-R 间期')

## Testing

Prompt tests verify template structure and variable substitution.
