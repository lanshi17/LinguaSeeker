"""Translation engine for biomedical documents."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List, Tuple

from loguru import logger

from .exceptions import TranslationError

from .blocks import (
    _BLOCK_SEP,
    join_blocks_with_markers,
    merge_short_keywords,
    split_by_markers,
    split_merged_keywords,
)
from .postprocess import (
    _DOI_RE,
    build_translated_blocks,
    check_block_coverage,
    check_block_language,
    deduplicate_bilingual_blocks,
    flag_quality_issues,
    trim_repetitive_content,
)
from .providers import (
    _to_text,
    create_json_llm,
    create_llm,
    invoke_json_with_retry,
    invoke_with_retry,
)

from ..config_context import TranslationConfigContext
from ..contracts import (
    ContentBlock,
    FormattedDocument,
    TranslationAlignmentChunk,
    TranslationResult,
    TranslationSegment,
)
from ..format.segmenter import estimate_tokens, segment_text
from .alignment import generate_chunk_span_pairs
from .base import BaseTranslator
from .language_detector import _CJK_RE, detect_language
from .prompts import (
    get_full_document_translate_prompt,
    get_self_review_prompt,
    get_system_prompt_generation_prompt,
    get_terminology_prompt,
    get_translate_prompt,
)
from .validator import (
    _IMAGE_REF_RE,
    fix_email_placeholder,
    fix_ocr_truncations,
    fix_word_boundary_redacted,
    normalize_cjk_punctuation,
    normalize_placeholders,
    strip_inline_artifacts,
    strip_prompt_artifacts,
    strip_prompt_echo,
    strip_source_contamination,
    summarize_validation_error,
    validate_image_references_preserved,
    validate_segment,
    validate_translation_output,
)


class MultiStageTranslator(BaseTranslator):
    """Translator with a 3-stage pipeline: terminology → translate → validate.

    Each segment is translated once with terminology and structure constraints
    built into the prompt. Failed segments are automatically retried.
    All LLM settings come from ``TranslationConfigContext``.
    """

    _MAX_SEGMENT_RETRIES: int = 3
    _MAX_TERMINOLOGY_ENTRIES: int = 100
    # When check_block_language flags >40% untranslated source-language blocks,
    # retry the block-mode translation once with a strict English-only prompt.
    # Capped at 1 to bound LLM cost on pathological inputs.
    _MAX_PER_BLOCK_RETRIES: int = 1

    # Token budget for self-review input (source + translation + prompt template).
    # Long documents can exceed the LLM context window; skip self-review when
    # the estimated prompt size surpasses this threshold.
    _SELF_REVIEW_INPUT_BUDGET: int = 24_000

    # Pre-compiled regex for _clean_terminology
    _TERM_HEADER_RE = re.compile(
        r"^(?:TERMINOLOGY_STAGE|FORMAT_STAGE|TRANSLATE_STAGE"
        r"|#\s*Terminology\s+Stage|#\s*Bilingual\s+Term\s+Pairs"
        r"|##\s*Bilingual\s+Term\s+Pairs|##\s*Preservation\s+Rules"
        r"|These bilingual term pairs|Bilingual Terminology Map"
        r"|You are a bilingual|Extract a concise"
        r"|\d+\.\s+\*\*[A-Z])",
        re.IGNORECASE,
    )
    _TERM_SUBSECTION_RE = re.compile(r"^(?:\d+\.\s+)?\*\*[A-Z].*\*\*\s*:?\s*$")
    _TERM_BULLET_PAIR_RE = re.compile(r"^[-*]\s+\*\*(.+?)\*\*\s*[→:→]\s*\*\*(.+?)\*\*")
    _TERM_LANG_SRC_RE = re.compile(
        r"^[-*]\s*(?:Japanese|Source|Chinese|Korean|Russian):\s*(.+?)\s*$",
        re.IGNORECASE,
    )
    _TERM_LANG_TGT_RE = re.compile(
        r"^[-*]\s*(?:English|Target):\s*(.+?)\s*$",
        re.IGNORECASE,
    )
    _TERM_SIMPLE_PAIR_RE = re.compile(r"^[-*]?\s*(.+?)\s*[→:→]\s*(.+)$")

    def __init__(self, ctx: TranslationConfigContext):
        self._ctx = ctx
        self._llm = create_llm(
            ctx.model,
            ctx.api_key,
            ctx.base_url,
            ctx.temperature,
            ctx.max_tokens,
            ctx.timeout,
            api_keys=ctx.api_keys,
            local_base_url=ctx.local_base_url,
            local_target_lang=ctx.local_target_lang,
            local_timeout=ctx.local_timeout,
        )
        self._json_llm = create_json_llm(
            ctx.model,
            ctx.api_key,
            ctx.base_url,
            ctx.temperature,
            ctx.max_tokens,
            ctx.timeout,
            api_keys=ctx.api_keys,
            local_base_url=ctx.local_base_url,
            local_target_lang=ctx.local_target_lang,
            local_timeout=ctx.local_timeout,
        )

    @staticmethod
    def _parse_terminology(raw: str, source_language: str = "unknown") -> Dict[str, str]:
        """Parse 'source: target' lines into a dict.

        Validates: short terms (not sentences/notes), source side is not
        identical to target (avoids English→English echo).  For CJK source
        languages the source side must contain non-ASCII characters; for
        Latin-script sources (es, pt, ru, etc.) ASCII source terms are
        accepted since the source itself uses Latin characters.
        Deduplicates by target value and caps at _MAX_TERMINOLOGY_ENTRIES.
        """
        # CJK languages require non-ASCII source terms
        _CJK_LANGS = {"zh", "ja", "ko"}
        require_non_ascii = source_language in _CJK_LANGS

        result: Dict[str, str] = {}
        seen_targets: set[str] = set()
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            # Strip numbered prefixes like "33. "
            line = re.sub(r"^\d+\.\s+", "", line)
            # Skip lines starting with * (LLM notes/explanations)
            if line.startswith("*"):
                continue
            match = re.match(r"^(.+?):\s*(.+)$", line)
            if not match:
                continue
            source = match.group(1).strip()
            target = match.group(2).strip()
            # Strip instruction annotations like "(保留)", "(keep)", "(preserve)"
            target = re.sub(r"\s*\(保留\)\s*$", "", target)
            target = re.sub(r"\s*\(keep\)\s*$", "", target, flags=re.IGNORECASE)
            target = re.sub(r"\s*\(preserve\)\s*$", "", target, flags=re.IGNORECASE)
            # Skip long entries (notes, explanations, sentences)
            # Use char length for CJK text where word splitting doesn't work
            if len(source) > 50 or len(target) > 50:
                continue
            if len(source.split()) > 10 or len(target.split()) > 10:
                continue
            # For CJK sources, require non-ASCII (actual CJK characters).
            # For Latin-script sources, accept ASCII but skip if source ≈ target
            # (the LLM echoed the term without translating).
            if require_non_ascii and source.isascii():
                continue
            if source.lower().strip() == target.lower().strip():
                continue
            # Deduplicate by normalized target
            target_norm = target.lower().strip()
            if target_norm in seen_targets:
                continue
            seen_targets.add(target_norm)
            result[source] = target
            if len(result) >= MultiStageTranslator._MAX_TERMINOLOGY_ENTRIES:
                logger.warning(
                    "Terminology map capped at {} entries",
                    MultiStageTranslator._MAX_TERMINOLOGY_ENTRIES,
                )
                break
        return result

    @classmethod
    def _clean_terminology(cls, raw: str) -> str:
        """Strip LLM echo artifacts and normalize terminology output.

        The terminology LLM returns structured markdown with headers,
        bullet points, and formatting. This strips artifacts and
        normalizes to simple ``source: target`` pairs.
        """
        if not raw:
            return raw

        lines = raw.splitlines()
        clean: list[str] = []
        pending_src: str | None = None  # buffered source term for lang-pair format

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Skip headers and stage markers
            if cls._TERM_HEADER_RE.match(stripped):
                continue

            # Skip sub-section headers (Preservation Rules, HGVS Notations, etc.)
            if cls._TERM_SUBSECTION_RE.match(stripped):
                pending_src = None
                continue

            # Skip "Keep as is" rules
            if "keep as is" in stripped.lower():
                pending_src = None
                continue

            # Try bullet pair: - **source** → **target**
            m = cls._TERM_BULLET_PAIR_RE.match(stripped)
            if m:
                clean.append(f"{m.group(1).strip()}: {m.group(2).strip()}")
                pending_src = None
                continue

            # Try Japanese/Source: X → buffer as source
            m = cls._TERM_LANG_SRC_RE.match(stripped)
            if m:
                pending_src = m.group(1).strip()
                continue

            # Try English/Target: X → pair with buffered source
            m = cls._TERM_LANG_TGT_RE.match(stripped)
            if m and pending_src:
                clean.append(f"{pending_src}: {m.group(1).strip()}")
                pending_src = None
                continue

            # Simple pair format (non-bold)
            m = cls._TERM_SIMPLE_PAIR_RE.match(stripped)
            if m and "**" not in m.group(1):
                src, tgt = m.group(1).strip(), m.group(2).strip()
                if len(src.split()) <= 10 and len(tgt.split()) <= 10:
                    clean.append(f"{src}: {tgt}")
                pending_src = None
                continue

            # Unknown line — reset pending
            pending_src = None

        return "\n".join(clean).strip()

    async def _generate_system_prompt(self, formatted: FormattedDocument) -> str:
        """Use an LLM to generate an optimal translation system prompt.

        Analyzes the document sample and produces a tailored system message
        that will be reused for all segment translations of this document.
        """
        source_lang = formatted.source_language or "unknown"
        sample = formatted.formatted_markdown[:2000]
        meta_prompt = get_system_prompt_generation_prompt(sample, source_lang)

        logger.info("Generating dynamic system prompt for lang={}", source_lang)
        system_prompt = await invoke_with_retry(self._llm, meta_prompt, "system_prompt_gen")

        # Validate: generated prompt should be reasonable length
        if len(system_prompt) < 50:
            logger.warning("Generated system prompt too short ({} chars), using fallback", len(system_prompt))
            return (
                "You are a professional biomedical translation engine. "
                "Translate to English. Preserve markdown structure, image references, "
                "and biomedical literals exactly. Output only translated markdown."
            )

        logger.info("Generated system prompt ({} chars)", len(system_prompt))
        return system_prompt

    # ── Pipeline stages ──────────────────────────────────────────────────

    async def extract_terminology(self, formatted: FormattedDocument) -> str:
        logger.info("Stage: terminology")
        text = formatted.formatted_markdown
        overhead = estimate_tokens(get_terminology_prompt(""))
        segments = segment_text(text, max_tokens=6000, prompt_overhead_tokens=overhead)

        if len(segments) <= 1:
            raw = await invoke_with_retry(
                self._llm,
                get_terminology_prompt(text),
                "terminology",
            )
            return self._clean_terminology(raw)

        async def _extract_one(idx: int, segment: str) -> str:
            prompt = get_terminology_prompt(segment)
            terms = await invoke_with_retry(self._llm, prompt, f"terminology/{idx}")
            logger.info("Terminology segment {}/{} done", idx, len(segments))
            return terms

        all_terms = await asyncio.gather(
            *[_extract_one(idx, seg) for idx, seg in enumerate(segments, start=1)],
            return_exceptions=True,
        )

        # Filter out failed segments (logged in _extract_one)
        successful_terms = [t for t in all_terms if isinstance(t, str)]

        # Merge: deduplicate by keeping unique source:target pairs
        merged = "\n".join(successful_terms)
        seen: set[str] = set()
        unique_lines: list[str] = []
        for line in merged.splitlines():
            key = line.strip().lower()
            if key and key not in seen:
                seen.add(key)
                unique_lines.append(line.strip())
        return self._clean_terminology("\n".join(unique_lines))

    async def _extract_terminology_json_pairs(self, text: str) -> list[str]:
        """Extract terminology via JSON mode for more reliable parsing.

        Returns a list of ``source: target`` strings.
        """
        prompt = (
            "Extract bilingual term pairs from the following biomedical text. "
            'Return a JSON object with a single key "terms" whose value is an array '
            'of strings in the format "source_term: target_term". '
            "Focus on biomedical terms, drug names, gene names, disease names, "
            "and technical abbreviations. Include at most 30 pairs.\n\n"
            f"Text:\n{text[:6000]}"
        )
        try:
            raw = await invoke_json_with_retry(self._json_llm, prompt, "terminology_json")
            data = json.loads(raw)
            terms = data.get("terms", [])
            if isinstance(terms, list):
                return [str(t).strip() for t in terms if t]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("JSON terminology extraction failed: {}", exc)
        return []

    # Maximum context tokens for the general-purpose LLM
    _MODEL_MAX_TOKENS: int = 200_000
    # Reserve for input (system prompt + terminology + segment + context)
    _INPUT_BUDGET: int = 16_000
    # Context window per side (prev/next)
    _CONTEXT_CHARS: int = 150

    # ── Full-document translation ─────────────────────────────────────────

    async def _translate_blocks(
        self,
        formatted: FormattedDocument,
        terminology: str,
        non_empty: list[tuple[int, ContentBlock]],
        *,
        strict: bool = False,
    ) -> Tuple[str, List[str], List[str]]:
        """Translate all text/title blocks in a single LLM call.

        Uses ``[BLOCK_N]`` markers to join blocks before translation,
        then splits the translated output on the same markers to recover
        per-block translations. Adjacent short keyword blocks are merged
        before translation to prevent context pollution.

        Args:
            strict: When True, use a stronger English-only prompt as a
                retry after the per-block language check failed once.

        Returns:
            Tuple of (joined_translated_text, source_block_texts, translated_block_texts).
        """
        system_prompt = await self._generate_system_prompt(formatted)
        self._text_block_indices = [i for i, _ in non_empty]

        # Save original source texts before prefix stripping
        source_texts = [block.text for _, block in non_empty]

        # Merge adjacent short keyword blocks to prevent context pollution
        merged_blocks, merge_map = merge_short_keywords(non_empty)

        # Join blocks with markers (strips prefixes)
        marked_source, block_indices, stripped_prefixes, english_overrides = join_blocks_with_markers(merged_blocks)

        logger.info(
            "Translating {} blocks in single call ({} chars), {} English-only blocks preserved, strict={}",
            len(merged_blocks),
            len(marked_source),
            len(english_overrides),
            strict,
        )

        # Single LLM call for the entire document
        prompt = get_full_document_translate_prompt(
            marked_source,
            terminology,
            strict=strict,
        )
        translated = await invoke_with_retry(self._llm, prompt, "translate/full", system_prompt)

        # Strip prompt artifacts
        translated = strip_prompt_echo(translated)
        translated = strip_inline_artifacts(translated)
        translated = strip_prompt_artifacts(translated)
        translated = normalize_cjk_punctuation(translated)
        translated = normalize_placeholders(translated)

        # Split on markers
        translated_parts = split_by_markers(translated, len(merged_blocks))

        # Safety: if marker count mismatch, pad/truncate to avoid index errors
        if len(translated_parts) != len(merged_blocks):
            logger.warning(
                "Marker mismatch: expected {} parts, got {} — padding with empties",
                len(merged_blocks),
                len(translated_parts),
            )
            if len(translated_parts) < len(merged_blocks):
                translated_parts.extend([""] * (len(merged_blocks) - len(translated_parts)))
            else:
                translated_parts = translated_parts[:len(merged_blocks)]

        # Fix [REDACTED] incorrectly inserted inside English words
        translated_parts = [fix_word_boundary_redacted(p) for p in translated_parts]

        # Collect CJK prefix translations for parallel execution
        prefix_tasks: list[tuple[int, asyncio.Task[str]]] = []
        for idx, prefix in enumerate(stripped_prefixes):
            seq = idx + 1  # 1-based sequence number
            if seq in english_overrides:
                # Preserve original English text — don't use LLM translation
                translated_parts[idx] = english_overrides[seq]
                logger.debug("Preserved English block {}: {}...", seq, english_overrides[seq][:60])
            elif prefix and idx < len(translated_parts):
                if _CJK_RE.search(prefix):
                    task = asyncio.create_task(
                        invoke_with_retry(
                            self._llm,
                            f"Translate this label to English (short, 2-5 words): {prefix}",
                            f"translate/prefix/{idx + 1}",
                        )
                    )
                    prefix_tasks.append((idx, task))
                else:
                    translated_parts[idx] = f"{prefix}{translated_parts[idx]}"

        # Await all prefix translations in parallel
        if prefix_tasks:
            results = await asyncio.gather(
                *[t for _, t in prefix_tasks],
                return_exceptions=True,
            )
            for (idx, _), prefix_tr in zip(prefix_tasks, results):
                if isinstance(prefix_tr, Exception):
                    logger.warning("Prefix translation for block {} failed: {}", idx + 1, prefix_tr)
                    continue
                prefix_tr = strip_inline_artifacts(prefix_tr).strip()
                part = translated_parts[idx]
                translated_parts[idx] = f"{prefix_tr} {part}" if part else prefix_tr

        # Split merged keyword blocks back into individual translations
        translated_parts = split_merged_keywords(translated_parts, merge_map)

        joined = _BLOCK_SEP.join(translated_parts)
        logger.info(
            "Translated {} blocks in single call ({} -> {} chars)",
            len(non_empty),
            len(marked_source),
            len(joined),
        )
        return joined, source_texts, translated_parts

    # ── Self-review ──────────────────────────────────────────────────────

    async def _self_review(
        self,
        source_text: str,
        translated_text: str,
        system_prompt: str = "",
    ) -> str:
        """Post-translation quality review and correction.

        Sends the source + translation to the LLM for a generic quality
        check. Returns the corrected translation, or the original if
        the review fails or introduces new issues.
        """
        prompt = get_self_review_prompt(source_text, translated_text)
        prompt_tokens = estimate_tokens(prompt)
        logger.info("Running self-review ({} source chars)", len(source_text))

        if prompt_tokens > self._SELF_REVIEW_INPUT_BUDGET:
            logger.warning(
                "Self-review skipped: prompt_tokens {} exceeds budget {}",
                prompt_tokens,
                self._SELF_REVIEW_INPUT_BUDGET,
            )
            return translated_text

        try:
            reviewed = await invoke_with_retry(self._llm, prompt, "self_review", system_prompt)
        except RuntimeError as exc:
            logger.warning("Self-review failed: {}, keeping original", exc)
            return translated_text

        reviewed = strip_prompt_echo(reviewed)
        reviewed = strip_inline_artifacts(reviewed)
        reviewed = strip_prompt_artifacts(reviewed)

        # Safety: if review destroyed markers or lost too much content, revert
        if len(reviewed) < len(translated_text) * 0.5:
            logger.warning(
                "Self-review too short ({} vs {} chars), keeping original",
                len(reviewed),
                len(translated_text),
            )
            return translated_text

        # Check that block separators survived (if present in original).
        # At this pipeline stage the text contains «BLK» separators
        # (_BLOCK_SEP), not [BLOCK_N] markers which were already consumed
        # by split_by_markers() in _translate_blocks().
        if _BLOCK_SEP in translated_text and _BLOCK_SEP not in reviewed:
            logger.warning("Self-review lost block separators, keeping original")
            return translated_text

        logger.info(
            "Self-review complete ({} -> {} chars)",
            len(translated_text),
            len(reviewed),
        )
        return reviewed

    async def translate_segments(
        self,
        formatted: FormattedDocument,
        terminology: str,
        blocks: List[ContentBlock] | None = None,
        *,
        strict: bool = False,
    ) -> Tuple[str, List[str], List[str]]:
        """Translate document segment by segment with per-segment validation.

        Each segment gets one translation attempt. If validation fails,
        the segment is retried up to ``_MAX_SEGMENT_RETRIES`` times.
        Segments are translated in parallel (bounded by LLM semaphore).

        Args:
            formatted: The formatted document.
            terminology: Extracted terminology string.
            blocks: Optional ContentBlock list. When provided, each non-empty
                text/title block is translated individually for guaranteed
                block-level alignment.
            strict: Forwarded to ``_translate_blocks`` for the retry pass.

        Returns:
            Tuple of (joined_translated_text, source_segments, translated_parts).
        """
        logger.info("Stage: translate")

        # When blocks are available, translate each block individually for
        # guaranteed block-level alignment.
        self._text_block_indices: list[int] = []
        if blocks:
            non_empty = [
                (i, b)
                for i, b in enumerate(blocks)
                if b.text.strip() and (b.type in ("text", "title") or (b.type == "footer" and _DOI_RE.search(b.text)))
            ]
            if non_empty:
                return await self._translate_blocks(
                    formatted,
                    terminology,
                    non_empty,
                    strict=strict,
                )

        text = formatted.formatted_markdown

        # Generate a dynamic system prompt tailored to this document
        system_prompt = await self._generate_system_prompt(formatted)

        # Calculate total overhead: system prompt + base template + context
        sys_tokens = estimate_tokens(system_prompt)
        base_template = get_translate_prompt("", "", "", "")
        base_tokens = estimate_tokens(base_template)
        ctx_sample = "x" * self._CONTEXT_CHARS * 2
        ctx_tokens = estimate_tokens(ctx_sample)

        # Budget for terminology = INPUT_BUDGET - sys - base - context
        available = self._INPUT_BUDGET - sys_tokens - base_tokens - ctx_tokens
        term_tokens = estimate_tokens(terminology)
        if term_tokens > max(available * 0.4, 500):
            # Truncate terminology to fit
            budget_chars = int(len(terminology) * (available * 0.4) / (term_tokens or 1) * 0.9)
            # Snap to nearest newline to avoid splitting mid-entry
            cut = terminology.rfind("\n", 0, max(budget_chars, 200))
            terminology = terminology[: max(cut, 200)]
            term_tokens = estimate_tokens(terminology)
            logger.warning("Truncated terminology to {} tokens", term_tokens)

        # Total overhead for segment_text budget
        overhead = sys_tokens + base_tokens + ctx_tokens + term_tokens
        max_segment_tokens = self._INPUT_BUDGET - overhead
        logger.info(
            "Token budget: sys={} + base={} + ctx={} + terms={} = overhead={}, segment_max={}",
            sys_tokens,
            base_tokens,
            ctx_tokens,
            term_tokens,
            overhead,
            max_segment_tokens,
        )

        segments = segment_text(text, max_tokens=max(2000, max_segment_tokens), prompt_overhead_tokens=overhead)

        total = len(segments)

        async def _translate_segment(idx: int, segment: str) -> str:
            # Provide neighboring context so the LLM can translate coherently
            prev_ctx = segments[idx - 1][-self._CONTEXT_CHARS :] if idx >= 1 else ""
            next_ctx = segments[idx + 1][: self._CONTEXT_CHARS] if idx + 1 < total else ""
            translated = await self._translate_one_segment(
                segment,
                terminology,
                idx + 1,
                total,
                prev_context=prev_ctx,
                next_context=next_ctx,
                system_prompt=system_prompt,
            )
            logger.info("Translate segment {}/{} done", idx + 1, total)
            return translated

        results = await asyncio.gather(
            *[_translate_segment(idx, seg) for idx, seg in enumerate(segments)],
            return_exceptions=True,
        )

        # Replace failed segments with empty strings to maintain alignment
        translated_parts: list[str] = []
        for idx, result in enumerate(results):
            if isinstance(result, str):
                translated_parts.append(result)
            else:
                logger.error("Segment {}/{} translation failed: {}", idx + 1, total, result)
                translated_parts.append("")

        return "\n\n".join(translated_parts), segments, translated_parts

    async def _translate_one_segment(
        self,
        source_segment: str,
        terminology: str,
        idx: int,
        total: int,
        prev_context: str = "",
        next_context: str = "",
        system_prompt: str = "",
    ) -> str:
        """Translate a single segment with validation and retry."""
        prompt = get_translate_prompt(
            source_segment,
            terminology,
            prev_context=prev_context,
            next_context=next_context,
        )
        stage = f"translate/{idx}"
        last_error = ""

        for attempt in range(1, self._MAX_SEGMENT_RETRIES + 1):
            # On retry, use a stronger prompt if previous attempt had CJK issues
            if attempt > 1 and "incomplete_translation" in str(last_error):
                retry_prompt = (
                    "The previous translation was incomplete and compressed the source into a summary. "
                    "Translate the following source text completely into English, sentence by sentence. "
                    "Do NOT summarize, omit, merge, or shorten any medical details. "
                    "Output ONLY the complete English translation.\n\n"
                    f"{source_segment}"
                )
                translated = await invoke_with_retry(self._llm, retry_prompt, stage, system_prompt)
            elif attempt > 1 and "source_language_content" in str(last_error):
                retry_prompt = (
                    f"Translate the following text from Chinese to English. "
                    f"Output ONLY the English translation. "
                    f"Do NOT keep any Chinese characters.\n\n{source_segment}"
                )
                translated = await invoke_with_retry(self._llm, retry_prompt, stage, system_prompt)
            elif attempt == 1:
                # First attempt: use JSON mode to prevent prompt echo
                json_prompt = f'{prompt}\n\nReturn a JSON object with key "translation" containing the translated text.'
                try:
                    raw = await invoke_json_with_retry(self._json_llm, json_prompt, stage, system_prompt)
                    data = json.loads(raw)
                    translated = _to_text(data.get("translation", ""))
                    if not translated:
                        raise ValueError("empty translation field")
                except Exception as exc:
                    logger.warning("JSON translation failed for segment {}/{}: {}", idx, total, exc)
                    # Fallback to non-JSON mode
                    translated = await invoke_with_retry(self._llm, prompt, stage, system_prompt)
            else:
                translated = await invoke_with_retry(self._llm, prompt, stage, system_prompt)

            # Strip prompt artifacts echoed back by the LLM
            translated = strip_prompt_artifacts(translated)

            # Strip any source-language contamination from this segment
            translated = strip_source_contamination(
                translated,
                self._detect_source_lang(source_segment),
            )

            # Validate segment quality
            try:
                validate_segment(source_segment, translated)
                return translated
            except ValueError as exc:
                last_error = str(exc)
                logger.warning(
                    "Segment {}/{} attempt {}/{} validation failed: {}",
                    idx,
                    total,
                    attempt,
                    self._MAX_SEGMENT_RETRIES,
                    exc,
                )
                if attempt == self._MAX_SEGMENT_RETRIES:
                    # Last attempt — accept whatever we have
                    logger.warning(
                        "Segment {}/{} max retries reached, accepting as-is",
                        idx,
                        total,
                    )
                    return translated

        return translated  # unreachable, but satisfies type checker

    @staticmethod
    def _detect_source_lang(text: str) -> str:
        """Quick heuristic to detect source language for contamination stripping."""
        cjk_count = len(_CJK_RE.findall(text[:500]))
        if cjk_count > 50:
            return detect_language(text) or "unknown"
        return "unknown"

    # ── Full pipeline ────────────────────────────────────────────────────

    async def run_pipeline(
        self,
        formatted: FormattedDocument,
        blocks: List[ContentBlock] | None = None,
        *,
        strict: bool = False,
    ) -> Tuple[Dict[str, str], str, str, str, List[str], List[str], List[str]]:
        # ── Stage 1: Translate (terminology + full-document translation) ──
        terminology = await self.extract_terminology(formatted)
        translated, source_segments, translated_parts = await self.translate_segments(
            formatted,
            terminology,
            blocks=blocks,
            strict=strict,
        )

        # ── Stage 2: Self-review (LLM quality check and correction) ──────
        translated = await self._self_review(
            formatted.formatted_markdown,
            translated,
        )

        # ── Stage 3: Normalize (validate, clean, strip artifacts) ────────
        warnings: list[str] = []
        translated = strip_prompt_artifacts(translated)
        translated = strip_inline_artifacts(translated)
        translated = strip_source_contamination(translated, formatted.source_language or "unknown")
        translated = normalize_cjk_punctuation(translated)
        translated = normalize_placeholders(translated)
        translated = fix_email_placeholder(translated)
        translated = fix_ocr_truncations(translated)
        translated = fix_word_boundary_redacted(translated)

        # Guard: detect LLM repetition loops (translated >> source size)
        source_len = len(formatted.formatted_markdown) or 1
        if len(translated) > source_len * 5:
            unique_headings = set(re.findall(r"^#{1,6}\s+.+", translated, re.MULTILINE))
            if len(unique_headings) > 0 and len(translated) / len(unique_headings) > 500:
                logger.warning(
                    "Detected LLM repetition loop: {} chars ({}x source), {} unique headings. "
                    "Trimming to first occurrence of repeated content.",
                    len(translated),
                    len(translated) // source_len,
                    len(unique_headings),
                )
                warnings.append("repetition_loop")
                translated = trim_repetitive_content(translated)

        try:
            validate_translation_output(formatted.formatted_markdown, translated)
        except Exception as exc:
            error_summary = summarize_validation_error(exc)
            warnings.append(error_summary)
            logger.warning("Translation validation warning: {}", error_summary)
            # Critical failures: refuse to produce a result that is clearly
            # untranslated. Raising prevents the caller from persisting garbage.
            if any(
                kw in error_summary for kw in ("unchanged", "non_english_output", "empty", "incomplete_translation")
            ):
                raise TranslationError(error_summary) from exc

        # Validate image references preserved
        # Check block-level images (MinerU format) first, then inline markdown refs
        if blocks:
            source_img_paths = {b.img_path for b in blocks if b.img_path}
            # translated_blocks not yet built here, check inline refs in translated text
            translated_img_paths = set(_IMAGE_REF_RE.findall(translated))
            if source_img_paths and not translated_img_paths:
                # Images are preserved as blocks, not inline refs — this is expected
                logger.info(
                    "Image blocks preserved: {} source images (block-level, not inline)",
                    len(source_img_paths),
                )
            elif source_img_paths - translated_img_paths:
                missing = source_img_paths - translated_img_paths
                warnings.append(f"image_refs: {len(missing)} image references missing")
                logger.warning("Image references missing: {}", missing)
        else:
            try:
                validate_image_references_preserved(formatted.formatted_markdown, translated)
            except ValueError as exc:
                warnings.append(f"image_refs: {exc}")
                logger.warning("Image reference warning: {}", exc)

        terminology_map = self._parse_terminology(terminology, formatted.source_language or "unknown")
        return terminology_map, translated, source_segments, translated_parts, warnings

    async def _translate_auxiliary_blocks(
        self,
        blocks: list[ContentBlock],
        system_prompt: str = "",
    ) -> dict[int, dict[str, Any]]:
        """Translate auxiliary fields (table_body, captions, footnotes) for non-text blocks.

        Returns a dict mapping block index to translated auxiliary fields.
        Batches are translated in parallel.
        """
        aux_translations: dict[int, dict[str, Any]] = {}
        # Collect all translatable auxiliary text
        to_translate: list[tuple[int, str, str]] = []  # (block_idx, field, text)
        for i, block in enumerate(blocks):
            if block.type == "table":
                for cap in block.table_caption:
                    if cap.strip() and _CJK_RE.search(cap):
                        to_translate.append((i, "table_caption", cap.strip()))
                for fn in block.table_footnote:
                    if fn.strip() and _CJK_RE.search(fn):
                        to_translate.append((i, "table_footnote", fn.strip()))
            elif block.type == "image":
                for cap in block.image_caption:
                    if cap.strip() and _CJK_RE.search(cap):
                        to_translate.append((i, "image_caption", cap.strip()))
                for fn in block.image_footnote:
                    if fn.strip() and _CJK_RE.search(fn):
                        to_translate.append((i, "image_footnote", fn.strip()))

        if not to_translate:
            return aux_translations

        # Build batches of 10
        batch_size = 10
        batches: list[list[tuple[int, str, str]]] = []
        for batch_start in range(0, len(to_translate), batch_size):
            batches.append(to_translate[batch_start : batch_start + batch_size])

        async def _translate_batch(batch: list[tuple[int, str, str]]) -> None:
            items_json = [
                {"index": idx, "field": field, "text": text} for idx, (_block_idx, field, text) in enumerate(batch)
            ]
            prompt = (
                "Translate each item from Chinese to English. "
                'Return a JSON object with key "translations" whose value is an array '
                'of objects, each with "index" (int) and "translation" (string). '
                "Preserve numbering and formatting.\n\n"
                f"Items:\n{json.dumps(items_json, ensure_ascii=False)}"
            )
            try:
                raw = await invoke_json_with_retry(self._json_llm, prompt, "aux_translate", system_prompt)
                data = json.loads(raw)
                translations = data.get("translations", [])
                for item in translations:
                    idx = item.get("index")
                    translation = item.get("translation", "")
                    if idx is not None and 0 <= idx < len(batch):
                        block_idx, field, _orig = batch[idx]
                        if block_idx not in aux_translations:
                            aux_translations[block_idx] = {}
                        if field not in aux_translations[block_idx]:
                            aux_translations[block_idx][field] = []
                        aux_translations[block_idx][field].append(translation)
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                logger.warning("Auxiliary translation batch failed: {}", exc)

        await asyncio.gather(
            *[_translate_batch(b) for b in batches],
            return_exceptions=True,
        )
        # Errors are already logged inside _translate_batch
        return aux_translations

    async def _attach_span_pairs_to_segments(
        self,
        segments: list[TranslationSegment],
        source_language: str,
    ) -> None:
        """Attach semantic/fallback span pairs to translation segments."""

        async def _align(segment: TranslationSegment) -> None:
            if (
                not segment.source_text.strip()
                or not segment.translated_text.strip()
                or segment.source_start_offset < 0
                or segment.source_end_offset <= segment.source_start_offset
                or segment.translated_start_offset < 0
                or segment.translated_end_offset <= segment.translated_start_offset
            ):
                return
            chunk_id = segment.chunk_id or f"c_{segment.index + 1:04d}"
            chunk = TranslationAlignmentChunk(
                chunk_id=chunk_id,
                original_text=segment.source_text,
                english_text=segment.translated_text,
                original_start_offset=segment.source_start_offset,
                original_end_offset=segment.source_end_offset,
                english_start_offset=segment.translated_start_offset,
                english_end_offset=segment.translated_end_offset,
                page=segment.source_bbox.page if segment.source_bbox is not None else 1,
                block_index=segment.index,
            )
            segment.span_pairs = await generate_chunk_span_pairs(
                self._json_llm,
                chunk,
                source_language,
                f"alignment/{chunk_id}",
            )

        await asyncio.gather(*[_align(segment) for segment in segments])

    async def translate_to_result(self, formatted: FormattedDocument) -> TranslationResult:
        blocks = formatted.original_blocks or []
        terminology_map, translated, source_segments, translated_parts, warnings = await self.run_pipeline(
            formatted, blocks=blocks if blocks else None
        )
        tr_segments: list[TranslationSegment] = []
        # Compute translated segment offsets by tracking cumulative position
        translated_offset = 0
        source_offset = 0
        for idx, src_seg in enumerate(source_segments):
            src_bbox = None
            for sent in formatted.sentences:
                if sent.text.strip() in src_seg.strip() or src_seg.strip() in sent.text:
                    src_bbox = sent
                    break
            tr_text = translated_parts[idx] if idx < len(translated_parts) else ""
            source_start = formatted.formatted_markdown.find(src_seg, source_offset)
            source_end = source_start + len(src_seg) if source_start >= 0 else -1
            translated_start = translated.find(tr_text, translated_offset) if tr_text else -1
            translated_end = translated_start + len(tr_text) if translated_start >= 0 else -1
            tr_segments.append(
                TranslationSegment(
                    index=idx,
                    source_text=src_seg,
                    translated_text=tr_text,
                    source_bbox=src_bbox,
                    source_start_offset=source_start,
                    source_end_offset=source_end,
                    translated_start_offset=translated_start,
                    translated_end_offset=translated_end,
                )
            )
            if source_end >= 0:
                source_offset = source_end
            if translated_end >= 0:
                translated_offset = translated_end

        # Translate auxiliary fields (captions, footnotes) for non-text blocks
        aux_translations = await self._translate_auxiliary_blocks(blocks)

        # Build translated blocks: split translated text on block delimiter
        translated_blocks = build_translated_blocks(
            blocks,
            tr_segments,
            translated,
            text_block_indices=getattr(self, "_text_block_indices", None),
            aux_translations=aux_translations,
        )

        # Deduplicate adjacent bilingual blocks (e.g. zh docs with English abstract)
        translated_blocks = deduplicate_bilingual_blocks(translated_blocks)

        # Per-block language detection: catch partial translation failures
        # (e.g. ru doc where only first page was translated).
        # If the LLM returned mostly source-language text (a known failure
        # mode for medical/scientific Chinese documents where the LLM
        # reproduces the source alongside the translation), retry once
        # with a strict English-only prompt before raising.
        try:
            check_block_coverage(blocks, translated_blocks)
            check_block_language(
                translated_blocks,
                formatted.source_language or "unknown",
            )
        except TranslationError as exc:
            if ("per_block_check" in str(exc) or "block_coverage" in str(exc)) and self._MAX_PER_BLOCK_RETRIES > 0:
                logger.warning(
                    "Translation block quality check failed ({}). "
                    "Retrying translation with strict English-only prompt.",
                    exc,
                )
                (
                    terminology_map,
                    translated,
                    source_segments,
                    translated_parts,
                    warnings,
                ) = await self.run_pipeline(
                    formatted,
                    blocks=blocks if blocks else None,
                    strict=True,
                )
                tr_segments = []
                translated_offset = 0
                source_offset = 0
                for idx, src_seg in enumerate(source_segments):
                    src_bbox = None
                    for sent in formatted.sentences:
                        if sent.text.strip() in src_seg.strip() or src_seg.strip() in sent.text:
                            src_bbox = sent
                            break
                    tr_text = translated_parts[idx] if idx < len(translated_parts) else ""
                    source_start = formatted.formatted_markdown.find(src_seg, source_offset)
                    source_end = source_start + len(src_seg) if source_start >= 0 else -1
                    translated_start = translated.find(tr_text, translated_offset) if tr_text else -1
                    translated_end = translated_start + len(tr_text) if translated_start >= 0 else -1
                    tr_segments.append(
                        TranslationSegment(
                            index=idx,
                            source_text=src_seg,
                            translated_text=tr_text,
                            source_bbox=src_bbox,
                            source_start_offset=source_start,
                            source_end_offset=source_end,
                            translated_start_offset=translated_start,
                            translated_end_offset=translated_end,
                        )
                    )
                    if source_end >= 0:
                        source_offset = source_end
                    if translated_end >= 0:
                        translated_offset = translated_end
                translated_blocks = build_translated_blocks(
                    blocks,
                    tr_segments,
                    translated,
                    text_block_indices=getattr(self, "_text_block_indices", None),
                    aux_translations=aux_translations,
                )
                translated_blocks = deduplicate_bilingual_blocks(translated_blocks)
                check_block_coverage(blocks, translated_blocks)
                check_block_language(
                    translated_blocks,
                    formatted.source_language or "unknown",
                )
            else:
                raise

        await self._attach_span_pairs_to_segments(
            tr_segments,
            formatted.source_language or "unknown",
        )

        # Flag blocks with quality issues for manual review
        flagged = flag_quality_issues(translated_blocks)
        if flagged:
            warnings.append(f"manual_review: {flagged} blocks flagged for review")
            logger.info("Flagged {} blocks for manual review", flagged)

        return TranslationResult(
            formatted_original=formatted.formatted_markdown,
            translated_english=translated,
            source_language=formatted.source_language or "unknown",
            terminology_map=terminology_map,
            translation_warnings=warnings,
            sentences=formatted.sentences,
            segments=tr_segments,
            original_blocks=blocks,
            translated_blocks=translated_blocks,
        )
