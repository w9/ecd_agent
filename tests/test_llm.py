"""OpenRouter chat helper, including LLM_DEBUG payload capture."""

from __future__ import annotations

from typing import Any

from app.config import Settings
from app.llm import chat


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeClient:
    last_body: dict[str, Any] | None = None

    def __init__(self, **kwargs: object) -> None:
        del kwargs

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, *args: object) -> bool:
        return False

    def post(self, url: str, headers: object = None, json: dict[str, Any] | None = None):
        del url, headers
        _FakeClient.last_body = json
        return _FakeResponse(
            {"choices": [{"message": {"role": "assistant", "content": "hello"}}]}
        )


def test_chat_attaches_debug_payloads_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.llm.get_settings",
        lambda: Settings(llm_debug=True, openrouter_api_key="test-key"),
    )
    monkeypatch.setattr("app.llm.httpx.Client", _FakeClient)

    result = chat([{"role": "user", "content": "ping"}])
    assert result.content == "hello"
    assert result.debug_request is not None
    assert result.debug_request["messages"][0]["content"] == "ping"
    assert result.debug_response == {
        "choices": [{"message": {"role": "assistant", "content": "hello"}}]
    }


def test_chat_omits_debug_payloads_by_default(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.llm.get_settings",
        lambda: Settings(llm_debug=False, openrouter_api_key="test-key"),
    )
    monkeypatch.setattr("app.llm.httpx.Client", _FakeClient)

    result = chat([{"role": "user", "content": "ping"}])
    assert result.content == "hello"
    assert result.debug_request is None
    assert result.debug_response is None
