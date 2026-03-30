from src.infrastructure import postgres


class _FakeEngine:
    def __init__(self) -> None:
        self.schema_translate_map = None

    def execution_options(self, **kwargs):
        self.schema_translate_map = kwargs.get("schema_translate_map")
        return self


def test_initialize_schema_uses_configured_schema_mapping(monkeypatch) -> None:
    fake_engine = _FakeEngine()
    created = {}

    monkeypatch.setattr(
        postgres, "ensure_database_exists", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(postgres, "ensure_schema_exists", lambda *args, **kwargs: None)
    monkeypatch.setattr(postgres, "get_engine", lambda *args, **kwargs: fake_engine)
    monkeypatch.setattr(postgres, "_get_schema_name", lambda: "acmg_app")
    monkeypatch.setattr(
        postgres.Base.metadata,
        "create_all",
        lambda engine: created.setdefault("engine", engine),
    )

    postgres.initialize_schema()

    assert fake_engine.schema_translate_map == {None: "acmg_app"}
    assert created["engine"] is fake_engine
