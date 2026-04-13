from __future__ import annotations

from pathlib import Path

import yaml


def test_neo4j_runtime_config_uses_environment_not_host_conf_mounts() -> None:
    compose_path = Path(__file__).resolve().parents[2] / "database" / "podman-compose.yml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))

    volumes = compose["services"]["neo4j"]["volumes"]
    environment = compose["services"]["neo4j"]["environment"]

    assert "./neo4j/conf:/var/lib/neo4j/conf" not in volumes
    assert "./neo4j/conf/neo4j.conf:/var/lib/neo4j/conf/neo4j.conf" not in volumes
    assert "NEO4J_server_bolt_enabled=true" in environment
    assert "NEO4J_server_bolt_listen__address=0.0.0.0:7687" in environment
    assert "NEO4J_server_bolt_advertised__address=:7687" in environment
    assert "NEO4J_server_bolt_tls__level=DISABLED" in environment
    assert "NEO4J_server_memory_pagecache_size=512M" in environment
    assert "NEO4J_server_default__listen__address=0.0.0.0" in environment
