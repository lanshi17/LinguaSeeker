from __future__ import annotations

from bisect import bisect_right
import re
from typing import Any, Dict, List, Optional, Tuple


_ENTITY_PRIORITY: Dict[str, int] = {
    "variant": 5,
    "protein": 4,
    "gene": 3,
    "disease": 2,
    "transcript": 2,
    "experiment": 1,
}

_ENTITY_PATHS: Tuple[Tuple[str, str], ...] = (
    ("gene", "gene.symbol"),
    ("gene", "gene.full_name"),
    ("variant", "variant.hgvs_c"),
    ("variant", "variant.hgvs_g"),
    ("protein", "variant.hgvs_p"),
    ("disease", "disease_chpo.disease_name"),
    ("disease", "disease_icd10.disease_name"),
    ("transcript", "transcript_id.transcript_id"),
    ("experiment", "experiment_data.assay_type"),
)


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


def _find_quote_offsets_case_insensitive(text: str, quote: str) -> Optional[Tuple[int, int]]:
    lowered_text = text.lower()
    for candidate in _candidate_quotes(quote):
        lowered_candidate = candidate.lower()
        if not lowered_candidate:
            continue
        start = lowered_text.find(lowered_candidate)
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


def _find_first_keyword_offsets_case_insensitive(
    text: str,
    keywords: List[str],
) -> Optional[Tuple[int, int]]:
    lowered_text = text.lower()
    for keyword in keywords:
        if not keyword:
            continue
        lowered_keyword = keyword.lower()
        start = lowered_text.find(lowered_keyword)
        if start != -1:
            return start, start + len(keyword)
    return None


def _build_empty_locator() -> Dict[str, Optional[int]]:
    return {
        "start": None,
        "end": None,
        "char_start": None,
        "char_end": None,
        "line_start": None,
        "line_end": None,
    }


def _build_locator(
    line_starts: List[int],
    start: int,
    end: int,
) -> Dict[str, Optional[int]]:
    return {
        "start": start,
        "end": end,
        "char_start": start,
        "char_end": end,
        "line_start": _offset_to_line(line_starts, start),
        "line_end": _offset_to_line(line_starts, max(end - 1, start)),
    }


def _normalize_locator(locator: Any) -> Dict[str, Optional[int]]:
    if not isinstance(locator, dict):
        return _build_empty_locator()

    start = locator.get("start")
    end = locator.get("end")
    char_start = locator.get("char_start")
    char_end = locator.get("char_end")

    if start is None and isinstance(char_start, int):
        start = char_start
    if end is None and isinstance(char_end, int):
        end = char_end

    if char_start is None and isinstance(start, int):
        char_start = start
    if char_end is None and isinstance(end, int):
        char_end = end

    return {
        "start": start if isinstance(start, int) else None,
        "end": end if isinstance(end, int) else None,
        "char_start": char_start if isinstance(char_start, int) else None,
        "char_end": char_end if isinstance(char_end, int) else None,
        "line_start": locator.get("line_start")
        if isinstance(locator.get("line_start"), int)
        else None,
        "line_end": locator.get("line_end") if isinstance(locator.get("line_end"), int) else None,
    }


def _read_nested(payload: Dict[str, Any], path: str) -> Any:
    current: Any = payload
    for segment in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(segment)
    return current


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
            candidate_index = idx - 1 + look_ahead
            candidate_line = lines[candidate_index] if candidate_index < len(lines) else ""
            image_match = image_pattern.search(candidate_line)
            if image_match:
                image_path = image_match.group(1)
                image_line = idx + look_ahead
                break
        image_entries.append(
            {
                "id": f"fig{fig_num}",
                "label": f"Fig. {fig_num}",
                "path": image_path,
                "nearest_md_lines": {
                    "file": "en_format.md",
                    "line_start": idx,
                    "line_end": image_line,
                },
            }
        )

    if not image_entries:
        for idx, line in enumerate(lines, start=1):
            image_match = image_pattern.search(line)
            if image_match:
                image_entries.append(
                    {
                        "id": f"img{len(image_entries) + 1}",
                        "label": f"Image {len(image_entries) + 1}",
                        "path": image_match.group(1),
                        "nearest_md_lines": {
                            "file": "en_format.md",
                            "line_start": idx,
                            "line_end": idx,
                        },
                    }
                )

    return image_entries


