from src.infrastructure import postgres


def test_build_conninfo_includes_search_path_when_schema_configured(
    monkeypatch,
) -> None:
    monkeypatch.setattr(postgres.cfg.postgresql, "schema", "acmg_app", raising=False)

    conninfo = postgres._build_conninfo()

    assert "search_path=acmg_app,public" in conninfo
