import html

from telethon import events

from trevoga.config import save_ai_model, save_ignored_channels, save_watermark
from trevoga.handlers.context import HandlerContext
from trevoga.services.fix_service import (
    RESULT_ERROR,
    RESULT_OK,
    RESULT_TOO_LONG,
    RESULT_UNCHANGED,
)
from trevoga.services.text_cleaner import (
    clean_text,
    format_post_html,
    is_watermark_enabled,
    quote_html,
    set_watermark,
    watermark,
)


HELP_TEXT = """<blockquote>=== КОМАНДЫ АДМИНИСТРАТОРА ===

.ai | .ai on | .ai off | .ai status | .ai set [MODEL]
.wmark | .wmark on | .wmark off
.cignore [ID or @name] | .cignore off | .cignore list
.fix [short|urgent|official|neutral] | .fix test | .fix <просьба> | .fix undo | .fix help
.stats | .stats 12 | .stats 24
.ai_reason [MESSAGE_ID] или ответом на сообщение
.отмена | .delete | .удалить
.help

=== КОМАНДЫ ПОДПИСКИ ===

.sub [СЛОВО] — подписаться на ключевое слово
.unsub [СЛОВО] — отписаться от ключевого слова
.unsub all — сбросить все подписки</blockquote>"""


FIX_HELP = """<blockquote>=== .fix ===
.fix — отредактировать ответом (режим default)
.fix short|urgent|official|neutral — стиль редактуры
.fix test [режим] [просьба] — показать результат, не меняя пост
.fix [просьба] — своя инструкция редактору (напр. «убери мат»)
.fix undo — вернуть исходный текст (в течение 10 минут)
.fix help — эта справка</blockquote>"""


async def _undo_fix(client, context, event):
    if not event.message.is_reply:
        await event.respond(
            "<blockquote>⚠️ Ответьте .fix undo на отредактированное сообщение.</blockquote>",
            parse_mode="html",
        )
        await event.delete()
        return
    reply = await event.message.get_reply_message()
    saved = context.fixer.pop_undo(reply.id) if reply else None
    if saved is None:
        await event.respond(
            "<blockquote>ℹ️ Нет сохранённой версии для отката (или истёк срок).</blockquote>",
            parse_mode="html",
        )
        await event.delete()
        return
    restored = f"{format_post_html(saved, context.rules)}"
    mark = watermark()
    full = f"{restored}\n\n{mark}" if mark else restored
    try:
        await client.edit_message(
            context.settings.group_c,
            reply.id,
            full,
            parse_mode="html",
            link_preview=False,
        )
        await event.respond(
            "<blockquote>↩️ Восстановлен исходный текст.</blockquote>",
            parse_mode="html",
        )
    except Exception as error:
        await event.respond(
            f"<blockquote>⚠️ Не удалось откатить: {html.escape(str(error))}</blockquote>",
            parse_mode="html",
        )
    await event.delete()


async def _render_fix_outcome(
    client, context, event, reply, original, mode, outcome, preview
):
    if outcome.status == RESULT_ERROR:
        detail = f": {html.escape(outcome.error)}" if outcome.error else ""
        return f"<blockquote>⚠️ AI-редактор недоступен{detail}</blockquote>"
    if outcome.status == RESULT_UNCHANGED:
        return "<blockquote>ℹ️ Текст уже в порядке, изменений нет.</blockquote>"
    if outcome.status == RESULT_TOO_LONG:
        return "<blockquote>⚠️ Результат слишком длинный для этого сообщения.</blockquote>"
    limit = context.fixer.limits_for(reply)
    rendered = f"{format_post_html(outcome.text, context.rules)}"
    mark = watermark()
    full = f"{rendered}\n\n{mark}" if mark else rendered
    if len(full) > limit:
        return (
            "<blockquote>⚠️ Результат не влезает в лимит сообщения "
            f"({len(full)}/{limit}). Попробуйте .fix test.</blockquote>"
        )
    if preview:
        return f"<blockquote>🔎 Предпросмотр ({html.escape(mode)}):</blockquote>{full}"
    context.fixer.remember(reply.id, original)
    try:
        await client.edit_message(
            context.settings.group_c,
            reply.id,
            full,
            parse_mode="html",
            link_preview=False,
        )
    except Exception as error:
        return f"<blockquote>⚠️ Не удалось изменить пост: {html.escape(str(error))}</blockquote>"
    return f"<blockquote>✅ Исправлено (режим: {html.escape(mode)})</blockquote>"


