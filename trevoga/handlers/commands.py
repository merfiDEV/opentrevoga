import html

from telethon import events

from trevoga.config import save_ai_model
from trevoga.handlers.context import HandlerContext
from trevoga.services.text_cleaner import WATERMARK, clean_text, format_post_html


HELP_TEXT = """<blockquote>=== КОМАНДЫ АДМИНИСТРАТОРА ===

.ai | .ai on | .ai off | .ai status | .ai set [MODEL]
.fix | .fix short | .fix urgent | .fix official | .fix neutral
.stats | .stats 12 | .stats 24
.ai_reason [MESSAGE_ID] или ответом на сообщение
.отмена | .delete | .удалить
.help</blockquote>"""


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
            chats=context.settings.group_c,
            pattern=r"^\.ai(?:\s+(on|off|status|set)(?:\s+(.+))?)?\s*$",
        )
    )
    async def ai_mode(event):
        if not context.is_admin(event.sender_id):
            return
        argument = (event.pattern_match.group(1) or "").lower()
        model = event.pattern_match.group(2)
        if argument == "set":
            try:
                parts = model.split() if model else []
                fix = bool(parts) and parts[-1].lower() == "fix"
                if fix:
                    parts.pop()
                selected_model = " ".join(parts).strip()
                if not selected_model:
                    models = await context.moderation.list_models(fix)
                    if not models:
                        response = (
                            "<blockquote>Доступные модели не найдены</blockquote>"
                        )
                    else:
                        response = (
                            "<blockquote>Доступные модели:\n"
                            + "\n".join(
                                f"{index}. {html.escape(name)}"
                                for index, name in enumerate(models, 1)
                            )
                            + "</blockquote>"
                        )
                elif len(parts) > 1:
                    response = "<blockquote>Формат: .ai set MODEL [fix]</blockquote>"
                elif await context.moderation.set_model(selected_model, fix):
                    save_ai_model(selected_model, fix)
                    response = (
                        f"<blockquote>Модель {'fix' if fix else 'AI'} изменена на: "
                        f"{html.escape(selected_model)}</blockquote>"
                    )
                else:
                    response = (
                        "<blockquote>Такой модели нет в списке доступных</blockquote>"
                    )
            except Exception as error:
                response = f"<blockquote>Не удалось получить модели: {html.escape(str(error))}</blockquote>"
            await event.respond(response, parse_mode="html")
            await event.delete()
            return
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
            if context.moderation.enabled:
                context.moderation.enabled = False
            else:
                available, response = await context.moderation.enable()
                if not available:
                    await event.respond(
                        f"<blockquote>AI не включен: {response}</blockquote>",
                        parse_mode="html",
                    )
                    await event.delete()
                    return
        await event.respond(context.moderation.status_text(), parse_mode="html")
        await event.delete()

    @client.on(
        events.NewMessage(
            chats=context.settings.group_c,
            pattern=r"^\.fix(?:\s+(short|urgent|official|neutral))?\s*$",
        )
    )
    async def fix(event):
        if not context.is_admin(event.sender_id):
            return
        if not event.message.is_reply:
            await event.message.delete()
            return
        reply = await event.message.get_reply_message()
        original = clean_text(reply.raw_text or "") if reply else ""
        mode = (event.message.raw_text or "").strip().split(maxsplit=1)
        fix_mode = mode[1].lower() if len(mode) > 1 else "default"
        fixed = await context.moderation.fix(original, fix_mode) if original else None
        if fixed and fixed.strip() != original.strip():
            await client.edit_message(
                context.settings.group_c,
                reply.id,
                f"{format_post_html(fixed, context.rules)}\n\n{WATERMARK}",
                parse_mode="html",
            )
        await event.message.delete()

    @client.on(
        events.NewMessage(chats=context.settings.group_c, pattern=r"^\.help\s*$")
    )
    async def help_command(event):
        if context.is_admin(event.sender_id):
            await event.respond(HELP_TEXT, parse_mode="html")
            await event.delete()

    @client.on(
        events.NewMessage(
            chats=context.settings.group_c, pattern=r"^\.ai_reason(?:\s+(\d+))?\s*$"
        )
    )
    async def ai_reason(event):
        if not context.is_admin(event.sender_id):
            return
        value = event.pattern_match.group(1)
        message_id = int(value) if value else None
        if message_id is None and event.message.is_reply:
            reply = await event.message.get_reply_message()
            message_id = reply.id if reply else None
        result = context.moderation_results.get(message_id) if message_id else None
        if not result:
            text = "<blockquote>Результат AI-проверки не найден</blockquote>"
        else:
            reason = result.reason or "нет"
            text = (
                "<blockquote>"
                f"Сообщение: {result.message_id}\n"
                f"Статус: {html.escape(result.status)}\n"
                f"Причина: {html.escape(reason)}\n"
                f"Пояснение: {html.escape(result.reason_text)}\n"
                f"Уверенность: {result.confidence if result.confidence is not None else 'нет'}"
                "</blockquote>"
            )
        await event.respond(text, parse_mode="html")
        await event.delete()
