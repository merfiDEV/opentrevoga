import html
from datetime import datetime

from telethon import events

from trevoga import health, i18n
from trevoga.config import (
    save_aicheck,
    save_ai_model,
    save_ignored_channels,
    save_watermark,
)
from trevoga.handlers.context import HandlerContext
from trevoga.handlers.decorators import command
from trevoga.services.fix_service import (
    RESULT_ERROR,
    RESULT_TOO_LONG,
    RESULT_UNCHANGED,
)
from trevoga.services.text_cleaner import (
    clean_text,
    is_watermark_enabled,
    render_post,
    set_watermark,
    watermark,
)


async def _undo_fix(client, context, event):
    if not event.message.is_reply:
        await event.respond(i18n.FIX_NEED_REPLY_UNDO, parse_mode="html")
        return
    reply = await event.message.get_reply_message()
    saved = context.fixer.pop_undo(reply.id) if reply else None
    if saved is None:
        await event.respond(i18n.FIX_UNDO_MISSING, parse_mode="html")
        return
    full = render_post(saved, context.rules)
    try:
        await client.edit_message(
            context.settings.group_c,
            reply.id,
            full,
            parse_mode="html",
            link_preview=False,
        )
        await event.respond(i18n.FIX_UNDO_DONE, parse_mode="html")
    except Exception as error:
        await event.respond(
            i18n.FIX_UNDO_FAILED.format(error=html.escape(str(error))),
            parse_mode="html",
        )


async def _render_fix_outcome(client, context, event, reply, original, mode, outcome, preview):
    if outcome.status == RESULT_ERROR:
        detail = f": {html.escape(outcome.error)}" if outcome.error else ""
        return i18n.FIX_AI_UNAVAILABLE.format(detail=detail)
    if outcome.status == RESULT_UNCHANGED:
        return i18n.FIX_UNCHANGED
    if outcome.status == RESULT_TOO_LONG:
        return i18n.FIX_TOO_LONG
    limit = context.fixer.limits_for(reply)
    full = render_post(outcome.text, context.rules)
    if len(full) > limit:
        return i18n.FIX_OVERFLOW.format(length=len(full), limit=limit)
    if preview:
        return i18n.FIX_PREVIEW.format(mode=html.escape(mode), body=full)
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
        return i18n.FIX_EDIT_FAILED.format(error=html.escape(str(error)))
    return i18n.FIX_DONE.format(mode=html.escape(mode))


