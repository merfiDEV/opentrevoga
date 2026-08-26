from dataclasses import dataclass, field


@dataclass
class HandlerContext:
    client: object
    settings: object
    rules: list
    publisher: object
    moderation: object
    statistics: object
    group_c_peer_id: int | None = None
    moderation_results: object | None = None
    ignored_channels: set[int] = field(default_factory=set)

    def is_admin(self, user_id: int | None) -> bool:
        return user_id in self.settings.admin_ids

    def is_channel_ignored(self, chat_id: int | None) -> bool:
        return chat_id is not None and chat_id in self.ignored_channels
