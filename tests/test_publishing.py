from trevoga.services.publishing import PublishingService


class FakePosts:
    def __init__(self):
        self.saved = {}

    def save_main(self, source_message_id, messages):
        self.saved[source_message_id] = messages


class FakeStats:
    def __init__(self):
        self.records = []

    def record(self, kind, **kwargs):
        self.records.append((kind, kwargs))


class FakeMessage:
    def __init__(self, message_id, grouped_id=None):
        self.id = message_id
        self.grouped_id = grouped_id
        self.media = None

    async def forward_to(self, target):
        return FakeMessage(self.id * 10)


class FakeSettings:
    group_d_targets = ("-100",)
    channel_targets = ()


class FakeClient:
    def __init__(self):
        self.sent = []

    async def send_message(self, target, text, **kwargs):
        self.sent.append((target, text))
        return FakeMessage(1)

    async def send_file(self, target, media, **kwargs):
        self.sent.append((target, media))
        return FakeMessage(1)


async def test_forward_to_targets_records_references():
    posts, stats, client = FakePosts(), FakeStats(), FakeClient()
    service = PublishingService(client, FakeSettings(), posts, stats)
    references = await service.forward_to_targets(FakeMessage(5))
    assert references == {"-100": 50}
    assert posts.saved[5] == {"-100": 50}
    assert stats.records == [("to_d", {"message_id": 5})]
