"""Deterministic ACMG evidence value normalization."""

from __future__ import annotations

import re
import unicodedata

from src.core.standardize_entities_and_align_knowledge.hgvs_normalizer import (
    canonical_protein_hgvs,
    expand_hgvs_aliases,
)

from ..contracts import (
    EvidenceItem,
    EvidenceNormalizationIssue,
    EvidenceNormalizationIssueType,
    EvidenceNormalizationSeverity,
    EvidenceStatus,
)

_COORDINATE_ONLY_RE = re.compile(r"^(?:chr)?[0-9XYM]+[_:][0-9]+$", re.IGNORECASE)
_HGVS_G_RE = re.compile(
    r"^[A-Z]{1,3}_[0-9]+(?:\.[0-9]+)?:g\."
    r"(?:"
    r"[0-9]+[ACGT]>[ACGT]|"
    r"[0-9]+(?:_[0-9]+)?del(?:[ACGT]+)?|"
    r"[0-9]+(?:_[0-9]+)?ins[ACGT]+|"
    r"[0-9]+(?:_[0-9]+)?dup(?:[ACGT]+)?|"
    r"[0-9]+_[0-9]+inv"
    r")$"
)
_VALUE_KEY_UNSET = object()
# Canonical three-letter stop gain, e.g. `p.Ser65Ter`, whose group is a coding indel.
_PROTEIN_STOP_CANONICAL_RE = re.compile(r"^(p\.[A-Z][a-z]{2}\d+)Ter$")


