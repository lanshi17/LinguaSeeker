from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
MANIFEST_PATH = FIXTURES_DIR / "multilingual_case_report_manifest.json"


def test_manifest_has_required_language_and_provider_coverage() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    language_counts = Counter(item["language"] for item in manifest)
    assert language_counts == {
        "zh": 2,
        "ja": 2,
        "ko": 2,
        "ru": 2,
        "de": 2,
        "en": 5,
    }

    providers = {item["provider"] for item in manifest}
    assert {
        "crossref",
        "pmc",
        "unpaywall",
        "doaj",
        "jstage",
        "pubscholar",
        "hans_publishers",
        "cyberleninka",
    } <= providers
