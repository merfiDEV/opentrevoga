import logging

from trevoga.config import Settings
from trevoga.storage.repositories import ForwardedPostRepository, StatisticsRepository


logger = logging.getLogger(__name__)


class PublishingService:
    def __init__(
        self,
        client,
        settings: Settings,
        posts: ForwardedPostRepository,
        stats: StatisticsRepository,
    ):
        self.client = client
        self.settings = settings
        self.posts = posts
        self.stats = stats

    async def forward_to_targets(self, message) -> dict[str, int]:
        references = {}
        for target in self.settings.group_d_targets:
            try:
                forwarded = await message.forward_to(target)
                references[str(target)] = forwarded.id
            except Exception:
                logger.exception(
                    "Failed to forward message %s to %s", message.id, target
                )
        self.posts.save_main(message.id, references)
        self.stats.record("to_d", message_id=message.id)
        return references

    async def delete_forwarded(self, source_message_id: int) -> int:
        post = self.posts.get(source_message_id)
        if not post:
            return 0
        deleted = 0
        grouped: dict[str, list[int]] = {}
        for target, message_id in post.main.items():
            grouped.setdefault(target, []).append(message_id)
        for target, message_id in post.comments:
            grouped.setdefault(target, []).append(message_id)
        for target, message_ids in grouped.items():
            try:
                await self.client.delete_messages(
                    int(target) if target.lstrip("-").isdigit() else target, message_ids
                )
                deleted += len(message_ids)
            except Exception:
                logger.exception("Failed to delete messages in %s", target)
        self.posts.delete(source_message_id)
        return deleted