class AcmgEvidenceValueNormalizer:
    """Normalize extracted values before catalog backfill and quality gates."""

    _DE_NOVO_TRUE_VALUES = frozenset(
        {
            "1",
            "true",
            "de novo",
            "denovo",
            "assumed de novo",
            "assumed denovo",
            "pm6 eligible",
        }
    )
    # Longer phrases used as substrings so "assumed de novo (PM6-eligible)" still canonicalizes.
    _DE_NOVO_TRUE_PHRASES = (
        "assumed de novo",
        "assumed denovo",
        "pm6 eligible",
        "de novo",
        "denovo",
    )
    _GENE_SYMBOL_FIELDS = {
        "A.gene_symbol",
        "A.gene_aliases",
    }
    _HGVS_OR_REFERENCE_FIELDS = {
        "A.variant_hgvs_g",
        "A.reference_sequence",
        "A.variant_legacy_name",
    }

    _MILESTONE_PATTERNS = (
        r"\bstarted sitting\b",
        r"\bsitting with support\b",
        r"\bstarted walking\b",
        r"\bdelayed walking\b",
        r"\bstarted speaking\b",
        r"\bdevelopmental milestone\b",
    )
    _ONSET_TERMS = ("onset", "presented", "presentation", "diagnosed", "referred", "symptom")
    _GENERIC_PREDICTION_VALUES = {
        "in silico tools",
        "bioinformatics tools",
        "prediction tools",
        "computational tools",
    }
    _HGVS_ALIAS_FIELDS = frozenset({"A.variant_hgvs_c", "A.variant_hgvs_p"})
    _ACMG_CRITERION_TOKEN_RE = re.compile(
        r"\b(?:PVS1|PS[1-4]|PM[1-6]|PP[1-5]|BA1|BS[1-4]|BP[1-7])\b",
        re.IGNORECASE,
    )
    _INHERITED_VARIANT_RE = re.compile(
        r"maternally inherited|paternally inherited|"
        r"inherited from (?:the )?(?:mother|father|maternal|paternal)|"
        r"maternal inheritance|paternal inheritance|"
        r"遗传自母|遗传自父|母系遗传|父系遗传|来自母亲|来自父亲",
        re.IGNORECASE,
    )
    _PARENTAGE_CONFIRMED_RE = re.compile(
        r"parentage confirm|maternity.{0,40}paternity|paternity.{0,40}maternity|"
        r"identity testing|\bSTR(?:s)?\b|亲子鉴定|亲权",
        re.IGNORECASE,
    )
    _UNCONFIRMED_PS2_NOTE_RE = re.compile(
        r"PS2-eligible|confirmed PS2|\bPS2\b|confirmed de novo",
        re.IGNORECASE,
    )

    _CODING_INDEL_RE = re.compile(r"c\.\d+(?:_\d+)?(?:del|ins)", re.IGNORECASE)
    _NONSENSE_TYPE_VALUES = frozenset({"nonsense", "无义", "无义突变"})

    def normalize(
        self,
        items: list[EvidenceItem],
    ) -> tuple[list[EvidenceItem], list[EvidenceNormalizationIssue]]:
        normalized: list[EvidenceItem] = []
        issues: list[EvidenceNormalizationIssue] = []
        for item in items:
            replacement, item_issues = self._normalize_one(item)
            normalized.append(replacement)
            issues.extend(item_issues)
        aligned, align_issues = self._align_consequence_to_coding_hgvs(normalized)
        issues.extend(align_issues)
        merged, merge_issues = self._merge_duplicates(aligned)
        issues.extend(merge_issues)
        return merged, issues

    @classmethod
    def has_coding_indel(cls, text: str) -> bool:
        """True when compact text contains a coding-region del/ins HGVS token."""
        compact = re.sub(r"\s+", "", (text or "").casefold()).replace("&gt;", ">")
        return cls._CODING_INDEL_RE.search(compact) is not None

    def _normalize_one(
        self,
        item: EvidenceItem,
    ) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        if item.status != EvidenceStatus.FOUND or item.value is None:
            return item, []
        item = self._strip_runtime_criterion_codes(item)
        value_text = str(item.value).strip()
        if item.field_id in self._HGVS_OR_REFERENCE_FIELDS and _COORDINATE_ONLY_RE.fullmatch(value_text):
            return (
                self._reject_item(item),
                [
                    EvidenceNormalizationIssue(
                        issue_type=EvidenceNormalizationIssueType.INVALID_HGVS,
                        severity=EvidenceNormalizationSeverity.ERROR,
                        field_id=item.field_id,
                        message="Coordinate-only value is not valid for this HGVS/reference field.",
                        original_value=item.value,
                    )
                ],
            )
        if item.field_id == "A.variant_hgvs_g" and value_text and not _HGVS_G_RE.fullmatch(value_text):
            return (
                self._reject_item(item),
                [
                    EvidenceNormalizationIssue(
                        issue_type=EvidenceNormalizationIssueType.INVALID_HGVS,
                        severity=EvidenceNormalizationSeverity.ERROR,
                        field_id=item.field_id,
                        message="HGVS genomic variant must include reference sequence, g. coordinate, and base change.",
                        original_value=item.value,
                    )
                ],
            )
        if item.field_id in self._GENE_SYMBOL_FIELDS:
            return self._normalize_gene_symbol(item)
        if item.field_id in self._HGVS_ALIAS_FIELDS:
            return self._normalize_hgvs_alias(item)
        if item.field_id == "C.de_novo_status":
            return self._normalize_de_novo(item)
        if item.field_id == "C.parentage_confirmed":
            return self._normalize_parentage_confirmed(item)
        if item.field_id == "A.variant_type":
            return self._normalize_variant_type(item)
        if item.field_id == "J.clinvar_assertion":
            return self._normalize_clinvar_assertion(item)
        if item.field_id == "B.consanguinity":
            return self._normalize_consanguinity(item)
        if item.field_id == "C.obligate_carriers":
            return self._normalize_obligate_carriers(item)
        if item.field_id == "B.age_of_onset":
            return self._normalize_age_of_onset(item)
        if item.field_id.startswith("F."):
            return self._reject_in_silico_functional(item)
        if item.field_id == "E.prediction_tools_list":
            return self._normalize_prediction_tools(item)
        return item, []

    def _with_value_issue(
        self,
        item: EvidenceItem,
        normalized_value: object,
    ) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        return (
            item.model_copy(update={"value": normalized_value}),
            [
                EvidenceNormalizationIssue(
                    issue_type=EvidenceNormalizationIssueType.VALUE_NORMALIZED,
                    severity=EvidenceNormalizationSeverity.INFO,
                    field_id=item.field_id,
                    message="Field value normalized to ACMG-ready representation.",
                    original_value=item.value,
                    normalized_value=normalized_value,
                )
            ],
        )

    def _strip_runtime_criterion_codes(self, item: EvidenceItem) -> EvidenceItem:
        """Drop catalog copies and author-claimed ACMG codes from extraction output."""
        if not item.assigned_acmg_codes and not item.assigned_clingen_modules:
            return item
        note = "criterion_claim:stripped_runtime_codes"
        notes = f"{item.notes}; {note}" if item.notes else note
        return item.model_copy(
            update={
                "assigned_acmg_codes": [],
                "assigned_clingen_modules": [],
                "notes": notes,
            }
        )

    def _source_text(self, item: EvidenceItem) -> str:
        """Join the extracted value with grounded snippets for deterministic checks."""
        parts = [str(item.value or "")]
        for location in (item.source, item.raw_source):
            if location is not None and location.text_snippet:
                parts.append(location.text_snippet)
        return " ".join(parts)

    def _normalize_de_novo(
        self,
        item: EvidenceItem,
    ) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        evidence_text = self._source_text(item)
        if self._INHERITED_VARIANT_RE.search(evidence_text):
            replaced, issues = self._with_value_issue(item, "not_de_novo")
            note = "criterion_claim:inherited_not_de_novo"
            notes = f"{replaced.notes}; {note}" if replaced.notes else note
            return replaced.model_copy(update={"notes": notes}), issues
        text = str(item.value).strip().lower()
        collapsed = re.sub(r"[\s_\-]+", " ", text).strip()
        if (
            item.value is False
            or text in {"0", "false", "not de novo", "not_de_novo", "inherited"}
            or "not de novo" in collapsed
        ):
            return self._with_value_issue(item, "not_de_novo")
        if text == "de_novo":
            return self._downgrade_unconfirmed_ps2(item), []
        if item.value is True or collapsed in self._DE_NOVO_TRUE_VALUES or any(
            phrase in collapsed for phrase in self._DE_NOVO_TRUE_PHRASES
        ):
            replaced, issues = self._with_value_issue(item, "de_novo")
            return self._downgrade_unconfirmed_ps2(replaced), issues
        if text in {"unknown", "not reported", "not_reported", "unknown_not_reported"}:
            return self._with_value_issue(item, "unknown_not_reported")
        return item, []

    def _downgrade_unconfirmed_ps2(self, item: EvidenceItem) -> EvidenceItem:
        """Keep assumed de novo, but strip PS2 upgrades when parentage was not confirmed."""
        notes = item.notes or ""
        if not self._UNCONFIRMED_PS2_NOTE_RE.search(notes):
            return item
        if self._PARENTAGE_CONFIRMED_RE.search(self._source_text(item)):
            return item
        rewritten = self._UNCONFIRMED_PS2_NOTE_RE.sub("PM6-eligible", notes)
        tag = "criterion_claim:unconfirmed_parentage_not_ps2"
        if tag not in rewritten:
            rewritten = f"{rewritten}; {tag}" if rewritten else tag
        return item.model_copy(update={"notes": rewritten})

    def _normalize_parentage_confirmed(
        self,
        item: EvidenceItem,
    ) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        """Parental negativity is not identity testing; only keep confirmed when the quote says so."""
        evidence_text = self._source_text(item)
        text = str(item.value).strip().lower()
        if self._PARENTAGE_CONFIRMED_RE.search(evidence_text) and text in {
            "true",
            "1",
            "confirmed",
            "yes",
            "parentage_confirmed",
        }:
            return self._with_value_issue(item, "confirmed")
        if text in {"false", "0", "absent", "not_confirmed", "unconfirmed", "no", "not confirmed"}:
            if item.value == "not_confirmed":
                return item, []
            return self._with_value_issue(item, "not_confirmed")
        if text in {"true", "1", "confirmed", "yes", "parentage_confirmed"}:
            return self._with_value_issue(item, "not_confirmed")
        return item, []

    def _normalize_variant_type(
        self,
        item: EvidenceItem,
    ) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        """Prefer coding-indel consequence over a paper's historical nonsense label."""
        evidence_text = f"{item.target_variant} {self._source_text(item)}"
        value = str(item.value).strip().lower()
        if self.has_coding_indel(evidence_text) and value in self._NONSENSE_TYPE_VALUES:
            return self._with_value_issue(item, "frameshift")
        if value in {"错义", "错义突变"}:
            return self._with_value_issue(item, "missense")
        if value in {"移码", "移码突变"}:
            return self._with_value_issue(item, "frameshift")
        if value in {"无义", "无义突变"}:
            return self._with_value_issue(item, "nonsense")
        return item, []

    def _align_consequence_to_coding_hgvs(
        self,
        items: list[EvidenceItem],
    ) -> tuple[list[EvidenceItem], list[EvidenceNormalizationIssue]]:
        """Use sibling A.variant_hgvs_c in the same group when the type quote omitted the del/ins.

        Papers often label a coding del/ins with the historical nonsense wording
        and a matching `p.<AA><pos>Ter` protein change. Both describe the same
        consequence, so they are realigned together; leaving one as frameshift
        and the other as a stop gain would make the group self-contradictory.
        """
        coding_groups = {
            item.group_id or ""
            for item in items
            if item.status == EvidenceStatus.FOUND
            and (
                (item.field_id == "A.variant_hgvs_c" and self.has_coding_indel(str(item.value or "")))
                or self.has_coding_indel(item.target_variant)
            )
        }
        indel_coding_values = {
            str(item.value)
            for item in items
            if item.status == EvidenceStatus.FOUND
            and item.field_id == "A.variant_hgvs_c"
            and self.has_coding_indel(str(item.value or ""))
        }
        # Live grouping sometimes puts c. and p. on different group_ids; a single
        # coding indel in the batch is still enough to realign the protein stop.
        cross_group_indel = len(indel_coding_values) == 1
        aligned: list[EvidenceItem] = []
        issues: list[EvidenceNormalizationIssue] = []
        for item in items:
            in_coding_group = item.status == EvidenceStatus.FOUND and (
                (item.group_id or "") in coding_groups or cross_group_indel
            )
            value = str(item.value).strip().lower() if item.value is not None else ""
            if item.field_id == "A.variant_type" and in_coding_group and value in self._NONSENSE_TYPE_VALUES:
                replacement, item_issues = self._with_value_issue(item, "frameshift")
                aligned.append(replacement)
                issues.extend(item_issues)
                continue
            if item.field_id == "A.variant_hgvs_p" and in_coding_group:
                frameshift = _PROTEIN_STOP_CANONICAL_RE.sub(r"\1fs", str(item.value or ""))
                if frameshift != str(item.value or ""):
                    replacement, item_issues = self._with_value_issue(item, frameshift)
                    aligned.append(replacement)
                    issues.extend(item_issues)
                    continue
            aligned.append(item)
        return aligned, issues

    def _normalize_clinvar_assertion(
        self,
        item: EvidenceItem,
    ) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        """Reject ACMG criterion lists that were copied into ClinVar assertion."""
        value_text = str(item.value)
        tokens = self._ACMG_CRITERION_TOKEN_RE.findall(value_text)
        significance_terms = ("pathogenic", "benign", "vus", "uncertain")
        if tokens and not any(term in value_text.casefold() for term in significance_terms):
            note = "criterion_claim:author_acmg_codes_not_clinvar"
            notes = f"{item.notes}; {note}" if item.notes else note
            rejected = self._reject_item(item).model_copy(update={"notes": notes})
            return (
                rejected,
                [
                    EvidenceNormalizationIssue(
                        issue_type=EvidenceNormalizationIssueType.SEMANTIC_CONFLICT,
                        severity=EvidenceNormalizationSeverity.WARNING,
                        field_id=item.field_id,
                        message="Author-stated ACMG criterion codes are not a ClinVar assertion.",
                        original_value=item.value,
                    )
                ],
            )
        return item, []

    def _normalize_hgvs_alias(
        self,
        item: EvidenceItem,
    ) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        canonical = self._canonical_hgvs_alias(item.value)
        if not canonical or canonical == item.value:
            return item, []
        return self._with_value_issue(item, canonical)

    def _normalize_consanguinity(
        self,
        item: EvidenceItem,
    ) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        text = str(item.value).strip()
        lower = text.lower()
        if lower in {"present", "consanguineous", "true"}:
            return self._with_value_issue(item, "present")
        if lower in {"absent", "non-consanguineous", "false"}:
            return self._with_value_issue(item, "absent")
        if lower in {"unknown", "not reported", "not_reported", "not applicable", "n/a", "na"}:
            return self._with_value_issue(item, "unknown")
        if text:
            return self._with_value_issue(item, f"present:{text}")
        return item, []

    def _normalize_obligate_carriers(
        self,
        item: EvidenceItem,
    ) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        if item.value is True:
            return self._with_value_issue(item, 2)
        if item.value is False:
            return self._with_value_issue(item, 0)
        if isinstance(item.value, int):
            return item, []
        text = str(item.value).strip().lower()
        if text in {"parents", "both parents"}:
            return self._with_value_issue(item, 2)
        if text.isdigit():
            return self._with_value_issue(item, int(text))
        return item, []

    def _normalize_gene_symbol(
        self,
        item: EvidenceItem,
    ) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        value = item.value
        if isinstance(value, list):
            normalized = [unicodedata.normalize("NFKC", str(v)).strip().upper() for v in value]
        elif isinstance(value, str):
            normalized = unicodedata.normalize("NFKC", value).strip().upper()
        else:
            return item, []
        if normalized == value:
            return item, []
        return self._with_value_issue(item, normalized)

    def _normalize_age_of_onset(
        self,
        item: EvidenceItem,
    ) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        text = str(item.value).strip()
        lower = text.lower()
        has_milestone = any(re.search(pattern, lower) for pattern in self._MILESTONE_PATTERNS)
        has_onset = any(term in lower for term in self._ONSET_TERMS)
        if has_milestone and not has_onset:
            return (
                self._reject_item(item),
                [
                    EvidenceNormalizationIssue(
                        issue_type=EvidenceNormalizationIssueType.SEMANTIC_CONFLICT,
                        severity=EvidenceNormalizationSeverity.ERROR,
                        field_id=item.field_id,
                        message="Developmental milestone age must not be used as age of onset.",
                        original_value=item.value,
                    )
                ],
            )
        return item, []

    def _reject_in_silico_functional(
        self,
        item: EvidenceItem,
    ) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        text = str(item.value or "").strip().lower()
        if "in silico" in text or "computational" in text:
            return (
                self._reject_item(item),
                [
                    EvidenceNormalizationIssue(
                        issue_type=EvidenceNormalizationIssueType.SEMANTIC_CONFLICT,
                        severity=EvidenceNormalizationSeverity.ERROR,
                        field_id=item.field_id,
                        message="Computational prediction must not be treated as functional evidence.",
                        original_value=item.value,
                    )
                ],
            )
        return item, []

    def _normalize_prediction_tools(
        self,
        item: EvidenceItem,
    ) -> tuple[EvidenceItem, list[EvidenceNormalizationIssue]]:
        if isinstance(item.value, list):
            values = [str(v).strip() for v in item.value if str(v).strip()]
            if not values:
                return self._reject_item(item), []
            named = [v for v in values if v.lower() not in self._GENERIC_PREDICTION_VALUES]
            if named:
                replacement, issues = self._with_value_issue(item, named)
                if len(named) != len(values):
                    issues.append(
                        EvidenceNormalizationIssue(
                            issue_type=EvidenceNormalizationIssueType.GENERIC_PREDICTION_TOOL,
                            severity=EvidenceNormalizationSeverity.WARNING,
                            field_id=item.field_id,
                            message="Generic prediction-tool phrase removed from named tool list.",
                            original_value=item.value,
                            normalized_value=named,
                        )
                    )
                return replacement, issues
        else:
            text = str(item.value).strip()
            if text.lower() in self._GENERIC_PREDICTION_VALUES:
                pass  # fall through to reject below
            elif "," in text or ";" in text:
                values = [v.strip() for v in re.split(r"[,;]", text) if v.strip()]
                named = [v for v in values if v.lower() not in self._GENERIC_PREDICTION_VALUES]
                if named:
                    replacement, issues = self._with_value_issue(item, named)
                    if len(named) != len(values):
                        issues.append(
                            EvidenceNormalizationIssue(
                                issue_type=EvidenceNormalizationIssueType.GENERIC_PREDICTION_TOOL,
                                severity=EvidenceNormalizationSeverity.WARNING,
                                field_id=item.field_id,
                                message="Generic prediction-tool phrase removed from named tool list.",
                                original_value=item.value,
                                normalized_value=named,
                            )
                        )
                    return replacement, issues
            else:
                return item, []
        return (
            self._reject_item(item),
            [
                EvidenceNormalizationIssue(
                    issue_type=EvidenceNormalizationIssueType.GENERIC_PREDICTION_TOOL,
                    severity=EvidenceNormalizationSeverity.WARNING,
                    field_id=item.field_id,
                    message="Prediction tool evidence requires named algorithms.",
                    original_value=item.value,
                )
            ],
        )

    def _merge_duplicates(
        self,
        items: list[EvidenceItem],
    ) -> tuple[list[EvidenceItem], list[EvidenceNormalizationIssue]]:
        by_key: dict[tuple[str, str, str, str], EvidenceItem] = {}
        order: list[tuple[str, str, str, str]] = []
        issues: list[EvidenceNormalizationIssue] = []
        for item in items:
            base_key = (item.group_id, item.field_id, self._normalized_value_key(item.field_id, item.value))
            key = self._dedupe_key(base_key, item, by_key)
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = self._clean_value(item)
                order.append(key)
                continue
            if item.confidence > existing.confidence:
                by_key[key] = self._clean_value(self._merge_source(item, existing))
            elif existing.raw_source is None and item.raw_source is not None:
                by_key[key] = existing.model_copy(update={"raw_source": item.raw_source})
            issues.append(
                EvidenceNormalizationIssue(
                    issue_type=EvidenceNormalizationIssueType.DUPLICATE_MERGED,
                    severity=EvidenceNormalizationSeverity.INFO,
                    field_id=item.field_id,
                    message="Duplicate evidence item merged by normalized fact key.",
                    original_value=item.value,
                    normalized_value=by_key[key].value,
                )
            )
        return [by_key[key] for key in order], issues

    @staticmethod
    def _clean_value(item: EvidenceItem) -> EvidenceItem:
        if isinstance(item.value, str):
            cleaned = re.sub(r"\s+", " ", item.value.strip())
            if cleaned != item.value:
                return item.model_copy(update={"value": cleaned})
        return item

    def _dedupe_key(
        self,
        base_key: tuple[str, str, str],
        item: EvidenceItem,
        by_key: dict[tuple[str, str, str, str], EvidenceItem],
    ) -> tuple[str, str, str, str]:
        source_signature = self._source_signature(item)
        exact_key = (*base_key, source_signature)
        if exact_key in by_key:
            return exact_key
        if source_signature == "source:none":
            for existing_key in by_key:
                if existing_key[:3] == base_key:
                    return existing_key
            return exact_key
        none_key = (*base_key, "source:none")
        if none_key in by_key:
            return none_key
        return exact_key

    def _normalized_value_key(self, field_id: str | object, value: object = _VALUE_KEY_UNSET) -> str:
        if value is _VALUE_KEY_UNSET:
            value = field_id
            field_id = ""
        if field_id in self._HGVS_ALIAS_FIELDS:
            canonical = self._canonical_hgvs_alias(value)
            if canonical:
                return f"hgvs:{canonical.casefold()}"
        if isinstance(value, list):
            return "list:" + "|".join(sorted(str(entry).strip().lower() for entry in value))
        if value is None:
            return "none:"
        normalized_text = re.sub(r"\s+", " ", str(value).strip().lower())
        return f"{type(value).__name__}:{normalized_text}"

    @staticmethod
    def _canonical_hgvs_alias(value: object) -> str:
        raw_values = value if isinstance(value, list) else [value]
        aliases: list[str] = []
        for raw_value in raw_values:
            aliases.extend(expand_hgvs_aliases(str(raw_value or "")))
        if not aliases:
            return ""
        fs_aliases = [alias for alias in aliases if re.search(r"fs", alias, re.IGNORECASE)]
        if fs_aliases:
            preferred_fs = [alias for alias in fs_aliases if re.fullmatch(r"p\.[A-Z]\d+fs", alias)]
            compact = sorted(preferred_fs or fs_aliases, key=lambda alias: (len(alias), alias))[0]
        else:
            preferred = [alias for alias in aliases if re.fullmatch(r"p\.[A-Z]\d+(?:[A-Z*]|del|dup|ins)", alias)]
            compact = sorted(preferred or aliases, key=lambda alias: (len(alias), alias))[0]
        # HGVS prefers the three-letter amino acid code and `Ter` over `X`/`*`.
        return canonical_protein_hgvs(compact) or compact

    def _source_signature(self, item: EvidenceItem) -> str:
        source = item.raw_source or item.source
        if source is None:
            return "source:none"
        return f"source:{source.block_index}:{source.context_type}:{source.context_ref}:{source.text_snippet}"

    def _merge_source(self, winner: EvidenceItem, loser: EvidenceItem) -> EvidenceItem:
        if winner.raw_source is None and loser.raw_source is not None:
            return winner.model_copy(update={"raw_source": loser.raw_source})
        if winner.source is None and loser.source is not None:
            return winner.model_copy(update={"source": loser.source})
        return winner

    def _reject_item(self, item: EvidenceItem) -> EvidenceItem:
        return item.model_copy(
            update={
                "status": EvidenceStatus.NOT_FOUND,
                "value": None,
                "confidence": 0.0,
                "assigned_acmg_codes": [],
                "assigned_clingen_modules": [],
            }
        )
