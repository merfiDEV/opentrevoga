import pytest

from trevoga.handlers import commands, comments, sources
from trevoga.handlers.context import HandlerContext
from trevoga.services.fix_service import FixService


class FakeClient:
    def __init__(self):
        self.handlers = []

    def on(self, event):
        def decorator(func):
            self.handlers.append(func)
            return func

        return decorator

    async def edit_message(self, *args, **kwargs):
        return None

    async def send_message(self, *args, **kwargs):
        return FakeMessage(1)

    async def send_file(self, *args, **kwargs):
        return FakeMessage(1)


class FakeMessage:
    def __init__(self, message_id):
        self.id = message_id
        self.raw_text = ""

    async def delete(self):
        return None

    async def get_reply_message(self):
        return None


class FakePatternMatch:
    def __init__(self, groups):
        self._groups = groups

    def group(self, index):
        return self._groups[index - 1] if index - 1 < len(self._groups) else None


class FakeEvent:
    def __init__(self, text="", sender_id=1, pattern_groups=None):
        self.message = FakeMessage(42)
        self.sender_id = sender_id
        self.chat_id = -1
        self.pattern_match = FakePatternMatch(pattern_groups or [])
        self.responses = []
        self._text = text

    async def respond(self, text, **kwargs):
        self.responses.append(text)

    async def delete(self):
        return None


class FakeSettings:
    group_c = -1
    admin_ids = (1,)


class FakeSubscriptions:
    def __init__(self):
        self.data = {}

    def list_for_user(self, user_id):
        return sorted(self.data.get(user_id, set()))

    def add(self, user_id, keyword):
        self.data.setdefault(user_id, set()).add(keyword)
        return True

    def remove(self, user_id, keyword):
        return keyword in self.data.get(user_id, set()) and not self.data[user_id].discard(keyword)

    def remove_all(self, user_id):
        return len(self.data.pop(user_id, set()))


class FakeModeration:
    def __init__(self, fixed=None):
        self.enabled = False
        self.fixed = fixed
        self.calls = []

    async def enable(self):
        self.enabled = True
        return True, "ok"

    async def fix(self, text, mode="default", instruction=None):
        self.calls.append((text, mode, instruction))
        return self.fixed

    def status_text(self):
        return f"AI: {self.enabled}"


class FakeStatistics:
    def build_text(self):
        return "stats"

    def build_report(self, hours):
        return f"report {hours}"


def build_context(**overrides):
    moderation = overrides.get("moderation") or FakeModeration()
    defaults = dict(
        client=None,
        settings=FakeSettings(),
        rules=[],
        publisher=None,
        moderation=moderation,
        statistics=FakeStatistics(),
        group_c_peer_id=-1,
        moderation_results=None,
        subscriptions=FakeSubscriptions(),
        ignored_channels=set(),
        fixer=FixService(moderation),
    )
    defaults.update(overrides)
    return HandlerContext(**defaults)


@pytest.mark.asyncio
async def test_help_command_returns_commands():
    client = FakeClient()
    context = build_context(client=client)
    commands.register(client, context)
    help_handler = next(
        handler for handler in client.handlers if handler.__name__ == "help_command"
    )
    event = FakeEvent()
    await help_handler(event)
    assert event.responses and "КОМАНДИ АДМІНІСТРАТОРА" in event.responses[0]


class FakePublisher:
    def __init__(self):
        self.posts = FakePosts()
        self.forwarded = []

    async def delete_forwarded(self, message_id):
        return 0

    async def forward_to_targets(self, messages):
        self.forwarded.append(messages)
        return {}


class FakePosts:
    def __init__(self):
        self.saved = {}

    def save_main(self, source_message_id, messages):
        self.saved[source_message_id] = messages

    def exists(self, source_message_id):
        return source_message_id in self.saved


class FakeReplyMessage(FakeMessage):
    def __init__(self, message_id, text):
        super().__init__(message_id)
        self.raw_text = text
        self.media = None


class FakeFixMessage(FakeMessage):
    def __init__(self, message_id, text, media=None, reply=None):
        super().__init__(message_id)
        self.raw_text = text
        self.media = media
        self._reply = reply

    async def get_reply_message(self):
        return self._reply


class FakeFixEvent(FakeEvent):
    def __init__(self, text, reply=None, sender_id=1, groups=None):
        argument = text.strip().split(maxsplit=1)
        groups = groups if groups is not None else [argument[1] if len(argument) > 1 else None]
        super().__init__(text=text, sender_id=sender_id, pattern_groups=groups)
        self.message = FakeFixMessage(99, text, reply=reply)
        self.message.is_reply = reply is not None
        self.edits = []

    async def delete(self):
        return None


