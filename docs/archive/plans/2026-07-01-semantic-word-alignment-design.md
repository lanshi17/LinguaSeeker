# Semantic Word Alignment Design

**Status:** completed
**Created:** 2026-07-01
**Completed:** 2026-07-01
**PR:** N/A

## Goal

Bind each translated English block back to the original-language text at semantic word or phrase span level, so the bilingual reader can hover or click a source phrase and highlight the corresponding English phrase, and vice versa.

## Problem

The current translation alignment is block-level. `TranslationAlignmentChunk` stores one original span and one English span per translated block or segment. This is enough for deterministic traceback, but too coarse for the user's Rett case: a long Chinese paragraph can only be selected as one chunk, and any downstream evidence highlight is forced to fall back to sentence/block context instead of the exact source-language phrase.

The fix must also guard against missing alignment. If semantic alignment generation fails, the system must still produce a deterministic token-level fallback so no block is left unbound.

## Scope

In scope:

- Add nested span-pair alignment under `TranslationAlignmentChunk`.
- Generate semantic span pairs per translated block after the English translation is produced.
- Validate span offsets against the exact original and English block text before persistence.
- Provide deterministic token/phrase fallback pairs when semantic generation fails or returns invalid spans.
- Use span pairs in English-to-original traceback where evidence source offsets are available.
- Expose span pairs to the frontend through existing detail APIs.
- Add bilingual reader hover/click linked highlighting using span pairs.

Out of scope:

- Changing the translation model provider or adding a new external alignment service.
- Re-translating old stored documents automatically.
- Claiming perfect linguistic word segmentation for Chinese. The fallback is token/phrase based, while the primary path is semantic span-pair alignment.

## Architecture

The implementation keeps translation as the source of truth and adds a second, typed alignment artifact:

1. Translation creates `source_text` and `translated_text` per block/segment.
2. A new alignment provider asks the configured reasoning/validation model to return JSON span pairs for that block.
3. A validator clamps and verifies every returned pair against both block strings.
4. If semantic generation fails, deterministic fallback tokenizes source and English text and emits monotonic span pairs with low confidence.
5. `_build_translation_alignment()` persists block-level chunks plus `span_pairs`.
6. `translation_traceback.py` maps English source offsets to the narrowest matching span pair before falling back to the existing whole-chunk mapping.
7. The evidence detail API returns `translation_alignment` with nested `span_pairs`.
8. Frontend readers build a bidirectional span index and apply linked hover/click highlights across original and translated panes.

## Contracts

Add a Pydantic model in `backend/src/core/cross_lingual_process_and_extract_evidence/contracts.py`:

```python
class TranslationSpanPair(BaseModel):
    pair_id: str
    original_text: str
    english_text: str
    original_start_offset: int
    original_end_offset: int
    english_start_offset: int
    english_end_offset: int
    confidence: float = 0.0
    method: Literal["semantic_llm", "deterministic_token"] = "deterministic_token"
```

Extend `TranslationAlignmentChunk`:

```python
span_pairs: list[TranslationSpanPair] = Field(default_factory=list)
```

Offsets are relative to the full formatted original and full translated English document, not just block-local text. This keeps traceback and frontend full-text rendering simple.

## Semantic Alignment Prompt

The prompt should be JSON-only and small enough to run per block:

- Input: source language, `chunk_id`, original block text, English block text.
- Output: ordered `pairs[]` with exact copied `original_text` and `english_text`.
- Rules: align clinically meaningful words/phrases, gene symbols, variants, disease names, section labels, numeric values, and key verbs; do not invent text; preserve monotonic order where possible.

The implementation should use `REASONING_LLM_MODEL` configuration if available through the existing translation context. If not yet wired, use the translator's JSON LLM as a first implementation and keep the provider boundary isolated.

## Validation

Every semantic pair is accepted only if:

- The copied original and English text can be located inside the chunk text.
- The computed full-document offsets are within the chunk offsets.
- Ranges are non-empty.
- Pairs do not overlap previous accepted pairs on the same side unless the overlap is exact duplicate content.

Invalid pairs are dropped. If fewer than a useful threshold remain for a non-trivial chunk, fallback pairs are generated.

## Fallback

The deterministic fallback is deliberately simple and predictable:

- Source tokenization:
  - preserve gene symbols, HGVS expressions, numbers, Latin words, and CJK punctuation boundaries;
  - for CJK runs, split into short phrase windows around punctuation and biomedical literals rather than single characters where possible.
- English tokenization:
  - split on word/punctuation boundaries while preserving HGVS and identifiers.
- Pair tokens monotonically by relative position within the block.
- Mark pairs with `method="deterministic_token"` and low confidence.

This fallback is not semantic, but it guarantees a stable hover/click binding surface and prevents total alignment loss.

## Frontend Behavior

The bilingual reader should support:

- Hover original span: highlight the source span and linked English span.
- Hover English span: highlight the English span and linked source span.
- Click span: pin the linked highlight until another span is clicked or Escape clears it.
- Existing evidence highlights remain primary; alignment highlights are a secondary overlay and must not replace evidence colors.

The UI should not add explanatory text. It should behave like a linked reading interaction.

## Failure Handling

- If semantic alignment provider fails for a block, log a warning and generate fallback pairs for that block.
- If both semantic and fallback fail, persist the existing chunk without span pairs and add a translation warning.
- API parsing must tolerate old persisted chunks without `span_pairs`.
- Frontend must degrade to current block/document highlighting when no span pairs are present.

## Testing

Backend tests:

- Contract serialization and backwards compatibility.
- Semantic pair validation with valid, overlapping, out-of-range, and missing-text pairs.
- Fallback generation for Chinese/English Rett-like text.
- Persistence builds full-document offsets inside `TranslationAlignmentChunk.span_pairs`.
- Traceback maps an English evidence source span to a narrower original span pair.

Frontend tests:

- Type parsing accepts `span_pairs`.
- Reader renders linked span overlays for original and translated tracks.
- Hover and click produce bidirectional linked highlighting.
- Missing `span_pairs` keeps existing behavior unchanged.

## Rollout

This is backwards compatible. Existing saved documents have no `span_pairs`, so API and frontend consumers must treat the field as optional/default empty. New pipeline runs will persist semantic or fallback pairs.