def register(client, context: HandlerContext):
    @client.on(
        events.NewMessage(
            chats=context.settings.group_c,
            pattern=r"^\.cignore(?:\s+(.+))?\s*$",
        )
    )
    async def channel_ignore(event):
        if not context.is_admin(event.sender_id):
            return
        value = (event.pattern_match.group(1) or "").strip()
        if not value or value.lower() == "list":
            channels = sorted(context.ignored_channels)
            response = "Игнорируемые каналы: " + (
                ", ".join(map(str, channels)) if channels else "нет"
            )
        elif value.lower() == "off":
            context.ignored_channels.clear()
            save_ignored_channels(tuple())
            response = "Игнорирование каналов выключено"
        else:
            try:
                target = int(value) if value.lstrip("-").isdigit() else value
                entity = await client.get_entity(target)
                from telethon import utils

                channel_id = utils.get_peer_id(entity)
                context.ignored_channels.add(channel_id)
                save_ignored_channels(tuple(sorted(context.ignored_channels)))
                response = f"Канал добавлен в исключения: {channel_id}"
            except Exception as error:
                response = f"Не удалось найти канал: {html.escape(str(error))}"
        await event.respond(f"<blockquote>{response}</blockquote>", parse_mode="html")
        await event.delete()

    @client.on(events.NewMessage(pattern=r"^\.stat(?:s)?(?:\s+(\d+))?$"))
    async def stats(event):
        if not context.is_admin(event.sender_id):
            return
        value = event.pattern_match.group(1)
        hours = int(value) if value else None
        text = (
            context.statistics.build_text()
            if hours is None
            else f"<blockquote>{context.statistics.build_report(hours)}\n\n{watermark()}</blockquote>"
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
            chats=context.settings.group_c, pattern=r"^\.wmark(?:\s+(on|off))?\s*$"
        )
    )
    async def watermark_command(event):
        if not context.is_admin(event.sender_id):
            return
        value = event.pattern_match.group(1)
        enabled = (value == "on") if value else not is_watermark_enabled()
        set_watermark(enabled)
        save_watermark(enabled)
        await event.respond(
            f"<blockquote>Ссылка в ватермарке: {'включена ✅' if is_watermark_enabled() else 'выключена ❌'}</blockquote>",
            parse_mode="html",
        )
        await event.delete()

    @client.on(
        events.NewMessage(
            chats=context.settings.group_c, pattern=r"^\.fix(?:\s+(.+))?\s*$"
        )
    )
    async def fix(event):
        if not context.is_admin(event.sender_id):
            return
        argument = (event.pattern_match.group(1) or "").strip()
        if argument.lower() in {"help", "?"}:
            await event.respond(FIX_HELP, parse_mode="html")
            await event.delete()
            return
        if argument.lower() == "undo":
            await _undo_fix(client, context, event)
            return
        if not event.message.is_reply:
            await event.respond(
                "<blockquote>⚠️ Ответьте командой .fix на сообщение, которое нужно отредактировать.</blockquote>",
                parse_mode="html",
            )
            await event.delete()
            return
        reply = await event.message.get_reply_message()
        if reply is None:
            await event.respond(
                "<blockquote>⚠️ Не удалось получить исходное сообщение.</blockquote>",
                parse_mode="html",
            )
            await event.delete()
            return
        original = clean_text(reply.raw_text or "")
        mode, instruction, preview = context.fixer.parse_args(argument)
        outcome = await context.fixer.run(original, mode, instruction)
        status = await _render_fix_outcome(
            client, context, event, reply, original, mode, outcome, preview
        )
        if status:
            await event.respond(status, parse_mode="html")
        await event.delete()

    @client.on(
        events.NewMessage(chats=context.settings.group_c, pattern=r"^\.help\s*$")
    )
    async def help_command(event):
        await event.respond(HELP_TEXT, parse_mode="html")
        await event.delete()

    @client.on(events.NewMessage(pattern=r"^\.sub(?:\s+(.+))?\s*$"))
    async def subscribe(event):
        if event.sender_id is None:
            return
        value = (event.pattern_match.group(1) or "").strip()
        if not value:
            keywords = context.subscriptions.list_for_user(event.sender_id)
            text = (
                "<blockquote>Ваши подписки: "
                + (", ".join(html.escape(word) for word in keywords) if keywords else "нет")
                + "\n\n📌 Можно подписываться на типы вооружения "
                + "(бпла, каб, рсзв, fpv, ракета, балістика, арта) "
                + "или на свой город (краматорськ, покровськ, бахмут тощо)"
                + "</blockquote>"
            )
        else:
            normalized = value.lower()
            context.subscriptions.add(event.sender_id, normalized)
            text = f"<blockquote>Подписка на «{html.escape(normalized)}» добавлена</blockquote>"
        await event.respond(text, parse_mode="html")
        await event.delete()

    @client.on(events.NewMessage(pattern=r"^\.unsub(?:\s+(.+))?\s*$"))
    async def unsubscribe(event):
        if event.sender_id is None:
            return
        value = (event.pattern_match.group(1) or "").strip()
        if not value:
            text = "<blockquote>Формат: .unsub СЛОВО | .unsub all</blockquote>"
        elif value.lower() == "all":
            removed = context.subscriptions.remove_all(event.sender_id)
            text = f"<blockquote>Сброшено подписок: {removed}</blockquote>"
        else:
            normalized = value.lower()
            if context.subscriptions.remove(event.sender_id, normalized):
                text = f"<blockquote>Подписка на «{html.escape(normalized)}» удалена</blockquote>"
            else:
                text = f"<blockquote>Подписка на «{html.escape(normalized)}» не найдена</blockquote>"
        await event.respond(text, parse_mode="html")
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
