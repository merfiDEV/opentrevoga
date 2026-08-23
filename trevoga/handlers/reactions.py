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
        if total == 0:
            await context.publisher.delete_forwarded(update.msg_id)
            return
        if context.publisher.posts.exists(update.msg_id):
            return
        message = await client.get_messages(update.peer, ids=update.msg_id)
        if message:
            await context.publisher.forward_to_targets(message)
