from telethon import events

from trevoga.handlers.context import HandlerContext
from trevoga.services.text_cleaner import WATERMARK, clean_text, format_post_html


def register(client, context: HandlerContext):
    @client.on(events.NewMessage(pattern=r"^\.stat(?:s)?(?:\s+(\d+))?$"))
    async def stats(event):
        if not context.is_admin(event.sender_id):
            return
        value = event.pattern_match.group(1)
        hours = int(value) if value else None
        text = (
            context.statistics.build_text()
            if hours is None
            else f"<blockquote>{context.statistics.build_report(hours)}\n\n{WATERMARK}</blockquote>"
        )
        await event.respond(text, parse_mode="html")
        await event.delete()

    @client.on(
        events.NewMessage(
            chats=context.settings.group_c, pattern=r"^\.ai(?:\s+(on|off|status))?\s*$"
        )
    )
    async def ai_mode(event):
        if not context.is_admin(event.sender_id):
            return
        argument = (event.pattern_match.group(1) or "").lower()
        if argument == "on":
            available, response = await context.moderation.enable()
            if not available:
                await event.respond(
                    f"<blockquote>AI не включен: {response}</blockquote>",
                    parse_mode="html",
                )
                await event.delete()
                return
        elif argument == "off":
            context.moderation.enabled = False
        elif not argument:
            context.moderation.enabled = not context.moderation.enabled
        await event.respond(context.moderation.status_text(), parse_mode="html")
        await event.delete()

    @client.on(events.NewMessage(chats=context.settings.group_c, pattern=r"^\.fix\s*$"))
    async def fix(event):
        if not context.is_admin(event.sender_id):
            return
        if not event.message.is_reply:
            await event.message.delete()
            return
        reply = await event.message.get_reply_message()
        original = clean_text(reply.raw_text or "") if reply else ""
        fixed = await context.moderation.fix(original) if original else None
        if fixed and fixed.strip() != original.strip():
            await client.edit_message(
                context.settings.group_c,
                reply.id,
                f"{format_post_html(fixed, context.rules)}\n\n{WATERMARK}",
                parse_mode="html",
            )
        await event.message.delete()
