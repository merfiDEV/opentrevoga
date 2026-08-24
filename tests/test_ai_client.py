import pytest

from trevoga.integrations.ai_client import AIClient


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
    assert await AIClient("http://localhost/v1", "z", "", 5).list_models() == ["a", "z"]
