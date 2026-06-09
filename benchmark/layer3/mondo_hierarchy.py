"""MONDO ontology hierarchy lookup for evaluation ancestry matching.

Parses mondo.json (OBO Graph JSON format) to build:
- label → MONDO ID index (normalized, case-insensitive)
- child → parent adjacency from ``is_a`` edges
- Ancestor chain traversal for descendant checking

Usage::

    from benchmark.layer3.mondo_hierarchy import MondoHierarchy

    mondo = MondoHierarchy.load()
    # Check if MODY12 is a descendant of monogenic diabetes
    mondo.is_descendant_of("MONDO:0012345", "MONDO:0015967")  # True
    # Find MONDO ID by disease label
    mondo.find_id_by_label("maturity-onset diabetes of the young, type 12")
"""
from __future__ import annotations

import gzip
import json
import re
from pathlib import Path

from loguru import logger

_MONDO_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "database"
    / "terminology_database"
    / "mondo"
)
_CACHE_PATH = _MONDO_DIR / "mondo_hierarchy_cache.json"

# OBO Graph JSON predicate for subclass/parent relationship
_IS_A_PREDICATE = "is_a"


def _normalize_label(label: str) -> str:
    """Normalize a disease label for fuzzy comparison."""
    text = label.lower().strip()
    # Remove parenthetical content like "(disease)" or "(disorder)"
    text = re.sub(r"\s*\(.*?\)", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


class MondoHierarchy:
    """In-memory MONDO hierarchy for ancestry-based disease matching.

    Built from mondo.json (OBO Graph JSON). Provides:
    - Label → MONDO ID lookup
    - Ancestor chain traversal via ``is_a`` edges
    """

    def __init__(
        self,
        label_to_id: dict[str, str],
        child_to_parents: dict[str, set[str]],
    ):
        self._label_to_id = label_to_id
        self._child_to_parents = child_to_parents

    @classmethod
    def load(cls, mondo_dir: Path | None = None) -> MondoHierarchy:
        """Load MONDO hierarchy from mondo.json or cache.

        Args:
            mondo_dir: Override directory containing mondo.json.
                Defaults to ``database/terminology_database/mondo/``.
        """
        base = mondo_dir or _MONDO_DIR

        # Try cache first
        cache_path = base / "mondo_hierarchy_cache.json"
        if cache_path.exists():
            return cls._load_cache(cache_path)

        # Parse from mondo.json
        json_path = base / "mondo.json"
        gz_path = base / "mondo.json.gz"

        if json_path.exists():
            return cls._parse_and_cache(json_path, cache_path)
        if gz_path.exists():
            return cls._parse_and_cache_gz(gz_path, json_path, cache_path)

        raise FileNotFoundError(
            f"No mondo.json or mondo.json.gz found in {base}. "
            "Download from https://github.com/monarch-initiative/mondo/releases"
        )

    @classmethod
    def _parse_and_cache(
        cls, json_path: Path, cache_path: Path,
    ) -> MondoHierarchy:
        """Parse mondo.json and save a lightweight cache."""
        logger.info("Parsing MONDO from {}", json_path)
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        return cls._build_from_obo_graph(data, cache_path)

    @classmethod
    def _parse_and_cache_gz(
        cls, gz_path: Path, json_path: Path, cache_path: Path,
    ) -> MondoHierarchy:
        """Decompress mondo.json.gz, save plain JSON, then parse."""
        logger.info("Decompressing MONDO from {}", gz_path)
        with gzip.open(gz_path, "rt", encoding="utf-8") as fin:
            with open(json_path, "w", encoding="utf-8") as fout:
                # Stream in chunks to avoid loading full file twice
                while True:
                    chunk = fin.read(1024 * 1024)
                    if not chunk:
                        break
                    fout.write(chunk)
        return cls._parse_and_cache(json_path, cache_path)

    @classmethod
    def _build_from_obo_graph(
        cls, data: dict, cache_path: Path,
    ) -> MondoHierarchy:
        """Build hierarchy from OBO Graph JSON structure."""
        graphs = data.get("graphs", [])
        if not graphs:
            raise ValueError("No graphs found in mondo.json")

        graph = graphs[0]
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])

        # Build label → ID index (MONDO nodes only)
        label_to_id: dict[str, str] = {}
        id_to_label: dict[str, str] = {}
        for node in nodes:
            node_id = node.get("id", "")
            label = node.get("lbl", "")
            if not label:
                continue
            # Convert CURIE to MONDO: prefix
            mondo_id = _curie_to_mondo(node_id)
            if not mondo_id:
                continue
            norm = _normalize_label(label)
            label_to_id[norm] = mondo_id
            id_to_label[mondo_id] = label

        # Build child → parent adjacency from is_a edges
        child_to_parents: dict[str, set[str]] = {}
        for edge in edges:
            if edge.get("pred") != _IS_A_PREDICATE:
                continue
            child_curie = edge.get("sub", "")
            parent_curie = edge.get("obj", "")
            child_id = _curie_to_mondo(child_curie)
            parent_id = _curie_to_mondo(parent_curie)
            if child_id and parent_id:
                child_to_parents.setdefault(child_id, set()).add(parent_id)

        logger.info(
            "MONDO hierarchy: {} labels, {} is_a edges, {} children",
            len(label_to_id),
            sum(len(v) for v in child_to_parents.values()),
            len(child_to_parents),
        )

        instance = cls(label_to_id, child_to_parents)

        # Save lightweight cache
        cache_data = {
            "label_to_id": label_to_id,
            "child_to_parents": {
                k: sorted(v) for k, v in child_to_parents.items()
            },
        }
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f)
            logger.info("Saved MONDO cache to {}", cache_path)
        except OSError as e:
            logger.warning("Failed to save MONDO cache: {}", e)

        return instance

    @classmethod
    def _load_cache(cls, cache_path: Path) -> MondoHierarchy:
        """Load pre-built cache."""
        logger.info("Loading MONDO hierarchy from cache: {}", cache_path)
        with open(cache_path, encoding="utf-8") as f:
            data = json.load(f)
        child_to_parents = {
            k: set(v) for k, v in data["child_to_parents"].items()
        }
        logger.info(
            "MONDO hierarchy loaded: {} labels, {} children",
            len(data["label_to_id"]),
            len(child_to_parents),
        )
        return cls(data["label_to_id"], child_to_parents)

    # ── Public API ───────────────────────────────────────────────────

    def find_id_by_label(self, label: str) -> str | None:
        """Find MONDO ID by disease label (case-insensitive, normalized)."""
        norm = _normalize_label(label)
        result = self._label_to_id.get(norm)
        if result:
            return result
        # Try substring matching for partial labels
        for key, mondo_id in self._label_to_id.items():
            if norm in key or key in norm:
                return mondo_id
        return None

    def get_ancestors(self, mondo_id: str, max_depth: int = 20) -> set[str]:
        """Get all ancestor MONDO IDs by traversing is_a edges upward.

        Args:
            mondo_id: Starting MONDO ID (e.g., ``MONDO:0012345``).
            max_depth: Maximum traversal depth to prevent cycles.
        """
        ancestors: set[str] = set()
        queue = list(self._child_to_parents.get(mondo_id, set()))
        depth = 0
        while queue and depth < max_depth:
            next_queue: list[str] = []
            for parent_id in queue:
                if parent_id in ancestors:
                    continue
                ancestors.add(parent_id)
                next_queue.extend(
                    self._child_to_parents.get(parent_id, set())
                )
            queue = next_queue
            depth += 1
        return ancestors

    def is_descendant_of(self, child_id: str, ancestor_id: str) -> bool:
        """Check if child_id is a descendant of ancestor_id via is_a chain."""
        if child_id == ancestor_id:
            return True
        return ancestor_id in self.get_ancestors(child_id)

    def is_label_descendant_of(
        self, extracted_label: str, expected_mondo_id: str,
    ) -> bool:
        """Check if a disease label maps to a descendant of expected MONDO ID.

        This is the primary method for evaluation matching:
        - extracted_label: what the pipeline extracted (e.g., "MODY12")
        - expected_mondo_id: ground truth MONDO ID (e.g., "MONDO:0015967")
        """
        found_id = self.find_id_by_label(extracted_label)
        if not found_id:
            return False
        return self.is_descendant_of(found_id, expected_mondo_id)


def _curie_to_mondo(curie: str) -> str | None:
    """Convert a CURIE like ``http://purl.obolibrary.org/obo/MONDO_0012345``
    to ``MONDO:0012345``.

    Returns None if not a MONDO CURIE.
    """
    # OBO Graph JSON uses full IRIs
    if curie.startswith("http://purl.obolibrary.org/obo/MONDO_"):
        numeric = curie.split("MONDO_")[-1]
        return f"MONDO:{numeric}"
    # Direct CURIE format
    if curie.startswith("MONDO:"):
        return curie
    return None
