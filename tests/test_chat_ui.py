"""Cached-protocol dropdown API used by the separate chat UI."""

from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app

client = TestClient(app)


def test_chat_page_is_removed() -> None:
    response = client.get("/chat")
    assert response.status_code == 404


def test_protocols_lists_cached_studies(tmp_path, monkeypatch) -> None:
    protocols_dir = tmp_path / "protocols"
    protocols_dir.mkdir()
    (protocols_dir / "NCT00000001.json").write_text(
        '{"protocolSection":{"identificationModule":'
        '{"nctId":"NCT00000001","briefTitle":"Toy vaccine study"}}}',
        encoding="utf-8",
    )
    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.main.settings",
        Settings(protocols_dir=protocols_dir),
    )

    response = client.get("/protocols")
    assert response.status_code == 200
    assert response.json() == [
        {"nct_id": "NCT00000001", "brief_title": "Toy vaccine study"}
    ]


def test_protocols_empty_when_directory_missing(tmp_path, monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.main.settings",
        Settings(protocols_dir=tmp_path / "missing"),
    )

    response = client.get("/protocols")
    assert response.status_code == 200
    assert response.json() == []
