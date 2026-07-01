"""Tests for DAO type-contract compliance rules."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent


def test_unstructured_dict_return_annotations_are_justified() -> None:
    """DAO bare dict return annotations use the project-required noqa marker."""
    files = [
        REPO_ROOT / "backend" / "src" / "dao" / "redis" / "cache_repo.py",
        REPO_ROOT / "backend" / "src" / "dao" / "postgresql" / "search_index_repo.py",
        REPO_ROOT / "backend" / "src" / "dao" / "postgresql" / "literature_profile_repo.py",
    ]

    for path in files:
        for line_number, line in enumerate(path.read_text().splitlines(), start=1):
            if "-> dict[" in line or "-> list[dict[" in line:
                assert "# noqa" in line and "dict-return:" in line, (
                    f"{path}:{line_number} missing dict-return justification"
                )
