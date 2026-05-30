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
| `get_translate_prompt` | `(markdown_segment, terminology, prev_context="", next_context="") -> str` | Human message for translating one segment. Assembles context, terminology, and rules. |
| `get_full_document_translate_prompt` | `(full_text, terminology, content_blocks=None) -> str` | Full-document block-mode translation prompt with `[BLOCK_N]` markers. |
| `get_self_review_prompt` | `(source, translated) -> str` | Self-review stage: compare source vs translation for quality. |

### `format.py`

| Function | Signature | Description |
|----------|-----------|-------------|
| `get_prescan_prompt` | `(source_text: str) -> str` | LLM prescan to identify and mark missing/redacted values with `[REDACTED]`. |
| `get_format_prompt` | `(markdown_content: str) -> str` | Document formatting: structure normalization + redacted value marking. |

## Internal Design

All prompts are pure functions returning strings. No side effects, no LLM calls. The `translate.py` prompts embed detailed biomedical translation rules:

- Evidence strength mapping (提示→suggestive of, 支持→supportive of, etc.)
- Variant terminology (变异→variant, 突变→mutation)
- HGVS/gene symbol/protein name preservation
- `[REDACTED]` marker preservation
- Author name transliteration rules
- Chinese medical title patterns

## Testing

Prompt tests verify template structure and variable substitution.
