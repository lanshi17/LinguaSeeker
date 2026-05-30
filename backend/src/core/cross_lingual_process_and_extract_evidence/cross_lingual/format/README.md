# Format Module

> Phase 2 submodule — normalizes parsed document markdown, segments text for LLM context windows, extracts sentences with page-level tracking, and computes character drift for bbox preservation.

## Quick Start

```python
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.format import (
    MarkdownFormatter,
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
├─ _split_paragraph()  — sentence-level sub-splitting
└─ paragraph-level merge → preserves structure

MarkdownFormatter [formatter.py]
│
├─ _format_markdown()  — join pages, normalize whitespace, fix headings
├─ build_page_offset_map()  — char offset → page number
├─ extract_sentences()  — split on  。！？.!?  with page tracking
├─ compute_format_drift()  — raw ↔ formatted position mapping
└─ _apply_llm_formatting()  — optional LLM redaction detection
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

Token-budgeted segmentation. Splits on paragraph boundaries first, then sentences, finally hard-splits. Adjusts char budget based on CJK ratio (~1 token/CJK char vs ~4 tokens/ASCII char).

### Key Functions

| Function | Purpose |
|----------|---------|
| `build_page_offset_map(pages)` | Maps character offsets to page numbers for bbox tracking |
| `extract_sentences(text, page_offset_map)` | Sentence splitting with page-level position tracking |
| `compute_format_drift(raw_text, sentences)` | Aligns formatted sentences back to raw text positions |
| `estimate_tokens(text)` | Approximates token count (no LLM needed) |

### Data Types (from parent contracts)

| Type | Description |
|------|-------------|
| `FormattedDocument` | Normalized markdown, sentences, metadata, raw original, blocks |
| `SentenceRegion` | Sentence text with page, start/end offset |
| `SentenceDrift` | Drift mapping between raw and formatted positions |
| `ContentBlock` | Structured content block with bbox |

## Internal Design

### Token estimation

Uses a hybrid heuristic: ASCII characters count as 0.25 tokens each, non-ASCII (CJK) count as 1 token each. This matches OpenAI/Claude tokenizer behavior closely enough for budget management without requiring a real tokenizer dependency.

### Page tracking

`build_page_offset_map()` records the cumulative character position at which each page starts. `extract_sentences()` then resolves each sentence's start offset through this map to determine its page number. This enables downstream bbox → page → sentence resolution.

### Drift computation

Formatting (whitespace normalization, heading fixes) shifts character positions. `compute_format_drift()` uses fuzzy string matching (exact → normalized prefix) to realign formatted sentences to raw text, producing per-sentence offset deltas.

### LLM formatting

When `llm` is provided, `_apply_llm_formatting()` sends the formatted markdown to the LLM with a redaction-detection prompt. Safety: output is rejected if length differs by >30% from input.

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
