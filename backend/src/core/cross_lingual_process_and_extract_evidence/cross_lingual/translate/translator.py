"""Translation engine for biomedical documents."""
from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Tuple

import httpx
import openai
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import SecretStr

from ...config_context import TranslationConfigContext
from ...contracts import (
    ContentBlock,
    FormattedDocument,
    SegmentDrift,
    TranslationResult,
    TranslationSegment,
)
from ..format.segmenter import estimate_tokens, segment_text
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
    _is_terminology_echo,
    fix_email_placeholder,
    fix_ocr_truncations,
    mark_redacted_values,
    normalize_cjk_punctuation,
    normalize_keywords_capitalization,
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
    _BLOCK_SEP = "\n\n«BLK»\n\n"
    _BLOCK_MARKER_RE = re.compile(r"\[BLOCK_(\d+)\]")

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
        self._llm = ChatOpenAI(
            model=self._ctx.model,
            api_key=SecretStr(self._ctx.api_key),
            base_url=self._ctx.base_url,
            temperature=self._ctx.temperature,
        )
        self._json_llm = ChatOpenAI(
            model=self._ctx.model,
            api_key=SecretStr(self._ctx.api_key),
            base_url=self._ctx.base_url,
            temperature=self._ctx.temperature,
            model_kwargs={"response_format": {"type": "json_object"}},
        )

    @staticmethod
    def _to_text(content: Any) -> str:
        """Extract plain text from LLM response content.

        Handles str, list of content blocks, and single content block dicts.
        Falls back to str() for unknown types.
        """
        if content is None:
            return ""
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    if item.get("type") in ("text", None):
                        text = item.get("text") or item.get("content") or ""
                        if text:
                            parts.append(str(text))
                    # Non-text items (image_url, etc.) are intentionally skipped
            return "\n".join(parts).strip()
        if isinstance(content, dict):
            text = content.get("text") or content.get("content") or ""
            return str(text).strip()
        return str(content).strip()

    # ── Helpers ─────────────────────────────────────────────────────────

    _MAX_RETRIES: int = 3
    _BACKOFF_BASE: float = 30.0  # seconds
    _TRANSIENT_EXCEPTIONS = (
        openai.APITimeoutError,
        openai.APIConnectionError,
        openai.RateLimitError,
        openai.InternalServerError,
        httpx.TimeoutException,
        httpx.ConnectError,
    )

    def _invoke_with_retry(
        self, prompt: str, stage: str, system_prompt: str = "",
    ) -> str:
        """Call LLM with exponential backoff on transient failures.

        Note: qwen-mt-flash only supports user/assistant roles, so
        the system prompt is prepended to the human message.
        """
        if system_prompt:
            content = (
                f"[SYSTEM INSTRUCTIONS — DO NOT output these. Follow them silently.]\n"
                f"{system_prompt}\n"
                f"[END SYSTEM INSTRUCTIONS]\n\n"
                f"{prompt}"
            )
        else:
            content = prompt
        messages = [HumanMessage(content=content)]

        last_exc: Exception | None = None
        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                response = self._llm.invoke(messages)
                return self._to_text(response.content)
            except self._TRANSIENT_EXCEPTIONS as exc:
                last_exc = exc
                delay = self._BACKOFF_BASE * (2 ** (attempt - 1))
                logger.warning(
                    "Stage {} attempt {}/{} failed: {}. Retrying in {:.0f}s",
                    stage, attempt, self._MAX_RETRIES, exc, delay,
                )
                if attempt < self._MAX_RETRIES:
                    time.sleep(delay)
        raise RuntimeError(f"Stage {stage} failed after {self._MAX_RETRIES} attempts") from last_exc

    def _invoke_json_with_retry(
        self, prompt: str, stage: str, system_prompt: str = "",
    ) -> str:
        """Call LLM with JSON mode and exponential backoff on transient failures.

        Returns the raw JSON string from the LLM response.
        """
        if system_prompt:
            content = (
                f"[SYSTEM INSTRUCTIONS — DO NOT output these. Follow them silently.]\n"
                f"{system_prompt}\n"
                f"[END SYSTEM INSTRUCTIONS]\n\n"
                f"{prompt}"
            )
        else:
            content = prompt
        messages = [HumanMessage(content=content)]

        last_exc: Exception | None = None
        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                response = self._json_llm.invoke(messages)
                return self._to_text(response.content)
            except self._TRANSIENT_EXCEPTIONS as exc:
                last_exc = exc
                delay = self._BACKOFF_BASE * (2 ** (attempt - 1))
                logger.warning(
                    "JSON stage {} attempt {}/{} failed: {}. Retrying in {:.0f}s",
                    stage, attempt, self._MAX_RETRIES, exc, delay,
                )
                if attempt < self._MAX_RETRIES:
                    time.sleep(delay)
        raise RuntimeError(f"JSON stage {stage} failed after {self._MAX_RETRIES} attempts") from last_exc

    @staticmethod
    def _parse_terminology(raw: str) -> Dict[str, str]:
        """Parse 'source: target' lines into a dict.

        Validates: short terms (not sentences/notes), source side contains
        non-ASCII (since source language is non-English for translation).
        Deduplicates by target value and caps at _MAX_TERMINOLOGY_ENTRIES.
        """
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
            # Skip long entries (notes, explanations, sentences)
            # Use char length for CJK text where word splitting doesn't work
            if len(source) > 50 or len(target) > 50:
                continue
            if len(source.split()) > 10 or len(target.split()) > 10:
                continue
            # Source side should contain non-ASCII (CJK/non-English term)
            if source.isascii():
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

    def _generate_system_prompt(self, formatted: FormattedDocument) -> str:
        """Use an LLM to generate an optimal translation system prompt.

        Analyzes the document sample and produces a tailored system message
        that will be reused for all segment translations of this document.
        """
        source_lang = formatted.source_language or "unknown"
        sample = formatted.formatted_markdown[:2000]
        meta_prompt = get_system_prompt_generation_prompt(sample, source_lang)

        logger.info("Generating dynamic system prompt for lang={}", source_lang)
        system_prompt = self._invoke_with_retry(meta_prompt, "system_prompt_gen")

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

    def extract_terminology(self, formatted: FormattedDocument) -> str:
        logger.info("Stage: terminology")
        text = formatted.formatted_markdown
        overhead = estimate_tokens(get_terminology_prompt(""))
        segments = segment_text(text, max_tokens=6000, prompt_overhead_tokens=overhead)

        if len(segments) <= 1:
            raw = self._invoke_with_retry(
                get_terminology_prompt(text), "terminology",
            )
            return self._clean_terminology(raw)

        all_terms: list[str] = []
        for idx, segment in enumerate(segments, start=1):
            prompt = get_terminology_prompt(segment)
            terms = self._invoke_with_retry(prompt, f"terminology/{idx}")
            all_terms.append(terms)
            logger.info("Terminology segment {}/{} done", idx, len(segments))

        # Merge: deduplicate by keeping unique source:target pairs
        merged = "\n".join(all_terms)
        seen: set[str] = set()
        unique_lines: list[str] = []
        for line in merged.splitlines():
            key = line.strip().lower()
            if key and key not in seen:
                seen.add(key)
                unique_lines.append(line.strip())
        return self._clean_terminology("\n".join(unique_lines))

    def _extract_terminology_json_pairs(self, text: str) -> list[str]:
        """Extract terminology via JSON mode for more reliable parsing.

        Returns a list of ``source: target`` strings.
        """
        prompt = (
            "Extract bilingual term pairs from the following biomedical text. "
            "Return a JSON object with a single key \"terms\" whose value is an array "
            "of strings in the format \"source_term: target_term\". "
            "Focus on biomedical terms, drug names, gene names, disease names, "
            "and technical abbreviations. Include at most 30 pairs.\n\n"
            f"Text:\n{text[:6000]}"
        )
        try:
            raw = self._invoke_json_with_retry(prompt, "terminology_json")
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

    # ── Block marker helpers ──────────────────────────────────────────────

    @staticmethod
    def _join_blocks_with_markers(
        non_empty: list[tuple[int, ContentBlock]],
    ) -> Tuple[str, list[int], list[str]]:
        """Join text/title blocks into one string with [BLOCK_N] markers.

        Strips ``【摘要】`` prefix (dropped) and ``【关键词】`` prefix
        (saved for re-add after translation). Inserts ``[REDACTED]``
        markers where OCR values are missing.

        Returns:
            Tuple of (marked_text, block_indices, stripped_prefixes).
            ``stripped_prefixes[i]`` corresponds to ``block_indices[i]``.
        """
        parts: list[str] = []
        indices: list[int] = []
        prefixes: list[str] = []

        for seq, (block_idx, block) in enumerate(non_empty, start=1):
            text = block.text

            # Strip 【…】 bracket prefixes
            prefix = ""
            kw_match = re.match(r"^【[^】]+】\s*", text)
            if kw_match:
                bracket = kw_match.group(0)
                text = text[kw_match.end():]
                # Keep 【关键词】 for re-add; drop 【摘要】
                if "摘要" not in bracket:
                    prefix = bracket.strip()

            # Mark redacted values before translation
            text = mark_redacted_values(text)

            indices.append(block_idx)
            prefixes.append(prefix)
            parts.append(f"[BLOCK_{seq}] {text}")

        return "\n\n".join(parts), indices, prefixes

    @staticmethod
    def _split_by_markers(marked_text: str, n_expected: int) -> list[str]:
        """Split LLM output on [BLOCK_N] markers.

        Returns a list of translated texts, one per block. If markers
        are missing, returns the full text as a single element.
        """
        marker_re = re.compile(r"\[BLOCK_(\d+)\]")
        segments: dict[int, str] = {}
        last_end = 0

        for m in marker_re.finditer(marked_text):
            seq = int(m.group(1))
            content_start = m.end()
            # Find the next marker (or end of string)
            next_m = marker_re.search(marked_text, content_start)
            content_end = next_m.start() if next_m else len(marked_text)
            content = marked_text[content_start:content_end].strip()
            # Strip leading newlines/separators
            content = content.lstrip("\n").strip()
            if content:
                segments[seq] = content
            last_end = content_end

        if not segments:
            # No markers found — return full text as single element
            return [marked_text.strip()]

        # Reconstruct in order
        result: list[str] = []
        for seq in range(1, n_expected + 1):
            result.append(segments.get(seq, ""))
        return result

    # ── Full-document translation ─────────────────────────────────────────

    def _translate_blocks(
        self,
        formatted: FormattedDocument,
        terminology: str,
        non_empty: list[tuple[int, ContentBlock]],
    ) -> Tuple[str, List[str], List[str]]:
        """Translate all text/title blocks in a single LLM call.

        Uses ``[BLOCK_N]`` markers to join blocks before translation,
        then splits the translated output on the same markers to recover
        per-block translations.

        Returns:
            Tuple of (joined_translated_text, source_block_texts, translated_block_texts).
        """
        system_prompt = self._generate_system_prompt(formatted)
        self._text_block_indices = [i for i, _ in non_empty]

        # Save original source texts before prefix stripping
        source_texts = [block.text for _, block in non_empty]

        # Join blocks with markers (strips prefixes)
        marked_source, block_indices, stripped_prefixes = (
            self._join_blocks_with_markers(non_empty)
        )

        logger.info(
            "Translating {} blocks in single call ({} chars)",
            len(non_empty), len(marked_source),
        )

        # Single LLM call for the entire document
        prompt = get_full_document_translate_prompt(marked_source, terminology)
        translated = self._invoke_with_retry(prompt, "translate/full", system_prompt)

        # Strip prompt artifacts
        translated = strip_prompt_echo(translated)
        translated = strip_inline_artifacts(translated)
        translated = strip_prompt_artifacts(translated)
        translated = normalize_cjk_punctuation(translated)
        translated = normalize_placeholders(translated)

        # Split on markers
        translated_parts = self._split_by_markers(translated, len(non_empty))

        # Re-add stripped prefixes
        for idx, prefix in enumerate(stripped_prefixes):
            if prefix and idx < len(translated_parts):
                part = translated_parts[idx]
                if _CJK_RE.search(prefix):
                    prefix_tr = self._invoke_with_retry(
                        f"Translate this label to English (short, 2-5 words): {prefix}",
                        f"translate/prefix/{idx + 1}",
                    )
                    prefix_tr = strip_inline_artifacts(prefix_tr).strip()
                    translated_parts[idx] = (
                        f"{prefix_tr} {part}" if part else prefix_tr
                    )
                else:
                    translated_parts[idx] = f"{prefix}{part}"

        joined = self._BLOCK_SEP.join(translated_parts)
        logger.info(
            "Translated {} blocks in single call ({} -> {} chars)",
            len(non_empty), len(marked_source), len(joined),
        )
        return joined, source_texts, translated_parts

    # ── Self-review ──────────────────────────────────────────────────────

    def _self_review(
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
        logger.info("Running self-review ({} source chars)", len(source_text))

        try:
            reviewed = self._invoke_with_retry(prompt, "self_review", system_prompt)
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
                len(reviewed), len(translated_text),
            )
            return translated_text

        # Check that block markers survived (if present in original)
        orig_markers = set(self._BLOCK_MARKER_RE.findall(translated_text))
        reviewed_markers = set(self._BLOCK_MARKER_RE.findall(reviewed))
        if orig_markers and not reviewed_markers:
            logger.warning("Self-review lost block markers, keeping original")
            return translated_text

        logger.info(
            "Self-review complete ({} -> {} chars)",
            len(translated_text), len(reviewed),
        )
        return reviewed

    def translate_segments(
        self, formatted: FormattedDocument, terminology: str,
        blocks: List[ContentBlock] | None = None,
    ) -> Tuple[str, List[str], List[str]]:
        """Translate document segment by segment with per-segment validation.

        Each segment gets one translation attempt. If validation fails,
        the segment is retried up to ``_MAX_SEGMENT_RETRIES`` times.

        Args:
            formatted: The formatted document.
            terminology: Extracted terminology string.
            blocks: Optional ContentBlock list. When provided, each non-empty
                text/title block is translated individually for guaranteed
                block-level alignment.

        Returns:
            Tuple of (joined_translated_text, source_segments, translated_parts).
        """
        logger.info("Stage: translate")

        # When blocks are available, translate each block individually for
        # guaranteed block-level alignment.
        self._text_block_indices: list[int] = []
        if blocks:
            non_empty = [(i, b) for i, b in enumerate(blocks)
                         if b.text.strip() and (b.type in ("text", "title") or
                                                (b.type == "footer" and self._DOI_RE.search(b.text)))]
            if non_empty:
                return self._translate_blocks(
                    formatted, terminology, non_empty,
                )

        text = formatted.formatted_markdown

        # Generate a dynamic system prompt tailored to this document
        system_prompt = self._generate_system_prompt(formatted)

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
            terminology = terminology[:max(cut, 200)]
            term_tokens = estimate_tokens(terminology)
            logger.warning("Truncated terminology to {} tokens", term_tokens)

        # Total overhead for segment_text budget
        overhead = sys_tokens + base_tokens + ctx_tokens + term_tokens
        max_segment_tokens = self._INPUT_BUDGET - overhead
        logger.info(
            "Token budget: sys={} + base={} + ctx={} + terms={} = overhead={}, segment_max={}",
            sys_tokens, base_tokens, ctx_tokens, term_tokens, overhead, max_segment_tokens,
        )

        segments = segment_text(text, max_tokens=max(2000, max_segment_tokens), prompt_overhead_tokens=overhead)

        translated_parts: list[str] = []
        for idx, segment in enumerate(segments, start=1):
            # Provide neighboring context so the LLM can translate coherently
            prev_ctx = segments[idx - 2][-self._CONTEXT_CHARS:] if idx >= 2 else ""
            next_ctx = segments[idx][:self._CONTEXT_CHARS] if idx < len(segments) else ""
            translated = self._translate_one_segment(
                segment, terminology, idx, len(segments),
                prev_context=prev_ctx, next_context=next_ctx,
                system_prompt=system_prompt,
            )
            translated_parts.append(translated)
            logger.info("Translate segment {}/{} done", idx, len(segments))

        return "\n\n".join(translated_parts), segments, translated_parts

    def _translate_one_segment(
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
            source_segment, terminology,
            prev_context=prev_context, next_context=next_context,
        )
        stage = f"translate/{idx}"
        last_error = ""

        for attempt in range(1, self._MAX_SEGMENT_RETRIES + 1):
            # On retry, use a stronger prompt if previous attempt had CJK issues
            if attempt > 1 and "source_language_content" in str(last_error):
                retry_prompt = (
                    f"Translate the following text from Chinese to English. "
                    f"Output ONLY the English translation. "
                    f"Do NOT keep any Chinese characters.\n\n{source_segment}"
                )
                translated = self._invoke_with_retry(retry_prompt, stage, system_prompt)
            elif attempt == 1:
                # First attempt: use JSON mode to prevent prompt echo
                json_prompt = (
                    f"{prompt}\n\n"
                    "Return a JSON object with key \"translation\" containing the translated text."
                )
                try:
                    raw = self._invoke_json_with_retry(json_prompt, stage, system_prompt)
                    data = json.loads(raw)
                    translated = data.get("translation", "")
                    if not translated:
                        raise ValueError("empty translation field")
                except (json.JSONDecodeError, KeyError, ValueError):
                    # Fallback to non-JSON mode
                    translated = self._invoke_with_retry(prompt, stage, system_prompt)
            else:
                translated = self._invoke_with_retry(prompt, stage, system_prompt)

            # Strip prompt artifacts echoed back by the LLM
            translated = strip_prompt_artifacts(translated)

            # Strip any source-language contamination from this segment
            translated = strip_source_contamination(
                translated, self._detect_source_lang(source_segment),
            )

            # Validate segment quality
            try:
                validate_segment(source_segment, translated)
                return translated
            except ValueError as exc:
                last_error = str(exc)
                logger.warning(
                    "Segment {}/{} attempt {}/{} validation failed: {}",
                    idx, total, attempt, self._MAX_SEGMENT_RETRIES, exc,
                )
                if attempt == self._MAX_SEGMENT_RETRIES:
                    # Last attempt — accept whatever we have
                    logger.warning(
                        "Segment {}/{} max retries reached, accepting as-is", idx, total,
                    )
                    return translated

        return translated  # unreachable, but satisfies type checker

    @staticmethod
    def _trim_repetitive_content(text: str) -> str:
        """Remove repetitive heading blocks from LLM output.

        When the LLM enters a repetition loop, it generates the same section
        structure over and over. This function detects repeated heading patterns
        and keeps only the first occurrence plus any content before it.
        """
        paragraphs = re.split(r"\n\s*\n", text)
        seen_headings: list[str] = []
        clean_parts: list[str] = []
        repetition_start: int | None = None

        for idx, para in enumerate(paragraphs):
            stripped = para.strip()
            heading_match = re.match(r"^(#{1,6})\s+(.+)", stripped)
            if heading_match:
                heading_text = heading_match.group(2).strip().lower()
                if heading_text in seen_headings:
                    # Found repeated heading — mark where repetition starts
                    if repetition_start is None:
                        repetition_start = idx
                    continue
                seen_headings.append(heading_text)
            if repetition_start is not None:
                # Skip content after repetition started
                continue
            clean_parts.append(para)

        if repetition_start is None:
            return text

        result = "\n\n".join(clean_parts).strip()
        if len(result) < 100:
            # Safety: if trimming removed almost everything, keep original
            logger.warning("Repetition trim left <100 chars, keeping original")
            return text

        logger.info(
            "Trimmed repetitive content: {} -> {} chars ({} paragraphs removed)",
            len(text), len(result), len(paragraphs) - len(clean_parts),
        )
        return result

    @staticmethod
    def _detect_source_lang(text: str) -> str:
        """Quick heuristic to detect source language for contamination stripping."""
        cjk_count = len(_CJK_RE.findall(text[:500]))
        if cjk_count > 50:
            return detect_language(text) or "unknown"
        return "unknown"

    # ── Full pipeline ────────────────────────────────────────────────────

    def run_pipeline(
        self, formatted: FormattedDocument, blocks: List[ContentBlock] | None = None,
    ) -> Tuple[Dict[str, str], str, str, str, List[str], List[str], List[str]]:
        # ── Stage 1: Translate (terminology + full-document translation) ──
        terminology = self.extract_terminology(formatted)
        translated, source_segments, translated_parts = self.translate_segments(
            formatted, terminology, blocks=blocks,
        )

        # ── Stage 2: Self-review (LLM quality check and correction) ──────
        translated = self._self_review(
            formatted.formatted_markdown, translated,
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

        # Guard: detect LLM repetition loops (translated >> source size)
        source_len = len(formatted.formatted_markdown) or 1
        if len(translated) > source_len * 5:
            unique_headings = set(re.findall(r"^#{1,6}\s+.+", translated, re.MULTILINE))
            if len(unique_headings) > 0 and len(translated) / len(unique_headings) > 500:
                logger.warning(
                    "Detected LLM repetition loop: {} chars ({}x source), {} unique headings. "
                    "Trimming to first occurrence of repeated content.",
                    len(translated), len(translated) // source_len, len(unique_headings),
                )
                warnings.append("repetition_loop")
                translated = self._trim_repetitive_content(translated)

        try:
            validate_translation_output(formatted.formatted_markdown, translated)
        except Exception as exc:
            warnings.append(summarize_validation_error(exc))
            logger.warning("Translation validation warning: {}", warnings[-1])

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

        terminology_map = self._parse_terminology(terminology)
        # Return structure_plan="" for backward compatibility with BaseTranslator
        return terminology_map, "", "", translated, source_segments, translated_parts, warnings

    def _translate_auxiliary_blocks(
        self,
        blocks: list[ContentBlock],
        system_prompt: str = "",
    ) -> dict[int, dict[str, Any]]:
        """Translate auxiliary fields (table_body, captions, footnotes) for non-text blocks.

        Returns a dict mapping block index to translated auxiliary fields.
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

        # Batch translate in groups of 10
        batch_size = 10
        for batch_start in range(0, len(to_translate), batch_size):
            batch = to_translate[batch_start:batch_start + batch_size]
            items_json = [
                {"index": idx, "field": field, "text": text}
                for idx, (block_idx, field, text) in enumerate(batch)
            ]
            prompt = (
                "Translate each item from Chinese to English. "
                "Return a JSON object with key \"translations\" whose value is an array "
                "of objects, each with \"index\" (int) and \"translation\" (string). "
                "Preserve numbering and formatting.\n\n"
                f"Items:\n{json.dumps(items_json, ensure_ascii=False)}"
            )
            try:
                raw = self._invoke_json_with_retry(prompt, "aux_translate", system_prompt)
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

        return aux_translations

    @staticmethod
    def _build_translated_blocks(
        original_blocks: List[ContentBlock],
        segments: List[TranslationSegment],
        translated_text: str,
        text_block_indices: list[int] | None = None,
        aux_translations: dict[int, dict[str, Any]] | None = None,
    ) -> List[ContentBlock]:
        """Map translated text back to original block structure.

        When the source text was built from blocks joined with _BLOCK_SEP,
        the translated text can be split on the same delimiter to recover
        per-block translations. Falls back to segment matching if the
        delimiter is not found.

        Args:
            original_blocks: The original content blocks.
            segments: Translation segments (used for fallback).
            translated_text: The full translated text (may contain delimiters).
            text_block_indices: Indices of blocks that were included in the
                marked text (non-empty text/title blocks).
            aux_translations: Optional dict of auxiliary field translations
                keyed by block index.
        """
        sep = MultiStageTranslator._BLOCK_SEP
        idx_map: dict[int, str] = {}

        # Try delimiter-based split first
        if sep in translated_text:
            parts = translated_text.split(sep)
            # Clean up residual markers and empty pieces
            pieces = []
            for p in parts:
                cleaned = p.replace(sep.strip(), "").strip()
                cleaned = strip_inline_artifacts(cleaned)
                if cleaned:
                    pieces.append(cleaned)
            indices = text_block_indices or []
            for j, piece in enumerate(pieces):
                if j < len(indices):
                    idx_map[indices[j]] = piece
            logger.info(
                "Split translated text on block delimiter: {} pieces from {} blocks",
                len(pieces), len(original_blocks),
            )

        # Count text/title blocks for single-block shortcut
        # Include footer blocks with DOI information as they are also text-based
        text_blocks = [b for b in original_blocks if b.type in ("text", "title") or
                       (b.type == "footer" and MultiStageTranslator._DOI_RE.search(b.text))]

        # Block types that are not body text — filter from downstream output
        # Exception: footer blocks containing DOI information are preserved
        _NON_BODY_TYPES = {"header", "footer", "page_number"}

        translated_blocks: list[ContentBlock] = []
        empty_count = 0
        filtered_non_body = 0
        doi_blocks_preserved = 0
        for i, block in enumerate(original_blocks):
            # Filter non-body blocks (headers, footers, page numbers)
            # but preserve footer blocks containing DOI information
            if block.type in _NON_BODY_TYPES:
                # Check if this footer block contains DOI information
                if block.type == "footer" and MultiStageTranslator._DOI_RE.search(block.text):
                    doi_blocks_preserved += 1
                    # Preserve DOI footer as-is (no translation needed)
                    translated_blocks.append(ContentBlock(
                        type=block.type,
                        page_idx=block.page_idx,
                        bbox=block.bbox,
                        text=block.text,
                    ))
                    continue
                filtered_non_body += 1
                continue

            # Handle text/title blocks AND footer blocks with DOI information
            if block.type in ("text", "title") or (block.type == "footer" and MultiStageTranslator._DOI_RE.search(block.text)):
                if i in idx_map:
                    new_text = idx_map[i]
                elif len(text_blocks) == 1 and translated_text.strip():
                    # Single text block, no delimiter — use full translation
                    new_text = translated_text.strip()
                else:
                    new_text = MultiStageTranslator._fallback_block_text(
                        block, segments,
                    )
                # Filter empty text/title blocks
                if not new_text.strip():
                    empty_count += 1
                    continue
                # Per-block post-processing (placeholders, punctuation, email, OCR)
                new_text = normalize_placeholders(new_text)
                new_text = normalize_cjk_punctuation(new_text)
                new_text = fix_email_placeholder(new_text)
                new_text = fix_ocr_truncations(new_text)
                new_block = ContentBlock(
                    type=block.type,
                    page_idx=block.page_idx,
                    bbox=block.bbox,
                    text=new_text,
                    text_level=block.text_level if block.type in ("text", "title") else None,
                )
            else:
                # Non-text blocks: copy with aux translations if available
                aux = (aux_translations or {}).get(i, {})
                content = block.content
                sub_type = block.sub_type

                # Strip Mermaid diagrams from image blocks — these are
                # LLM-generated reconstructions, not original content.
                # Keep only the image and caption for downstream.
                needs_review = False
                review_reason = ""
                if sub_type == "flowchart" and "mermaid" in (content or "").lower():
                    content = ""
                    sub_type = "pedigree"
                    needs_review = True
                    review_reason = "Mermaid structure does not represent pedigree topology"

                new_block = ContentBlock(
                    type=block.type,
                    page_idx=block.page_idx,
                    bbox=block.bbox,
                    text=block.text,
                    img_path=block.img_path,
                    content=content,
                    image_caption=aux.get("image_caption", list(block.image_caption)),
                    image_footnote=aux.get("image_footnote", list(block.image_footnote)),
                    sub_type=sub_type,
                    table_body=block.table_body,
                    table_caption=aux.get("table_caption", list(block.table_caption)),
                    table_footnote=aux.get("table_footnote", list(block.table_footnote)),
                    text_format=block.text_format,
                    code_body=block.code_body,
                    code_caption=list(block.code_caption),
                    code_sub_type=block.code_sub_type,
                    list_sub_type=block.list_sub_type,
                    list_items=list(block.list_items),
                    chart_caption=list(block.chart_caption),
                    chart_footnote=list(block.chart_footnote),
                    needs_manual_review=needs_review,
                    review_reason=review_reason,
                )
            translated_blocks.append(new_block)

        if empty_count:
            logger.info("Filtered {} empty text/title blocks", empty_count)
        if filtered_non_body:
            logger.info("Filtered {} non-body blocks (header/footer/page_number)", filtered_non_body)
        if doi_blocks_preserved:
            logger.info("Preserved {} footer blocks containing DOI information", doi_blocks_preserved)
        return translated_blocks

    @staticmethod
    def _fallback_block_text(
        block: ContentBlock,
        segments: List[TranslationSegment],
    ) -> str:
        """Fallback: find translated text via segment matching."""
        block_text = block.text.strip()
        if not block_text:
            return ""
        for seg in segments:
            src = seg.source_text.strip()
            if not src:
                continue
            src_start = src[:max(len(block_text) * 2, 100)]
            if src in block_text or block_text in src_start:
                return seg.translated_text
        return ""

    # Pattern to detect DOI content in footer blocks
    _DOI_RE = re.compile(
        r"(?:DOI|doi)\s*[:\s：]*\d+\.\d+/"  # DOI: 10.xxxx/... (including Chinese colon ：)
        r"|https?://doi\.org/"  # https://doi.org/...
        r"|https?://dx\.doi\.org/"  # http://dx.doi.org/...
    )

    # Patterns that indicate truncated or incomplete references
    _TRUNCATED_REF_RE = re.compile(
        r"(?:by et al\.)"                         # "by et al." — missing author name
        r"|(?:In \d{1,2},\s*et al\.)"            # "In 20, et al." (truncated year)
        r"|(?:^|\.\s+)et al\.\s*\[\d+\]"         # "et al. [12]" at start of sentence
    )
    # Pattern for 2-digit year that's likely truncated (e.g., "In 20," instead of "In 2020,")
    _TRUNCATED_YEAR_RE = re.compile(r"\bIn (\d{2}),\s")

    @staticmethod
    def _flag_quality_issues(blocks: list[ContentBlock]) -> int:
        """Flag blocks that need manual review due to quality issues.

        Detects truncated references, ambiguous pronouns, and other
        patterns that indicate OCR/translation problems.

        Returns the number of blocks flagged.
        """
        flagged = 0
        for block in blocks:
            if block.type not in ("text", "title"):
                continue
            text = block.text
            reasons: list[str] = []

            # Truncated references: "et al. [12]" with no author/year
            if MultiStageTranslator._TRUNCATED_REF_RE.search(text):
                reasons.append("truncated reference (missing author/year)")

            # Truncated 2-digit years: "In 20," instead of "In 2020,"
            year_match = MultiStageTranslator._TRUNCATED_YEAR_RE.search(text)
            if year_match:
                reasons.append(f"truncated year ({year_match.group(1)} digits)")

            # Ambiguous pronoun "including that" without clear antecedent
            if re.search(r"including that[,;.\s]", text):
                reasons.append("ambiguous pronoun 'including that' — should spell out noun (e.g. 'including ERT')")

            # "suspicious pathogenic" — should be "suspected pathogenic variant"
            if re.search(r"\bsuspicious\b", text, re.I):
                reasons.append("'suspicious' should be 'suspected' in medical English")

            if reasons:
                block.needs_manual_review = True
                block.review_reason = "; ".join(reasons)
                flagged += 1

        return flagged

    def translate_to_result(self, formatted: FormattedDocument) -> TranslationResult:
        blocks = formatted.original_blocks or []
        terminology_map, _structure_plan, _draft, translated, source_segments, translated_parts, warnings = (
            self.run_pipeline(formatted, blocks=blocks if blocks else None)
        )
        tr_segments: list[TranslationSegment] = []
        # Compute translated segment offsets by tracking cumulative position
        translated_offset = 0
        for idx, src_seg in enumerate(source_segments):
            src_bbox = None
            for sent in formatted.sentences:
                if sent.text.strip() in src_seg.strip() or src_seg.strip() in sent.text:
                    src_bbox = sent
                    break
            tr_text = translated_parts[idx] if idx < len(translated_parts) else ""
            tr_segments.append(TranslationSegment(
                index=idx, source_text=src_seg,
                translated_text=tr_text,
                source_bbox=src_bbox,
            ))
            translated_offset += len(tr_text) + 2  # +2 for "\n\n" joiner

        # Translate auxiliary fields (captions, footnotes) for non-text blocks
        aux_translations = self._translate_auxiliary_blocks(blocks)

        # Build translated blocks: split translated text on block delimiter
        translated_blocks = self._build_translated_blocks(
            blocks, tr_segments, translated,
            text_block_indices=getattr(self, '_text_block_indices', None),
            aux_translations=aux_translations,
        )

        # Flag blocks with quality issues for manual review
        flagged = self._flag_quality_issues(translated_blocks)
        if flagged:
            warnings.append(f"manual_review: {flagged} blocks flagged for review")
            logger.info("Flagged {} blocks for manual review", flagged)

        return TranslationResult(
            formatted_original=formatted.formatted_markdown,
            translated_english=translated,
            source_language=formatted.source_language or "unknown",
            terminology_map=terminology_map, translation_warnings=warnings,
            sentences=formatted.sentences, segments=tr_segments,
            original_blocks=blocks,
            translated_blocks=translated_blocks,
        )

    @staticmethod
    def compute_translation_drift(
        source_segments: List[str],
        translated_parts: List[str],
    ) -> List[SegmentDrift]:
        """Compute character drift between source and translated segments.

        For each segment pair, tracks the offset positions and length changes.
        """
        drifts: list[SegmentDrift] = []
        source_offset = 0
        translated_offset = 0

        for idx in range(max(len(source_segments), len(translated_parts))):
            src = source_segments[idx] if idx < len(source_segments) else ""
            tr = translated_parts[idx] if idx < len(translated_parts) else ""
            src_len = len(src)
            tr_len = len(tr)
            length_drift = tr_len - src_len

            drifts.append(
                SegmentDrift(
                    segment_index=idx,
                    source_start=source_offset,
                    source_end=source_offset + src_len,
                    translated_start=translated_offset,
                    translated_end=translated_offset + tr_len,
                    source_length=src_len,
                    translated_length=tr_len,
                    length_drift=length_drift,
                    source_text=src[:200],  # Truncate for JSON readability
                    translated_text=tr[:200],
                )
            )
            source_offset += src_len + 2  # +2 for "\n\n" joiner
            translated_offset += tr_len + 2

        return drifts