class FakeEditClient(FakeClient):
    def __init__(self):
        super().__init__()
        self.edits = []

    async def edit_message(self, chat, message_id, text, **kwargs):
        self.edits.append((message_id, text))
        return None


def fix_handler(client):
    return next(h for h in client.handlers if h.__name__ == "fix")


class FakeCommentEvent(FakeEvent):
    def __init__(self, text, reply):
        super().__init__(text=text)
        self.message.is_reply = reply is not None
        self.message.raw_text = text
        self._reply = reply
        self.message.get_reply_message = self._get_reply

    async def _get_reply(self):
        return self._reply


class FakeCommentSettings(FakeSettings):
    group_d_targets = ("-100",)


@pytest.mark.asyncio
async def test_comment_is_forwarded_to_targets():
    client = FakeClient()
    publisher = FakePublisher()
    context = build_context(client=client, publisher=publisher, settings=FakeCommentSettings())
    comments.register(client, context)
    handler = next(h for h in client.handlers if h.__name__ == "handle_comment")
    event = FakeCommentEvent("важное уточнение", FakeReplyMessage(7, "исходный текст"))
    await handler(event)
    assert publisher.posts.saved[7] == {"-100": 1}


@pytest.mark.asyncio
async def test_subscribe_adds_keyword():
    client = FakeClient()
    subscriptions = FakeSubscriptions()
    context = build_context(client=client, subscriptions=subscriptions)
    commands.register(client, context)
    handler = next(h for h in client.handlers if h.__name__ == "subscribe")
    event = FakeEvent(pattern_groups=["БПЛА"])
    await handler(event)
    assert "бпла" in subscriptions.list_for_user(1)


@pytest.mark.asyncio
async def test_fix_without_reply_reports_usage():
    client = FakeEditClient()
    context = build_context(client=client)
    commands.register(client, context)
    event = FakeFixEvent(".fix short", reply=None)
    await fix_handler(client)(event)
    assert event.responses and "Дайте відповідь" in event.responses[0]
    assert not client.edits


@pytest.mark.asyncio
async def test_fix_edits_reply_in_mode():
    client = FakeEditClient()
    moderation = FakeModeration(fixed="Виправлений текст")
    context = build_context(client=client, moderation=moderation)
    commands.register(client, context)
    reply = FakeReplyMessage(7, "исходный текст")
    event = FakeFixEvent(".fix short", reply=reply)
    await fix_handler(client)(event)
    assert moderation.calls == [("исходный текст", "short", "")]
    assert client.edits and client.edits[0][0] == 7
    assert any("Виправлено" in text for text in event.responses)


@pytest.mark.asyncio
async def test_fix_custom_instruction_is_forwarded():
    client = FakeEditClient()
    moderation = FakeModeration(fixed="Новый текст")
    context = build_context(client=client, moderation=moderation)
    commands.register(client, context)
    reply = FakeReplyMessage(7, "текст с матом")
    event = FakeFixEvent(".fix убери мат", reply=reply)
    await fix_handler(client)(event)
    assert moderation.calls[0][2] == "убери мат"
    assert moderation.calls[0][1] == "default"
    assert client.edits


@pytest.mark.asyncio
async def test_fix_test_mode_does_not_edit():
    client = FakeEditClient()
    moderation = FakeModeration(fixed="Предпросмотр")
    context = build_context(client=client, moderation=moderation)
    commands.register(client, context)
    reply = FakeReplyMessage(7, "исходник")
    event = FakeFixEvent(".fix test", reply=reply)
    await fix_handler(client)(event)
    assert not client.edits
    assert any("Попередній перегляд" in text for text in event.responses)


@pytest.mark.asyncio
async def test_fix_reports_when_ai_unavailable():
    client = FakeEditClient()
    moderation = FakeModeration(fixed=None)
    context = build_context(client=client, moderation=moderation)
    commands.register(client, context)
    reply = FakeReplyMessage(7, "исходник")
    event = FakeFixEvent(".fix", reply=reply)
    await fix_handler(client)(event)
    assert not client.edits
    assert any("недоступний" in text for text in event.responses)


