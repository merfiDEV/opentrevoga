from dataclasses import dataclass


@dataclass
class HandlerContext:
    client: object
    settings: object
    rules: list
    publisher: object
    moderation: object
    statistics: object
    group_c_peer_id: int | None = None

    def is_admin(self, user_id: int | None) -> bool:
        return user_id in self.settings.admin_ids
