import re

import pytest

from trevoga.integrations.ai_client import AIClient


def _mock_response(payload, status_code=200):
    class Response:
        def __init__(self):
            self.status_code = status_code
            self.request = None

        def raise_for_status(self):
            if status_code >= 400:
                import httpx

                raise httpx.HTTPStatusError(
                    "error", request=self.request, response=self
                )

        def json(self):
            return payload

    return Response()


def _install_mock(monkeypatch, handler):
    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def request(self, method, url, **kwargs):
            return handler(method, url, kwargs)

        async def aclose(self):
            pass

    import trevoga.integrations.ai_client as ai_client

    monkeypatch.setattr(ai_client.httpx, "AsyncClient", MockClient)


def test_ai_set_command_matches_without_model():
    pattern = re.compile(r"^\.ai(?:\s+(on|off|status|set)(?:\s+(.+))?)?\s*$")
    match = pattern.match(".ai set")
    assert match and match.group(1) == "set" and match.group(2) is None


@pytest.mark.asyncio
async def test_list_models_accepts_string_and_name_entries(monkeypatch):
    _install_mock(
        monkeypatch,
        lambda method, url, kwargs: _mock_response(
            {"data": ["z", {"name": "a"}, {}, None]}
        ),
    )
    assert await AIClient("http://localhost/v1", "z", "", 5).list_models() == [
        "a",
        "z",
    ]


@pytest.mark.asyncio
async def test_list_models_returns_sorted_ids(monkeypatch):
    _install_mock(
        monkeypatch,
        lambda method, url, kwargs: _mock_response(
            {"data": [{"id": "z"}, {"id": "a"}, {"name": "ignored"}]}
        ),
    )
    assert await AIClient("http://localhost/v1", "z", "", 5).list_models() == [
        "a",
        "ignored",
        "z",
    ]


@pytest.mark.asyncio
async def test_complete_retries_on_server_error(monkeypatch):
    calls = {"count": 0}

    def handler(method, url, kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return _mock_response({}, status_code=503)
        return _mock_response({"choices": [{"message": {"content": "ok"}}]})

    _install_mock(monkeypatch, handler)
    client = AIClient("http://localhost/v1", "z", "", 5)
    assert await client.complete("sys", "user") == "ok"
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_connect_error_is_not_retried(monkeypatch):
    import httpx

    calls = {"count": 0}

    def handler(method, url, kwargs):
        calls["count"] += 1
        raise httpx.ConnectError("connection refused")

    _install_mock(monkeypatch, handler)
    client = AIClient("http://localhost/v1", "z", "", 5)
    with pytest.raises(httpx.ConnectError):
        await client.complete("sys", "user")
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_read_timeout_is_retried(monkeypatch):
    import httpx

    calls = {"count": 0}

    def handler(method, url, kwargs):
        calls["count"] += 1
        if calls["count"] < 2:
            raise httpx.ReadTimeout("slow")
        return _mock_response({"choices": [{"message": {"content": "ok"}}]})

    async def instant_sleep(_delay):
        return None

    import trevoga.integrations.ai_client as ai_client

    monkeypatch.setattr(ai_client.asyncio, "sleep", instant_sleep)
    _install_mock(monkeypatch, handler)
    client = AIClient("http://localhost/v1", "z", "", 5)
    assert await client.complete("sys", "user") == "ok"
    assert calls["count"] == 2