def _locate_offsets(
    en_md_text: str,
    text_value: str,
    keywords: Optional[List[str]] = None,
) -> Optional[Tuple[int, int]]:
    offsets = _find_quote_offsets(en_md_text, text_value)
    if offsets is None:
        offsets = _find_quote_offsets_case_insensitive(en_md_text, text_value)

    normalized_text = _normalize_keyword(text_value)
    if offsets is None and normalized_text and normalized_text != text_value:
        offsets = _find_quote_offsets(en_md_text, normalized_text)
    if offsets is None and normalized_text and normalized_text != text_value:
        offsets = _find_quote_offsets_case_insensitive(en_md_text, normalized_text)

    keyword_candidates = [
        value for value in (keywords or []) if isinstance(value, str) and value.strip()
    ]
    if offsets is None and keyword_candidates:
        offsets = _find_first_keyword_offsets(en_md_text, keyword_candidates)
    if offsets is None and keyword_candidates:
        offsets = _find_first_keyword_offsets_case_insensitive(en_md_text, keyword_candidates)
    return offsets


def _build_annotation_index(annotations: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for annotation in annotations:
        if not isinstance(annotation, dict):
            continue
        annotation_id = annotation.get("id")
        if isinstance(annotation_id, str) and annotation_id.strip():
            result[annotation_id.strip()] = annotation
    return result


def _locate_with_evidence_ref(
    en_md_text: str,
    text_value: str,
    evidence_ref: Optional[str],
    annotation_index: Dict[str, Dict[str, Any]],
) -> Optional[Tuple[int, int]]:
    if not isinstance(evidence_ref, str) or not evidence_ref.strip():
        return None
    annotation = annotation_index.get(evidence_ref.strip())
    if not isinstance(annotation, dict):
        return None

    quote = annotation.get("quote")
    locator = _normalize_locator(annotation.get("locator"))
    base_start = locator.get("char_start")
    if not isinstance(quote, str) or not quote or not isinstance(base_start, int):
        return None

    inner_offsets = _locate_offsets(quote, text_value, [_normalize_keyword(text_value)])
    if inner_offsets is None:
        return None
    inner_start, inner_end = inner_offsets

    absolute_start = base_start + inner_start
    absolute_end = base_start + inner_end
    if absolute_start < 0 or absolute_end > len(en_md_text):
        return None
    return absolute_start, absolute_end


def _span_from_locator(locator: Dict[str, Optional[int]]) -> Optional[Tuple[int, int]]:
    start = locator.get("start")
    end = locator.get("end")
    if isinstance(start, int) and isinstance(end, int):
        return start, end
    return None


def _spans_overlap(left: Tuple[int, int], right: Tuple[int, int]) -> bool:
    return max(left[0], right[0]) < min(left[1], right[1])


def _entity_rank(entity: Dict[str, Any]) -> Tuple[int, int]:
    locator = _normalize_locator(entity.get("locator"))
    span = _span_from_locator(locator)
    span_length = (span[1] - span[0]) if span else 0
    entity_type = entity.get("type")
    priority = _ENTITY_PRIORITY.get(str(entity_type), 0)
    return span_length, priority


def _resolve_entity_overlaps(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    located: List[Dict[str, Any]] = []
    unresolved: List[Dict[str, Any]] = []

    for entity in entities:
        locator = _normalize_locator(entity.get("locator"))
        span = _span_from_locator(locator)
        copied = dict(entity)
        copied["locator"] = locator
        if span is None:
            unresolved.append(copied)
        else:
            located.append(copied)

    located.sort(
        key=lambda item: (
            item["locator"]["start"] if isinstance(item["locator"]["start"], int) else 10**12,
            -_entity_rank(item)[0],
            -_entity_rank(item)[1],
            str(item.get("text", "")),
        )
    )

    kept: List[Dict[str, Any]] = []
    for candidate in located:
        candidate_span = _span_from_locator(candidate["locator"])
        if candidate_span is None:
            unresolved.append(candidate)
            continue

        overlapping_indexes = [
            index
            for index, current in enumerate(kept)
            if (_span_from_locator(current["locator"]) is not None)
            and _spans_overlap(
                candidate_span, _span_from_locator(current["locator"]) or candidate_span
            )
        ]

        if not overlapping_indexes:
            kept.append(candidate)
            continue

        if all(
            _entity_rank(candidate) > _entity_rank(kept[index]) for index in overlapping_indexes
        ):
            for index in sorted(overlapping_indexes, reverse=True):
                kept.pop(index)
            kept.append(candidate)

    kept.sort(
        key=lambda item: (
            item["locator"]["start"] if isinstance(item["locator"]["start"], int) else 10**12,
            str(item.get("id", "")),
        )
    )
    unresolved.sort(key=lambda item: str(item.get("id", "")))
    return kept + unresolved


def _merge_locators(
    left: Dict[str, Optional[int]],
    right: Dict[str, Optional[int]],
    line_starts: List[int],
) -> Dict[str, Optional[int]]:
    left_norm = _normalize_locator(left)
    right_norm = _normalize_locator(right)
    left_span = _span_from_locator(left_norm)
    right_span = _span_from_locator(right_norm)

    if left_span is None:
        return right_norm
    if right_span is None:
        return left_norm

    start = min(left_span[0], right_span[0])
    end = max(left_span[1], right_span[1])
    return _build_locator(line_starts, start, end)


def _enrich_entity_extractions(
    entity_extractions: List[Dict[str, Any]],
    en_md_text: str,
    line_starts: List[int],
    annotation_index: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    for index, entity in enumerate(entity_extractions, start=1):
        if not isinstance(entity, dict):
            continue

        item = dict(entity)
        item.setdefault("id", f"ENT{index}")
        if "type" not in item and isinstance(item.get("entity_type"), str):
            item["type"] = item.get("entity_type")

        text_value = item.get("text")
        if not isinstance(text_value, str) or not text_value.strip():
            item["locator"] = _normalize_locator(item.get("locator"))
            enriched.append(item)
            continue

        evidence_ref = item.get("evidence_ref")
        offsets = _locate_with_evidence_ref(en_md_text, text_value, evidence_ref, annotation_index)
        if offsets is None:
            offsets = _locate_offsets(en_md_text, text_value, [_normalize_keyword(text_value)])

        if offsets:
            item["locator"] = _build_locator(line_starts, offsets[0], offsets[1])
        else:
            item["locator"] = _build_empty_locator()
        enriched.append(item)

    resolved = _resolve_entity_overlaps(enriched)
    for index, entity in enumerate(resolved, start=1):
        entity["id"] = f"ENT{index}"
    return resolved


def _build_entities_from_extracted_fields(
    extracted_fields: Dict[str, Any],
    en_md_text: str,
    line_starts: List[int],
) -> List[Dict[str, Any]]:
    entities: List[Dict[str, Any]] = []
    seen_keys: set[Tuple[str, str, Optional[int], Optional[int]]] = set()

    for entity_type, field_path in _ENTITY_PATHS:
        value = _read_nested(extracted_fields, field_path)
        if not isinstance(value, str) or not value.strip():
            continue

        text_value = value.strip()
        offsets = _locate_offsets(en_md_text, text_value, [_normalize_keyword(text_value)])
        locator = (
            _build_locator(line_starts, offsets[0], offsets[1])
            if offsets
            else _build_empty_locator()
        )

        key = (
            entity_type,
            text_value,
            locator.get("start"),
            locator.get("end"),
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)

        entities.append(
            {
                "id": "",
                "type": entity_type,
                "text": text_value,
                "source_path": f"extracted_fields.{field_path}",
                "locator": locator,
            }
        )

    resolved = _resolve_entity_overlaps(entities)
    for index, entity in enumerate(resolved, start=1):
        entity["id"] = f"ENT{index}"
    return resolved


def _build_relations_from_entities(
    entities: List[Dict[str, Any]],
    line_starts: List[int],
) -> List[Dict[str, Any]]:
    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for entity in entities:
        entity_type = entity.get("type")
        if isinstance(entity_type, str):
            by_type.setdefault(entity_type, []).append(entity)

    def _first(type_name: str) -> Optional[Dict[str, Any]]:
        values = by_type.get(type_name) or []
        return values[0] if values else None

    gene = _first("gene")
    variant = _first("variant")
    disease = _first("disease")

    relations: List[Dict[str, Any]] = []
    relation_specs: List[Tuple[str, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]] = [
        ("gene_variant", gene, variant),
        ("variant_disease", variant, disease),
        ("gene_disease", gene, disease),
    ]

    for relation_type, source, target in relation_specs:
        if not source or not target:
            continue
        locator = _merge_locators(
            _normalize_locator(source.get("locator")),
            _normalize_locator(target.get("locator")),
            line_starts,
        )
        relations.append(
            {
                "id": "",
                "type": relation_type,
                "source_entity_id": source.get("id"),
                "target_entity_id": target.get("id"),
                "arguments": [
                    {
                        "entity_id": source.get("id"),
                        "type": source.get("type"),
                        "text": source.get("text"),
                        "locator": _normalize_locator(source.get("locator")),
                    },
                    {
                        "entity_id": target.get("id"),
                        "type": target.get("type"),
                        "text": target.get("text"),
                        "locator": _normalize_locator(target.get("locator")),
                    },
                ],
                "locator": locator,
            }
        )

    for index, relation in enumerate(relations, start=1):
        relation["id"] = f"REL{index}"
    return relations


def _enrich_relation_extractions(
    relation_extractions: List[Dict[str, Any]],
    entities: List[Dict[str, Any]],
    en_md_text: str,
    line_starts: List[int],
    annotation_index: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    entity_lookup: Dict[str, Dict[str, Any]] = {}
    for entity in entities:
        entity_id = entity.get("id")
        if isinstance(entity_id, str):
            entity_lookup[entity_id] = entity

    enriched_relations: List[Dict[str, Any]] = []
    for index, relation in enumerate(relation_extractions, start=1):
        if not isinstance(relation, dict):
            continue

        item = dict(relation)
        item.setdefault("id", f"REL{index}")
        merged_locator = _normalize_locator(item.get("locator"))

        relation_text = item.get("text")
        if isinstance(relation_text, str) and relation_text.strip():
            offsets = _locate_with_evidence_ref(
                en_md_text,
                relation_text,
                item.get("evidence_ref") if isinstance(item.get("evidence_ref"), str) else None,
                annotation_index,
            )
            if offsets is None:
                offsets = _locate_offsets(
                    en_md_text, relation_text, [_normalize_keyword(relation_text)]
                )
            if offsets:
                merged_locator = _merge_locators(
                    merged_locator,
                    _build_locator(line_starts, offsets[0], offsets[1]),
                    line_starts,
                )

        arguments = item.get("arguments")
        if isinstance(arguments, list):
            normalized_arguments: List[Dict[str, Any]] = []
            for argument in arguments:
                if not isinstance(argument, dict):
                    continue
                enriched_argument = dict(argument)
                text_value = enriched_argument.get("text")
                evidence_ref = (
                    enriched_argument.get("evidence_ref")
                    if isinstance(enriched_argument.get("evidence_ref"), str)
                    else item.get("evidence_ref")
                )
                locator = _normalize_locator(enriched_argument.get("locator"))
                if isinstance(text_value, str) and text_value.strip():
                    offsets = _locate_with_evidence_ref(
                        en_md_text,
                        text_value,
                        evidence_ref if isinstance(evidence_ref, str) else None,
                        annotation_index,
                    )
                    if offsets is None:
                        offsets = _locate_offsets(
                            en_md_text, text_value, [_normalize_keyword(text_value)]
                        )
                    if offsets:
                        locator = _build_locator(line_starts, offsets[0], offsets[1])
                enriched_argument["locator"] = locator
                merged_locator = _merge_locators(merged_locator, locator, line_starts)
                normalized_arguments.append(enriched_argument)
            item["arguments"] = normalized_arguments

        for endpoint_key in ("source_entity_id", "target_entity_id"):
            endpoint_id = item.get(endpoint_key)
            if isinstance(endpoint_id, str) and endpoint_id in entity_lookup:
                merged_locator = _merge_locators(
                    merged_locator,
                    _normalize_locator(entity_lookup[endpoint_id].get("locator")),
                    line_starts,
                )

        item["locator"] = merged_locator
        enriched_relations.append(item)

    for index, relation in enumerate(enriched_relations, start=1):
        relation["id"] = f"REL{index}"
    return enriched_relations


def _build_experiment_info_from_extracted_fields(
    extracted_fields: Dict[str, Any],
    evidence_json: Dict[str, Any],
    en_md_text: str,
    line_starts: List[int],
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    experiment_data = extracted_fields.get("experiment_data")
    if not isinstance(experiment_data, dict):
        experiment_data = {}

    candidates: List[Tuple[str, str, str]] = []
    assay_type = experiment_data.get("assay_type")
    if isinstance(assay_type, str) and assay_type.strip():
        candidates.append(
            ("method", assay_type.strip(), "extracted_fields.experiment_data.assay_type")
        )

    method_description = experiment_data.get("method_description")
    if isinstance(method_description, str) and method_description.strip():
        candidates.append(
            (
                "method",
                method_description.strip(),
                "extracted_fields.experiment_data.method_description",
            )
        )

    key_findings = experiment_data.get("key_findings")
    if isinstance(key_findings, list):
        for finding in key_findings:
            if isinstance(finding, str) and finding.strip():
                candidates.append(
                    ("result", finding.strip(), "extracted_fields.experiment_data.key_findings")
                )

    overall = evidence_json.get("overall_assessment")
    if isinstance(overall, dict):
        recommendation = overall.get("final_recommendation")
        if isinstance(recommendation, str) and recommendation.strip():
            candidates.append(
                ("conclusion", recommendation.strip(), "overall_assessment.final_recommendation")
            )

    step4 = evidence_json.get("ps3_step_4")
    if isinstance(step4, dict):
        final_strength = step4.get("final_evidence_strength")
        if isinstance(final_strength, str) and final_strength.strip():
            candidates.append(
                ("conclusion", final_strength.strip(), "ps3_step_4.final_evidence_strength")
            )

    for index, (category, text_value, source_path) in enumerate(candidates, start=1):
        offsets = _locate_offsets(en_md_text, text_value, [_normalize_keyword(text_value)])
        locator = (
            _build_locator(line_starts, offsets[0], offsets[1])
            if offsets
            else _build_empty_locator()
        )
        items.append(
            {
                "id": f"EXP{index}",
                "category": category,
                "text": text_value,
                "source_path": source_path,
                "locator": locator,
            }
        )
    return items


def _enrich_experiment_info_extractions(
    experiment_info_extractions: List[Dict[str, Any]],
    en_md_text: str,
    line_starts: List[int],
    annotation_index: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    def _enrich_part(
        part: Dict[str, Any],
        inherited_ref: Optional[str] = None,
    ) -> Dict[str, Any]:
        text_value = part.get("text")
        locator = _normalize_locator(part.get("locator"))
        evidence_ref = (
            part.get("evidence_ref") if isinstance(part.get("evidence_ref"), str) else inherited_ref
        )
        if isinstance(text_value, str) and text_value.strip():
            offsets = _locate_with_evidence_ref(
                en_md_text,
                text_value,
                evidence_ref,
                annotation_index,
            )
            if offsets is None:
                offsets = _locate_offsets(en_md_text, text_value, [_normalize_keyword(text_value)])
            if offsets:
                locator = _build_locator(line_starts, offsets[0], offsets[1])
        part["locator"] = locator
        return part

    enriched_items: List[Dict[str, Any]] = []
    for index, entry in enumerate(experiment_info_extractions, start=1):
        if not isinstance(entry, dict):
            continue

        item = dict(entry)
        item.setdefault("id", f"EXP{index}")
        inherited_ref = (
            item.get("evidence_ref") if isinstance(item.get("evidence_ref"), str) else None
        )

        merged_locator = _normalize_locator(item.get("locator"))
        if isinstance(item.get("text"), str) and item.get("text", "").strip():
            item = _enrich_part(item, inherited_ref=inherited_ref)
            merged_locator = _merge_locators(
                merged_locator, _normalize_locator(item.get("locator")), line_starts
            )

        for key in ("method", "results", "conclusion"):
            part = item.get(key)
            if isinstance(part, dict):
                enriched_part = _enrich_part(dict(part), inherited_ref=inherited_ref)
                item[key] = enriched_part
                merged_locator = _merge_locators(
                    merged_locator,
                    _normalize_locator(enriched_part.get("locator")),
                    line_starts,
                )
            elif isinstance(part, list):
                normalized_parts: List[Dict[str, Any]] = []
                for child in part:
                    if isinstance(child, str):
                        child_payload: Dict[str, Any] = {"text": child}
                    elif isinstance(child, dict):
                        child_payload = dict(child)
                    else:
                        continue
                    enriched_child = _enrich_part(child_payload, inherited_ref=inherited_ref)
                    normalized_parts.append(enriched_child)
                    merged_locator = _merge_locators(
                        merged_locator,
                        _normalize_locator(enriched_child.get("locator")),
                        line_starts,
                    )
                item[key] = normalized_parts

        item["locator"] = merged_locator
        enriched_items.append(item)

    for index, item in enumerate(enriched_items, start=1):
        item["id"] = f"EXP{index}"
    return enriched_items


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

            keywords_value = annotation.get("keywords")
            raw_keywords: List[str] = []
            if isinstance(keywords_value, dict):
                raw_values = keywords_value.get("raw")
                if isinstance(raw_values, list):
                    for keyword in raw_values:
                        if isinstance(keyword, str):
                            raw_keywords.append(keyword)

            normalized_keywords = [_normalize_keyword(keyword) for keyword in raw_keywords]

            tex_wrapped: List[str] = []
            if isinstance(keywords_value, dict):
                tex_values = keywords_value.get("tex_wrapped")
                if isinstance(tex_values, list):
                    for item in tex_values:
                        if isinstance(item, str):
                            tex_wrapped.append(item)

            if not tex_wrapped and isinstance(annotation.get("quote"), str):
                tex_wrapped = _extract_tex_wrapped(annotation.get("quote", ""))

            keywords_payload: Dict[str, Any] = {
                "raw": raw_keywords,
                "normalized": normalized_keywords,
                "tex_wrapped": tex_wrapped,
            }
            annotation["keywords"] = keywords_payload

            locator = _normalize_locator(annotation.get("locator"))

            if annotation.get("type") == "image" and annotation.get("image_ref"):
                image_entry = image_map.get(annotation.get("image_ref"))
                if image_entry and isinstance(image_entry.get("nearest_md_lines"), dict):
                    nearest = image_entry["nearest_md_lines"]
                    locator["line_start"] = nearest.get("line_start")
                    locator["line_end"] = nearest.get("line_end")
                annotation["locator"] = locator
                continue

            quote = annotation.get("quote") if isinstance(annotation.get("quote"), str) else ""
            offsets = _locate_offsets(en_md_text, quote, normalized_keywords) if quote else None

            if offsets:
                annotation["locator"] = _build_locator(line_starts, offsets[0], offsets[1])
            else:
                annotation["locator"] = locator

    if not isinstance(annotations, list):
        annotations = []

    annotation_index = _build_annotation_index(
        [item for item in annotations if isinstance(item, dict)]
    )

    extracted_fields = evidence_json.get("extracted_fields")
    if not isinstance(extracted_fields, dict):
        extracted_fields = {}

    entity_extractions = evidence_json.get("entity_extractions")
    if isinstance(entity_extractions, list):
        entities = _enrich_entity_extractions(
            [item for item in entity_extractions if isinstance(item, dict)],
            en_md_text,
            line_starts,
            annotation_index,
        )
    else:
        entities = _build_entities_from_extracted_fields(extracted_fields, en_md_text, line_starts)
    evidence_json["entity_extractions"] = entities

    relation_extractions = evidence_json.get("relation_extractions")
    if isinstance(relation_extractions, list):
        relations = _enrich_relation_extractions(
            [item for item in relation_extractions if isinstance(item, dict)],
            entities,
            en_md_text,
            line_starts,
            annotation_index,
        )
    else:
        relations = _build_relations_from_entities(entities, line_starts)
    evidence_json["relation_extractions"] = relations

    experiment_info_extractions = evidence_json.get("experiment_info_extractions")
    if isinstance(experiment_info_extractions, list):
        experiments = _enrich_experiment_info_extractions(
            [item for item in experiment_info_extractions if isinstance(item, dict)],
            en_md_text,
            line_starts,
            annotation_index,
        )
    else:
        experiments = _build_experiment_info_from_extracted_fields(
            extracted_fields,
            evidence_json,
            en_md_text,
            line_starts,
        )
    evidence_json["experiment_info_extractions"] = experiments

    return evidence_json
