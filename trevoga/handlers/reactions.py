from telethon import events, utils
from telethon.tl.types import UpdateMessageReactions

from trevoga.handlers.context import HandlerContext


def register(client, context: HandlerContext):
    @client.on(events.Raw())
    async def reactions(update):
        if (
            not isinstance(update, UpdateMessageReactions)
            or utils.get_peer_id(update.peer) != context.group_c_peer_id
        ):
            return
        total = sum(reaction.count for reaction in update.reactions.results)
        message = await client.get_messages(update.peer, ids=update.msg_id)
        if message:
            messages = [message]
            if message.grouped_id:
                nearby = await client.get_messages(
                    update.peer, min_id=max(0, message.id - 10), max_id=message.id + 10
                )
                messages = sorted(
                    [item for item in nearby if item.grouped_id == message.grouped_id],
                    key=lambda item: item.id,
                )
            primary_id = messages[0].id
            if total == 0:
                await context.publisher.delete_forwarded(primary_id)
                return
            if context.publisher.posts.exists(primary_id):
                return
            await context.publisher.forward_to_targets(messages)
