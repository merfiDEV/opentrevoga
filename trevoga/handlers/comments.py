import logging

from telethon import events

from trevoga.handlers.context import HandlerContext
from trevoga.services.text_cleaner import clean_text, quote_html, watermark


logger = logging.getLogger(__name__)


def register(client, context: HandlerContext):
    @client.on(events.NewMessage(chats=context.settings.group_c))
    async def handle_comment(event):
        message = event.message
        raw = (message.raw_text or "").strip().lower()
        if not message.is_reply or raw.startswith("."):
            return
        reply = await message.get_reply_message()
        if raw in {".отмена", ".delete", ".удалить"}:
            if reply:
                await context.publisher.delete_forwarded(reply.id)
            await message.delete()
            return
        comment = clean_text(message.raw_text or "")
        if not reply or not comment:
            return
        original = quote_html(clean_text(reply.raw_text or ""))
        combined = (
            "\n\n".join(
                filter(None, [original, f"Доп коммент.\n{quote_html(comment)}"])
            )
            + f"\n\n{watermark()}"
        )
        for target in context.settings.group_d_targets:
            try:
                sent = (
                    await client.send_file(
                        target, reply.media, caption=combined, parse_mode="html"
                    )
                    if reply.media
                    else await client.send_message(target, combined, parse_mode="html")
                )
                context.publisher.posts.save_main(reply.id, {str(target): sent.id})
            except Exception:
                logger.exception(
                    "Failed to deliver comment for %s to %s", reply.id, target
                )
        await message.delete()
