from __future__ import annotations

from bisect import bisect_right
import re
from typing import Any, Dict, List, Optional, Tuple


def _build_line_starts(text: str) -> List[int]:
    starts = [0]
    offset = 0
    for line in text.splitlines(keepends=True):
        offset += len(line)
        starts.append(offset)
    return starts


def _offset_to_line(line_starts: List[int], offset: int) -> int:
    if offset <= 0:
        return 1
    idx = bisect_right(line_starts, offset) - 1
    return max(1, idx + 1)


def _extract_tex_wrapped(text: str) -> List[str]:
    return re.findall(r"\$[^$]+\$", text)


def _normalize_keyword(keyword: str) -> str:
    if not keyword:
        return keyword
    normalized = keyword.replace("\\%", "%")
    normalized = normalized.replace("±", "+-")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _candidate_quotes(quote: str) -> List[str]:
    if not quote:
        return []
    candidates = [quote]
    if "\\%" not in quote and "%" in quote:
        candidates.append(quote.replace("%", "\\%"))
    if "\\%" in quote:
        candidates.append(quote.replace("\\%", "%"))
    if "±" in quote:
        candidates.append(quote.replace("±", "+-"))
    if "+-" in quote:
        candidates.append(quote.replace("+-", "±"))
    return list(dict.fromkeys(candidates))


def _find_quote_offsets(text: str, quote: str) -> Optional[Tuple[int, int]]:
    for candidate in _candidate_quotes(quote):
        start = text.find(candidate)
        if start != -1:
            return start, start + len(candidate)
    return None


def _find_first_keyword_offsets(text: str, keywords: List[str]) -> Optional[Tuple[int, int]]:
    for keyword in keywords:
        if not keyword:
            continue
        start = text.find(keyword)
        if start != -1:
            return start, start + len(keyword)
    return None


def _extract_image_links(text: str) -> List[Dict[str, Any]]:
    lines = text.splitlines()
    image_entries: List[Dict[str, Any]] = []
    fig_pattern = re.compile(r"^\s*Fig\.\s*(\d+)")
    image_pattern = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")

    for idx, line in enumerate(lines, start=1):
        fig_match = fig_pattern.search(line)
        if not fig_match:
            continue
        fig_num = fig_match.group(1)
        image_path = None
        image_line = idx
        for look_ahead in (0, 1, 2):
            candidate_line = lines[idx - 1 + look_ahead] if idx - 1 + look_ahead < len(lines) else ""
            image_match = image_pattern.search(candidate_line)
            if image_match:
                image_path = image_match.group(1)
                image_line = idx + look_ahead
                break
        image_entries.append({
            "id": f"fig{fig_num}",
            "label": f"Fig. {fig_num}",
            "path": image_path,
            "nearest_md_lines": {
                "file": "en_format.md",
                "line_start": idx,
                "line_end": image_line,
            },
        })

    if not image_entries:
        for idx, line in enumerate(lines, start=1):
            image_match = image_pattern.search(line)
            if image_match:
                image_entries.append({
                    "id": f"img{len(image_entries) + 1}",
                    "label": f"Image {len(image_entries) + 1}",
                    "path": image_match.group(1),
                    "nearest_md_lines": {
                        "file": "en_format.md",
                        "line_start": idx,
                        "line_end": idx,
                    },
                })

    return image_entries


def enrich_evidence_json(evidence_json: Dict[str, Any], en_md_text: str) -> Dict[str, Any]:
    if not isinstance(evidence_json, dict):
        return evidence_json

    evidence_json.setdefault("annotation_schema_version", "1.0")
    source_documents = evidence_json.setdefault("source_documents", {})
    source_documents.setdefault("en_md", {"path": "en_format.md"})
    source_documents.setdefault("image_descriptions", {"path": "image_descriptions.txt"})

    images = source_documents.get("images")
    if not isinstance(images, list) or not images:
        images = _extract_image_links(en_md_text)
        source_documents["images"] = images

    image_map = {img.get("id"): img for img in images if isinstance(img, dict)}
    line_starts = _build_line_starts(en_md_text)

    annotations = evidence_json.setdefault("evidence_annotations", [])
    if isinstance(annotations, list):
        for annotation in annotations:
            if not isinstance(annotation, dict):
                continue
            annotation.setdefault("type", "text")
            annotation.setdefault("purpose", "")

            keywords = annotation.get("keywords")
            if not isinstance(keywords, dict):
                keywords = {"raw": [], "normalized": [], "tex_wrapped": []}
            raw_keywords = keywords.get("raw") if isinstance(keywords.get("raw"), list) else []
            normalized_keywords = [_normalize_keyword(k) for k in raw_keywords]
            tex_wrapped = keywords.get("tex_wrapped") if isinstance(keywords.get("tex_wrapped"), list) else []
            if not tex_wrapped and isinstance(annotation.get("quote"), str):
                tex_wrapped = _extract_tex_wrapped(annotation.get("quote", ""))
            keywords["raw"] = raw_keywords
            keywords["normalized"] = normalized_keywords
            keywords["tex_wrapped"] = tex_wrapped
            annotation["keywords"] = keywords

            locator = annotation.get("locator")
            if not isinstance(locator, dict):
                locator = {}
            locator.setdefault("file", "en_format.md")

            if annotation.get("type") == "image" and annotation.get("image_ref"):
                image_entry = image_map.get(annotation.get("image_ref"))
                if image_entry and isinstance(image_entry.get("nearest_md_lines"), dict):
                    nearest = image_entry["nearest_md_lines"]
                    locator["line_start"] = nearest.get("line_start")
                    locator["line_end"] = nearest.get("line_end")
                locator.setdefault("char_start", None)
                locator.setdefault("char_end", None)
                annotation["locator"] = locator
                continue

            quote = annotation.get("quote") if isinstance(annotation.get("quote"), str) else ""
            offsets = _find_quote_offsets(en_md_text, quote) if quote else None
            if offsets is None and normalized_keywords:
                offsets = _find_first_keyword_offsets(en_md_text, normalized_keywords)

            if offsets:
                start, end = offsets
                locator["char_start"] = start
                locator["char_end"] = end
                locator["line_start"] = _offset_to_line(line_starts, start)
                locator["line_end"] = _offset_to_line(line_starts, max(end - 1, start))
            else:
                locator.setdefault("char_start", None)
                locator.setdefault("char_end", None)
                locator.setdefault("line_start", None)
                locator.setdefault("line_end", None)

            annotation["locator"] = locator

    return evidence_json