@pytest.mark.asyncio
async def test_fix_unchanged_reports_no_changes():
    client = FakeEditClient()
    moderation = FakeModeration(fixed="исходник")
    context = build_context(client=client, moderation=moderation)
    commands.register(client, context)
    reply = FakeReplyMessage(7, "исходник")
    event = FakeFixEvent(".fix", reply=reply)
    await fix_handler(client)(event)
    assert not client.edits
    assert any("змін немає" in text for text in event.responses)


@pytest.mark.asyncio
async def test_fix_undo_restores_original():
    client = FakeEditClient()
    moderation = FakeModeration(fixed="Правка")
    context = build_context(client=client, moderation=moderation)
    commands.register(client, context)
    reply = FakeReplyMessage(7, "оригинал")
    handler = fix_handler(client)
    await handler(FakeFixEvent(".fix", reply=reply))
    assert client.edits
    client.edits.clear()
    await handler(FakeFixEvent(".fix undo", reply=reply))
    assert client.edits and client.edits[0][0] == 7
    assert "оригинал" in client.edits[0][1]


@pytest.mark.asyncio
async def test_autocheck_message_edits_when_enabled():
    client = FakeEditClient()
    moderation = FakeModeration(fixed="Офіційний текст")
    context = build_context(client=client, moderation=moderation)
    context.fixer.autocheck_enabled = True
    await sources._autocheck_message(client, context, 5, "текст про бпла")
    assert moderation.calls and moderation.calls[0][1] == "official"
    assert client.edits and client.edits[0][0] == 5
    assert "Офіційний текст" in client.edits[0][1]


@pytest.mark.asyncio
async def test_autocheck_message_skips_when_disabled():
    client = FakeEditClient()
    moderation = FakeModeration(fixed="Офіційний текст")
    context = build_context(client=client, moderation=moderation)
    context.fixer.autocheck_enabled = False
    await sources._autocheck_message(client, context, 5, "якийсь текст")
    assert not moderation.calls
    assert not client.edits


@pytest.mark.asyncio
async def test_autocheck_keeps_wiki_links():
    client = FakeEditClient()
    moderation = FakeModeration(fixed="Офіційний текст про бпла")
    rules = [
        (
            ("бпла",),
            None,
            "БПЛА/Шахеди",
            "https://uk.wikipedia.org/wiki/БпЛА",
        ),
    ]
    context = build_context(client=client, moderation=moderation, rules=rules)
    context.fixer.autocheck_enabled = True
    await sources._autocheck_message(client, context, 5, "текст про бпла")
    assert client.edits
    edited = client.edits[0][1]
    assert "uk.wikipedia.org" in edited
    assert "БПЛА/Шахеди" in edited


@pytest.mark.asyncio
async def test_aicheck_toggles_and_persists(monkeypatch):
    saved = {}
    monkeypatch.setattr(commands, "save_aicheck", lambda value: saved.__setitem__("value", value))
    client = FakeEditClient()
    context = build_context(client=client)
    commands.register(client, context)
    handler = next(h for h in client.handlers if h.__name__ == "aicheck")
    assert context.fixer.autocheck_enabled is False
    on_event = FakeFixEvent(".aicheck on")
    await handler(on_event)
    assert context.fixer.autocheck_enabled is True
    assert saved["value"] is True
    assert any("увімкнено" in text for text in on_event.responses)
    off_event = FakeFixEvent(".aicheck off")
    await handler(off_event)
    assert context.fixer.autocheck_enabled is False
    assert saved["value"] is False
    assert any("вимкнено" in text for text in off_event.responses)


@pytest.mark.asyncio
async def test_fix_help_lists_custom_request():
    client = FakeEditClient()
    context = build_context(client=client)
    commands.register(client, context)
    event = FakeFixEvent(".fix help")
    await fix_handler(client)(event)
    assert any("прохання" in text for text in event.responses)


@pytest.mark.asyncio
async def test_truncate_caption_keeps_short_text():
    caption = "короткий текст"
    assert sources._truncate_caption(caption) == caption


def test_truncate_caption_closes_open_tags():
    caption = "<blockquote>" + "х" * 2000 + "</blockquote>"
    result = sources._truncate_caption(caption)
    assert len(result) <= 1024
    assert result.startswith("<blockquote>")
    assert result.count("<blockquote>") == result.count("</blockquote>")
    assert result.endswith("</blockquote>")


def test_truncate_caption_handles_no_html():
    caption = "a" * 2000
    result = sources._truncate_caption(caption)
    assert len(result) <= 1024
    assert "…" in result
