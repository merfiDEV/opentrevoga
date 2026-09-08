import pytest
import re

from trevoga.integrations.ai_client import AIClient


def test_ai_set_command_matches_without_model():
    pattern = re.compile(r"^\.ai(?:\s+(on|off|status|set)(?:\s+(.+))?)?\s*$")
    match = pattern.match(".ai set")
    assert match and match.group(1) == "set" and match.group(2) is None


@pytest.mark.asyncio
async def test_list_models_accepts_string_and_name_entries(monkeypatch):
    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, *args, **kwargs):
            class Response:
                def raise_for_status(self):
                    return None

                def json(self):
                    return {"data": ["z", {"name": "a"}, {}, None]}

            return Response()

    import trevoga.integrations.ai_client as ai_client

    monkeypatch.setattr(ai_client.httpx, "AsyncClient", MockClient)
    assert await AIClient("http://localhost/v1", "z", "", 5).list_models() == [
        "a",
        "z",
    ]


@pytest.mark.asyncio
async def test_list_models_returns_sorted_ids(monkeypatch):
    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, *args, **kwargs):
            class Response:
                def raise_for_status(self):
                    return None

                def json(self):
                    return {"data": [{"id": "z"}, {"id": "a"}, {"name": "ignored"}]}

            return Response()

    import trevoga.integrations.ai_client as ai_client

    monkeypatch.setattr(ai_client.httpx, "AsyncClient", MockClient)
    assert await AIClient("http://localhost/v1", "z", "", 5).list_models() == [
        "a",
        "ignored",
        "z",
    ]
