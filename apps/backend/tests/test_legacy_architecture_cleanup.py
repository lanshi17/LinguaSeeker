from __future__ import annotations

import importlib.util
import re
import sys
import types
from pathlib import Path
from typing import Protocol, cast

import pytest


BACKEND_ROOT = Path(__file__).resolve().parent.parent
APP_MODULE_PATH = BACKEND_ROOT / "app.py"
SKIP_DIR_NAMES = {".venv", "__pycache__", ".worktrees", "worktrees"}
LEGACY_IMPORT_REGEXES = (
    re.compile(r"^\s*from\s+src\.presentation\b", re.MULTILINE),
    re.compile(r"^\s*import\s+src\.presentation\b", re.MULTILINE),
    re.compile(r"^\s*from\s+presentation\b", re.MULTILINE),
    re.compile(r"^\s*import\s+presentation\b", re.MULTILINE),
)
LEGACY_CONFIG_IMPORT_REGEXES = (
    re.compile(r"^\s*from\s+src\.configs\b", re.MULTILINE),
    re.compile(r"^\s*import\s+src\.configs\b", re.MULTILINE),
    re.compile(r"^\s*from\s+configs\b", re.MULTILINE),
    re.compile(r"^\s*import\s+configs\b", re.MULTILINE),
)


class SupportsApp(Protocol):
    app: object


class FakeMainModule(types.ModuleType):
    app: object

    def __init__(self, name: str, app: object) -> None:
        super().__init__(name)
        self.app = app


def _python_files_without_skipped_dirs(root: Path):
    for path in root.rglob("*.py"):
        relative_path = path.relative_to(root)
        if any(part in SKIP_DIR_NAMES for part in relative_path.parts[:-1]):
            continue
        yield path


def test_legacy_app_module_re_exports_main_app(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_app = object()
    fake_main = FakeMainModule("main", fake_app)
    monkeypatch.setitem(sys.modules, "main", fake_main)

    spec = importlib.util.spec_from_file_location("_legacy_app_module", APP_MODULE_PATH)
    assert spec is not None and spec.loader is not None
    legacy_app_module = importlib.util.module_from_spec(spec)

    try:
        spec.loader.exec_module(legacy_app_module)
    except Exception as exc:  # pragma: no cover - exercised only in RED state
        pytest.fail(
            f"legacy app module must import and re-export main.app without legacy dependencies: {exc}"
        )

    loaded_module = cast(SupportsApp, cast(object, legacy_app_module))
    assert loaded_module.app is fake_app


def test_legacy_presentation_package_is_removed() -> None:
    assert not (BACKEND_ROOT / "src/presentation").exists()


def test_legacy_controller_integration_test_is_removed() -> None:
    assert not (BACKEND_ROOT / "tests/integration/api/test_document_api.py").exists()


def test_no_python_files_depend_on_presentation_imports() -> None:
    matches: list[str] = []

    for path in _python_files_without_skipped_dirs(BACKEND_ROOT):
        relative_path = path.relative_to(BACKEND_ROOT)
        content = path.read_text(encoding="utf-8")
        if any(pattern.search(content) for pattern in LEGACY_IMPORT_REGEXES):
            matches.append(str(relative_path))

    assert matches == []


def test_no_python_files_depend_on_legacy_config_imports() -> None:
    matches: list[str] = []

    for path in _python_files_without_skipped_dirs(BACKEND_ROOT):
        relative_path = path.relative_to(BACKEND_ROOT)
        content = path.read_text(encoding="utf-8")
        if any(pattern.search(content) for pattern in LEGACY_CONFIG_IMPORT_REGEXES):
            matches.append(str(relative_path))

    assert matches == []
