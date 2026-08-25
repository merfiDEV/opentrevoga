import logging

from telethon.tl.types import Channel

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
        self._valid_channel_targets = tuple(settings.channel_targets)

    async def forward_to_targets(self, message) -> dict[str, int]:
        messages = message if isinstance(message, list) else [message]
        primary = messages[0]
        references = {}
        for target in self.settings.group_d_targets:
            try:
                if len(messages) == 1:
                    forwarded = await primary.forward_to(target)
                else:
                    forwarded = await self.client.forward_messages(target, messages)
                forwarded = forwarded if isinstance(forwarded, list) else [forwarded]
                references[str(target)] = forwarded[0].id
            except Exception:
                logger.exception(
                    "Failed to forward message %s to %s", primary.id, target
                )
        for target in self._valid_channel_targets:
            try:
                sent = await self._send_to_channel(target, messages)
                references[str(target)] = sent[0].id
            except Exception:
                logger.exception(
                    "Failed to publish message %s to channel %s", primary.id, target
                )
        self.posts.save_main(primary.id, references)
        self.stats.record("to_d", message_id=primary.id)
        return references

    async def validate_channel_targets(self) -> None:
        """Keep only channels where this account can publish as the channel."""
        valid = []
        for target in self.settings.channel_targets:
            try:
                entity = await self.client.get_entity(target)
                if not isinstance(entity, Channel) or not entity.broadcast:
                    raise ValueError("target is not a broadcast channel")
                permissions = await self.client.get_permissions(entity, "me")
                admin_rights = permissions.participant.admin_rights
                if not permissions.is_admin or not (
                    permissions.is_creator
                    or (admin_rights and admin_rights.post_messages)
                ):
                    raise PermissionError("account has no post_messages admin right")
                valid.append(target)
            except Exception:
                logger.exception(
                    "Channel target %s is unavailable for publishing", target
                )
        self._valid_channel_targets = tuple(valid)

    async def _send_to_channel(self, target, messages):
        if len(messages) == 1:
            message = messages[0]
            if message.media:
                sent = await self.client.send_file(
                    target,
                    message.media,
                    caption=message.message or "",
                    formatting_entities=message.entities,
                )
            else:
                sent = await self.client.send_message(
                    target, message.message or "", formatting_entities=message.entities
                )
            return sent if isinstance(sent, list) else [sent]
        sent = await self.client.send_file(
            target,
            [message.media for message in messages],
            caption=[message.message or "" for message in messages],
            formatting_entities=[message.entities for message in messages],
        )
        return sent if isinstance(sent, list) else [sent]

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
