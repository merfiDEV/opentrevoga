import pytest

from trevoga.handlers import commands, comments
from trevoga.handlers.context import HandlerContext


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
    def __init__(self):
        self.enabled = False

    async def enable(self):
        self.enabled = True
        return True, "ok"

    def status_text(self):
        return f"AI: {self.enabled}"


class FakeStatistics:
    def build_text(self):
        return "stats"

    def build_report(self, hours):
        return f"report {hours}"


def build_context(**overrides):
    defaults = dict(
        client=None,
        settings=FakeSettings(),
        rules=[],
        publisher=None,
        moderation=FakeModeration(),
        statistics=FakeStatistics(),
        group_c_peer_id=-1,
        moderation_results=None,
        subscriptions=FakeSubscriptions(),
        ignored_channels=set(),
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
    assert event.responses and "КОМАНДЫ АДМИНИСТРАТОРА" in event.responses[0]


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
    context = build_context(
        client=client, publisher=publisher, settings=FakeCommentSettings()
    )
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
    handler = next(
        h for h in client.handlers if h.__name__ == "subscribe"
    )
    event = FakeEvent(pattern_groups=["БПЛА"])
    await handler(event)
    assert "бпла" in subscriptions.list_for_user(1)
