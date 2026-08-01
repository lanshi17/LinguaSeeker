"""Neo4j environment configuration tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


@pytest.mark.parametrize("environment", ["development", "staging"])
def test_neo4j_database_matches_server_default(environment: str) -> None:
    config_path = (
        Path(__file__).resolve().parents[3]
        / "config"
        / "environments"
        / f"{environment}.yaml"
    )
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert config["neo4j"]["database"] == "neo4j"