def register(client, context: HandlerContext):
    @client.on(
        events.NewMessage(
            chats=context.settings.group_c,
            pattern=r"^\.cignore(?:\s+(.+))?\s*$",
        )
    )
    @command(context, admin=True)
    async def channel_ignore(event):
        value = (event.pattern_match.group(1) or "").strip()
        if not value or value.lower() == "list":
            channels = sorted(context.ignored_channels)
            response = i18n.CIGNORE_LIST.format(
                channels=", ".join(map(str, channels)) if channels else i18n.CIGNORE_NONE
            )
        elif value.lower() == "off":
            context.ignored_channels.clear()
            save_ignored_channels(tuple())
            response = i18n.CIGNORE_OFF
        else:
            try:
                target = int(value) if value.lstrip("-").isdigit() else value
                entity = await client.get_entity(target)
                from telethon import utils

                channel_id = utils.get_peer_id(entity)
                context.ignored_channels.add(channel_id)
                save_ignored_channels(tuple(sorted(context.ignored_channels)))
                response = i18n.CIGNORE_ADDED.format(channel_id=channel_id)
            except Exception as error:
                response = i18n.CIGNORE_NOT_FOUND.format(error=html.escape(str(error)))
        await event.respond(f"<blockquote>{response}</blockquote>", parse_mode="html")

    @client.on(events.NewMessage(pattern=r"^\.stat(?:s)?(?:\s+(\d+))?$"))
    @command(context, admin=True)
    async def stats(event):
        value = event.pattern_match.group(1)
        hours = int(value) if value else None
        text = (
            context.statistics.build_text()
            if hours is None
            else f"<blockquote>{context.statistics.build_report(hours)}\n\n{watermark()}</blockquote>"
        )
        await event.respond(text, parse_mode="html")

    @client.on(
        events.NewMessage(
            chats=context.settings.group_c,
            pattern=r"^\.ai(?:\s+(on|off|status|set)(?:\s+(.+))?)?\s*$",
        )
    )
    @command(context, admin=True)
    async def ai_mode(event):
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
                        response = i18n.AI_NO_MODELS
                    else:
                        response = i18n.AI_MODELS_LIST.format(
                            models="\n".join(
                                f"{index}. {html.escape(name)}"
                                for index, name in enumerate(models, 1)
                            )
                        )
                elif len(parts) > 1:
                    response = i18n.AI_SET_FORMAT
                elif await context.moderation.set_model(selected_model, fix):
                    save_ai_model(selected_model, fix)
                    response = i18n.AI_MODEL_CHANGED.format(
                        scope="fix" if fix else "AI",
                        model=html.escape(selected_model),
                    )
                else:
                    response = i18n.AI_MODEL_UNKNOWN
            except Exception as error:
                response = i18n.AI_MODELS_FAILED.format(error=html.escape(str(error)))
            await event.respond(response, parse_mode="html")
            return
        if argument == "on":
            available, response = await context.moderation.enable()
            if not available:
                await event.respond(i18n.AI_ENABLE_FAILED.format(error=response), parse_mode="html")
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
                        i18n.AI_ENABLE_FAILED.format(error=response), parse_mode="html"
                    )
                    return
        await event.respond(context.moderation.status_text(), parse_mode="html")

    @client.on(
        events.NewMessage(chats=context.settings.group_c, pattern=r"^\.wmark(?:\s+(on|off))?\s*$")
    )
    @command(context, admin=True)
    async def watermark_command(event):
        value = event.pattern_match.group(1)
        enabled = (value == "on") if value else not is_watermark_enabled()
        set_watermark(enabled)
        save_watermark(enabled)
        await event.respond(
            i18n.WMARK_ON if is_watermark_enabled() else i18n.WMARK_OFF,
            parse_mode="html",
        )

    @client.on(
        events.NewMessage(
            chats=context.settings.group_c,
            pattern=r"^\.aicheck(?:\s+(on|off|status))?\s*$",
        )
    )
    @command(context, admin=True)
    async def aicheck(event):
        argument = (event.pattern_match.group(1) or "").lower()
        if argument == "on":
            context.fixer.autocheck_enabled = True
        elif argument == "off":
            context.fixer.autocheck_enabled = False
        elif not argument:
            context.fixer.autocheck_enabled = not context.fixer.autocheck_enabled
        save_aicheck(context.fixer.autocheck_enabled)
        await event.respond(
            i18n.AICHECK_ON if context.fixer.autocheck_enabled else i18n.AICHECK_OFF,
            parse_mode="html",
        )

    @client.on(events.NewMessage(chats=context.settings.group_c, pattern=r"^\.fix(?:\s+(.+))?\s*$"))
    @command(context, admin=True)
    async def fix(event):
        argument = (event.pattern_match.group(1) or "").strip()
        if argument.lower() in {"help", "?"}:
            await event.respond(i18n.FIX_HELP, parse_mode="html")
            return
        if argument.lower() == "undo":
            await _undo_fix(client, context, event)
            return
        if not event.message.is_reply:
            await event.respond(i18n.FIX_NEED_REPLY, parse_mode="html")
            return
        reply = await event.message.get_reply_message()
        if reply is None:
            await event.respond(i18n.FIX_NO_SOURCE, parse_mode="html")
            return
        original = clean_text(reply.raw_text or "")
        mode, instruction, preview = context.fixer.parse_args(argument)
        outcome = await context.fixer.run(original, mode, instruction)
        status = await _render_fix_outcome(
            client, context, event, reply, original, mode, outcome, preview
        )
        if status:
            await event.respond(status, parse_mode="html")

    @client.on(events.NewMessage(chats=context.settings.group_c, pattern=r"^\.help\s*$"))
    @command(context)
    async def help_command(event):
        await event.respond(i18n.HELP_TEXT, parse_mode="html")

    @client.on(events.NewMessage(chats=context.settings.group_c, pattern=r"^\.health\s*$"))
    @command(context, admin=True)
    async def health_command(event):
        available, response = await context.moderation.check_available()
        ai_status = (
            i18n.HEALTH_AI_OK
            if available
            else i18n.HEALTH_AI_DOWN.format(error=html.escape(str(response)))
        )
        try:
            db_size = health.format_bytes(context.settings.database_path.stat().st_size)
        except OSError:
            db_size = i18n.HEALTH_DB_MISSING
        message, timestamp = health.last_error()
        if message:
            when = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
            last_error = f"{when} — {html.escape(message)}"
        else:
            last_error = i18n.HEALTH_NO_ERROR
        await event.respond(
            i18n.HEALTH_TEXT.format(
                uptime=health.format_uptime(health.uptime_seconds()),
                ai_status=ai_status,
                floodwait=health.floodwait_count(),
                db_size=db_size,
                last_error=last_error,
            ),
            parse_mode="html",
        )

    @client.on(events.NewMessage(pattern=r"^\.sub(?:\s+(.+))?\s*$"))
    @command(context)
    async def subscribe(event):
        value = (event.pattern_match.group(1) or "").strip()
        if not value:
            keywords = context.subscriptions.list_for_user(event.sender_id)
            text = i18n.SUB_LIST.format(
                keywords=", ".join(html.escape(word) for word in keywords)
                if keywords
                else i18n.SUB_NONE
            )
        else:
            normalized = value.lower()
            context.subscriptions.add(event.sender_id, normalized)
            text = i18n.SUB_ADDED.format(word=html.escape(normalized))
        await event.respond(text, parse_mode="html")

    @client.on(events.NewMessage(pattern=r"^\.unsub(?:\s+(.+))?\s*$"))
    @command(context)
    async def unsubscribe(event):
        value = (event.pattern_match.group(1) or "").strip()
        if not value:
            text = i18n.UNSUB_FORMAT
        elif value.lower() == "all":
            removed = context.subscriptions.remove_all(event.sender_id)
            text = i18n.UNSUB_ALL.format(count=removed)
        else:
            normalized = value.lower()
            if context.subscriptions.remove(event.sender_id, normalized):
                text = i18n.UNSUB_REMOVED.format(word=html.escape(normalized))
            else:
                text = i18n.UNSUB_MISSING.format(word=html.escape(normalized))
        await event.respond(text, parse_mode="html")

    @client.on(
        events.NewMessage(chats=context.settings.group_c, pattern=r"^\.ai_reason(?:\s+(\d+))?\s*$")
    )
    @command(context, admin=True)
    async def ai_reason(event):
        value = event.pattern_match.group(1)
        message_id = int(value) if value else None
        if message_id is None and event.message.is_reply:
            reply = await event.message.get_reply_message()
            message_id = reply.id if reply else None
        result = context.moderation_results.get(message_id) if message_id else None
        if not result:
            text = i18n.AI_REASON_MISSING
        else:
            reason = result.reason or "немає"
            text = i18n.AI_REASON_TEXT.format(
                message_id=result.message_id,
                status=html.escape(result.status),
                reason=html.escape(reason),
                reason_text=html.escape(result.reason_text),
                confidence=result.confidence if result.confidence is not None else "немає",
            )
        await event.respond(text, parse_mode="html")
