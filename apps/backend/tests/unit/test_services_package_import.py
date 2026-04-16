from __future__ import annotations

import importlib
import sys


def test_workflow_import_does_not_trigger_services_package_cycle() -> None:
    for name in (
        "src.domain.agent.workflow",
        "src.services",
        "src.services.task_manager",
        "src.services.translation_validation",
    ):
        sys.modules.pop(name, None)

    module = importlib.import_module("src.domain.agent.workflow")

    assert module.EvidenceAgent is not None
