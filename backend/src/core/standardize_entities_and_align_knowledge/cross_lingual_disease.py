"""Cross-lingual disease name resolution via fuzzy string matching.

The precise matcher resolves disease mentions by exact lookup on
``terminology_aliases.normalized_alias``. Non-English names that are not in the
hardcoded ``_CROSS_LINGUAL_DISEASE_MAP`` therefore miss unless the embedding
similarity fallback happens to land close enough to an English alias.

This module provides a deterministic, DB-query-only fallback that splits a
normalized disease name into significant tokens and matches them against
disease aliases with PostgreSQL ``ILIKE``. When several aliases match, the one
with the highest token-set overlap (Jaccard similarity) wins. ``pg_trgm`` is not
installed in the current deployment, so trigram ``similarity()`` is intentionally
omitted; the token-ILIKE path already covers the partial-match cases.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.standardize_entities_and_align_knowledge.contracts import EntityType
from src.core.standardize_entities_and_align_knowledge.normalizers import (
    normalize_disease_lookup_text,
)
from src.dao.postgresql.models import TerminologyAlias, TerminologyEntry

# Significant-token extraction: alphanumeric runs after NFKC + casefold.
_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Generic disease-name words that carry no discriminative signal. Filtering them
# keeps ILIKE queries narrow and avoids matching every "type 2" alias.
_STOPWORDS: frozenset[str] = frozenset(
    {
        "disease",
        "syndrome",
        "type",
        "the",
        "of",
        "and",
        "with",
        "due",
        "to",
        "a",
        "in",
        "for",
        "disorder",
        "deficiency",
        "mutation",
    },
)


def _tokenize_disease_query(text: str) -> list[str]:
    """Return significant query tokens from a normalized disease name.

    Tokens are alphanumeric runs longer than two characters that are not in the
    stopword set. Order is preserved for deterministic query construction.
    """
    return [token for token in _TOKEN_RE.findall(text) if len(token) > 2 and token not in _STOPWORDS]


def _jaccard_overlap(query_tokens: set[str], alias_tokens: set[str]) -> float:
    """Jaccard similarity between the query and alias token sets."""
    if not query_tokens or not alias_tokens:
        return 0.0
    intersection = len(query_tokens & alias_tokens)
    union = len(query_tokens | alias_tokens)
    return intersection / union if union else 0.0


class CrossLingualDiseaseResolver:
    """Resolve non-English disease names to English terminology display names.

    The resolver is a deterministic fallback for the precise matcher: it does no
    LLM calls and only issues ``ILIKE`` queries against ``terminology_aliases``.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve(self, raw_text: str) -> str | None:
        """Return the best matching disease ``display_name`` or ``None``.

        Steps:
          1. Normalize via ``normalize_disease_lookup_text`` (applies the
             hardcoded Chinese→English map as a fast path).
          2. Split into significant tokens; bail out if none remain.
          3. Query disease aliases whose ``normalized_alias`` ILIKE-matches every
             token.
          4. Pick the match with the highest token-set overlap (Jaccard).
        """
        normalized = normalize_disease_lookup_text(raw_text)
        tokens = _tokenize_disease_query(normalized)
        if not tokens:
            return None

        rows = await self._query_token_ilike(tokens)
        if not rows:
            return None

        return self._pick_best_overlap(tokens, rows)

    async def _query_token_ilike(
        self,
        tokens: list[str],
    ) -> list[dict[str, str]]:
        """Query disease aliases containing every token as a substring."""
        statement = (
            select(
                TerminologyEntry.display_name,
                TerminologyAlias.normalized_alias,
            )
            .join(
                TerminologyAlias,
                TerminologyAlias.entry_id == TerminologyEntry.entry_id,
            )
            .where(TerminologyAlias.entity_type == EntityType.DISEASE.value)
        )
        for token in tokens:
            statement = statement.where(
                TerminologyAlias.normalized_alias.ilike(f"%{token}%"),
            )

        result = await self._session.execute(statement)
        return [
            {
                "display_name": str(row["display_name"]),
                "normalized_alias": str(row["normalized_alias"]),
            }
            for row in result.mappings().all()
        ]

    @staticmethod
    def _pick_best_overlap(
        tokens: list[str],
        rows: list[dict[str, str]],
    ) -> str | None:
        """Return the display name of the row with the highest token overlap."""
        query_set = set(tokens)
        best_name: str | None = None
        best_score = -1.0
        for row in rows:
            alias_tokens = set(_tokenize_disease_query(row["normalized_alias"]))
            score = _jaccard_overlap(query_set, alias_tokens)
            if score > best_score:
                best_score = score
                best_name = row["display_name"]
        return best_name
