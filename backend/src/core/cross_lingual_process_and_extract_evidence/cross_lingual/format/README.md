# Format Module

> Phase 2 submodule — normalizes parsed document markdown, segments text for LLM context windows, extracts sentences with page-level tracking, and computes character drift for bbox preservation.

## Quick Start

```python
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.format.formatter import (
    MarkdownFormatter,
)
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.format.segmenter import (
    segment_text,
)

# Normalize MinerU-parsed document
formatter = MarkdownFormatter()
doc = formatter.format(pages, content_blocks=blocks)
print(f"{len(doc.sentences)} sentences across {doc.metadata['page_count']} pages")

# Segment for LLM input
chunks = segment_text(doc.formatted_markdown, max_tokens=4096)
```

## Architecture

```
segment_text() [segmenter.py]
│
├─ estimate_tokens()  — rough tokenizer (ASCII ÷ 4, CJK × 1)
├─ _split_paragraph()  — sentence-level sub-splitting with max_chars guard
└─ paragraph-level merge → preserves structure
    └─ CJK ratio-aware char budget (4.0 - cjk_ratio * 2.8 chars/token)

MarkdownFormatter [formatter.py]
│
├─ _format_markdown()  — join pages, normalize whitespace, fix headings
│   └─ ContentBlock.from_mineru_block()  — build structured blocks from MinerU content_list
├─ build_page_offset_map()  — char offset → page number
├─ _resolve_page()  — resolve character offset to page via offset map
├─ extract_sentences()  — split on 。！？.!?  with page tracking (regex finditer)
├─ compute_format_drift()  — raw ↔ formatted position mapping (exact → normalized prefix)
├─ _find_raw_offset()  — find sentence position in raw text (exact → fuzzy fallback)
├─ _is_html()  — detect HTML error pages from LLM output
└─ _apply_llm_formatting()  — optional LLM redaction detection
    └─ HTML rejection + length-mismatch safety (>30%) + [REDACTED] marker counting
```

## Public API

### `MarkdownFormatter`

```python
class MarkdownFormatter(BaseFormatter):
    def __init__(self, llm: Any = None)
    def format(self, pages: List[Dict], content_blocks: List[Dict] | None = None) -> FormattedDocument
    def compute_drift(self, raw_text: str, formatted_sentences: List[SentenceRegion]) -> List[SentenceDrift]
```

### `segment_text()`

```python
def segment_text(
    text: str,
    max_tokens: int = 8192,
    prompt_overhead_tokens: int = 0,
) -> List[str]:
```

Token-budgeted segmentation. Splits on paragraph boundaries first, then sentences, finally hard-splits. Adjusts char budget based on CJK ratio using a blended formula: `chars_per_token = 4.0 - cjk_ratio * 2.8` (ASCII-heavy ~4 chars/token, CJK-heavy ~1.2 chars/token). The internal `_split_paragraph()` also enforces a `max_chars` guard derived from the token budget.

### Key Functions

| Function | Purpose |
|----------|---------|
| `build_page_offset_map(pages)` | Maps character offsets to page numbers for bbox tracking |
| `_resolve_page(offset, page_map)` | Resolve a character offset to its page number via the offset map |
| `extract_sentences(text, page_offset_map)` | Sentence splitting with page-level position tracking (regex `finditer`, trailing segment capture) |
| `compute_format_drift(raw_text, sentences)` | Aligns formatted sentences back to raw text positions (exact -> normalized-prefix fuzzy) |
| `_find_raw_offset(sentence, raw_text, search_start)` | Find sentence position in raw text; returns `(-1, -1)` if not found |
| `estimate_tokens(text)` | Approximates token count (no LLM needed) |
| `_is_html(text)` | Detect HTML documents (used to reject LLM error pages) |

### Data Types (from parent contracts)

| Type | Description |
|------|-------------|
| `FormattedDocument` | Normalized markdown, sentences, metadata, raw original, original blocks |
| `SentenceRegion` | Sentence text with page, start/end offset |
| `SentenceDrift` | Drift mapping between raw and formatted positions (sentence_index, page, raw/formatted offsets, drift delta) |
| `ContentBlock` | Structured content block with bbox; built from MinerU blocks via `ContentBlock.from_mineru_block()` |

## Internal Design

### Token estimation

`estimate_tokens()` uses a hybrid heuristic: ASCII characters count as 0.25 tokens each (`ascii_chars / 4`), non-ASCII (CJK) characters count as 1 token each. This matches OpenAI/Claude tokenizer behavior closely enough for budget management without requiring a real tokenizer dependency. O(n) scan, ~0.1ms for 100KB text.

### Page tracking

`build_page_offset_map()` records the cumulative character position at which each page starts. `extract_sentences()` then resolves each sentence's start offset through this map to determine its page number. This enables downstream bbox → page → sentence resolution.

### Drift computation

Formatting (whitespace normalization, heading fixes) shifts character positions. `compute_format_drift()` uses fuzzy string matching (exact → normalized prefix) to realign formatted sentences to raw text, producing per-sentence offset deltas.

### LLM formatting

When `llm` is provided, `_apply_llm_formatting()` sends the formatted markdown to the LLM with a redaction-detection prompt (from `translate.prompts.get_format_prompt`). Safety checks:
- Output is rejected if it looks like an HTML error page (`_is_html()`)
- Output is rejected if length differs by >30% from input
- `[REDACTED]` marker count is logged (new markers added by LLM)
- On failure, the original document is preserved unchanged

The LLM is invoked synchronously via LangChain's `invoke()` (not async).

## Usage Patterns

### Basic formatting

```python
formatter = MarkdownFormatter()
doc = formatter.format(mineru_pages)
# doc.formatted_markdown — cleaned text
# doc.sentences — list of SentenceRegion with page numbers
```

### With LLM redaction detection

```python
from langchain_core.language_models import BaseChatModel
llm = get_llm()  # your LangChain model
formatter = MarkdownFormatter(llm=llm)
doc = formatter.format(pages)
# [REDACTED] markers inserted for sensitive content
```

### Text segmentation for translation

```python
chunks = segment_text(
    long_article,
    max_tokens=4096,
    prompt_overhead_tokens=500,  # reserve for system prompt
)
for i, chunk in enumerate(chunks):
    print(f"Chunk {i}: {len(chunk)} chars, ~{estimate_tokens(chunk)} tokens")
```

## Extension Guide

### Adding a new formatter

Subclass `BaseFormatter`:

```python
class MyFormatter(BaseFormatter):
    def format(self, pages, content_blocks=None) -> FormattedDocument:
        # Custom formatting logic
        return FormattedDocument(...)
```

### Changing segmentation strategy

Modify `_split_paragraph()` to use a different sub-division heuristic, or change `estimate_tokens()` to use a real tokenizer library.

## Performance Notes

- `estimate_tokens()` is O(n) but very fast (~0.1 ms for 100 KB text)
- `_find_raw_offset()` uses linear search as fallback — worst case O(n²) for highly divergent texts
- Segmentation is CPU-bound, no I/O

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `re` | Sentence splitting, whitespace normalization |
| `loguru` | Logging |
| `langchain_core.messages.HumanMessage` | LLM formatting (optional) |
| Parent contracts (`...contracts`) | FormattedDocument, SentenceRegion, ContentBlock |

## Testing

```bash
uv run pytest tests/ -k "format" -v
```
