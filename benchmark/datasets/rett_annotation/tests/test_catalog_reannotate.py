"""Tests for the catalog reannotation CLI."""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from cli import catalog_reannotate
from src.models import RettExpectedJson


class CatalogReannotateTest(unittest.TestCase):
    def test_empty_annotation_is_failed_and_not_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "ground_truth" / "rett_empty"
            target.mkdir(parents=True)
            config = SimpleNamespace(
                resolved_paths={
                    "ground_truth_dir": root / "ground_truth",
                    "approved_dir": root / "approved",
                    "draft_dir": root / "draft",
                }
            )
            source = catalog_reannotate.EntryInput(
                entry_id="rett_empty",
                language="en",
                source_path=root / "source.md",
                source_text="MECP2 Rett syndrome source text",
            )

            async def fake_annotate_article(*_args, **_kwargs):
                return RettExpectedJson(entry_id="rett_empty", source_language="en")

            with mock.patch.object(catalog_reannotate, "annotate_article", fake_annotate_article):
                row = asyncio.run(
                    catalog_reannotate._annotate_one(
                        config=config,
                        source=source,
                        model="claude-opus-4-8",
                        write=True,
                        semaphore=asyncio.Semaphore(1),
                    )
                )

            self.assertEqual("failed", row.status)
            self.assertIn("empty annotation", row.error)
            self.assertFalse((target / "expected.json").exists())


if __name__ == "__main__":
    unittest.main()
