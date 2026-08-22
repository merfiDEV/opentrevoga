import asyncio
import json
import os
import re
import time
from collections import Counter
from html import escape

from telethon import TelegramClient, events, utils
from telethon.tl.types import UpdateMessageReactions

import config

client = TelegramClient(
    "session", config.API_ID, config.API_HASH, catch_up=True
)
forwarded_to_d = {}
group_c_peer_id = None

STATS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    os.getenv("STATS_FILE_NAME", "stats.json"),
)
STATS_TTL = 24 * 3600

WATERMARK = "OpenTrevoga 🕊"

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F000-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U00002B00-\U00002BFF"
    "\U0001F1E6-\U0001F1FF"
    "\uFE00-\uFE0F"
    "\u200D"
    "\u20E3"
    "]+"
)


LINK_PATTERN = re.compile(r"(?:https?://|www\.|t\.me/)\S+", re.IGNORECASE)
FOOTER_LINES = {"донецька сова", "чат", "підтримати"}

PHOTO_RULES = [
    (
        ("бпла", "шахед", "шахеди", "шахеді", "реактивні"),
        r"D:\code\trevoga\asseti\photo_2026-08-22_14-29-40.jpg",
        "БПЛА/Шахеди",
    ),
    (
        ("каб", "каби", "бандероль", "баражуючі боєприпаси"),
        r"D:\code\trevoga\asseti\cab.jpg",
        "Каби",
    ),
    (("рсзв", "рсзо"), r"D:\code\trevoga\asseti\rszo.jpg", "РСЗВ/РСЗО"),
    (("фпв", "fpv"), r"D:\code\trevoga\asseti\fpv.jpg", "FPV"),
    (("швидкісна",), r"D:\code\trevoga\asseti\svidkisna.jpg", "Швидкісна ціль"),
    (
        ("балістичн", "балістик", "балістичні", "балістична", "балістика"),
        r"D:\code\trevoga\asseti\ballistika.jpg",
        "Балістичні ракети",
    ),
]

_ALL_KEYWORDS = sorted(
    {kw for kw_list, _photo, _label in PHOTO_RULES for kw in kw_list},
    key=len,
    reverse=True,
)
KEYWORD_RE = re.compile(
    r"(?<![\w-])(" + "|".join(re.escape(kw) for kw in _ALL_KEYWORDS) + r")(?![\w-])",
    re.IGNORECASE,
)


def format_post_html(text):
    escaped = escape(text).strip()
    if not escaped:
        return ""
    bolded = KEYWORD_RE.sub(r"<b>\1</b>", escaped)
    return f"<blockquote>{bolded}</blockquote>"


def clean_text(text):
    kept = []
    for line in text.splitlines():
        if LINK_PATTERN.search(line):
            continue
        stripped = EMOJI_PATTERN.sub("", line).strip()
        if not stripped or stripped.lower() in FOOTER_LINES:
            continue
        kept.append(stripped)
    result = "\n".join(kept)
    return re.sub(r"\n{3,}", "\n\n", result).strip()


def detect_keywords(lowered):
    found = []
    for keywords, _, label in PHOTO_RULES:
        if any(kw in lowered for kw in keywords) and label not in found:
            found.append(label)
    return found


def quote_html(text):
    t = escape(text).strip()
    return f"<blockquote>{t}</blockquote>" if t else ""


def chat_name(chat, fallback=""):
    username = getattr(chat, "username", None)
    if username:
        return f"@{username}"
    title = getattr(chat, "title", None)
    if title:
        return title
    return fallback or str(getattr(chat, "id", "?"))


def load_stats():
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {"to_c": [], "to_d": []}
    cutoff = time.time() - STATS_TTL
    for key in ("to_c", "to_d"):
        entries = [e for e in data.get(key, []) if isinstance(e, dict)]
        data[key] = [e for e in entries if e.get("ts", 0) >= cutoff]
    return data


def save_stats(data):
    tmp = STATS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, STATS_FILE)


def record_stat(kind, **entry):
    try:
        data = load_stats()
        entry["ts"] = time.time()
        data.setdefault(kind, []).append(entry)
        save_stats(data)
    except Exception as e:
        print(f"Stats error: {e!r}")


def build_report(hours):
    data = load_stats()
    cutoff = time.time() - hours * 3600
    c_entries = [e for e in data["to_c"] if e.get("ts", 0) >= cutoff]
    counter = Counter(kw for e in c_entries for kw in e.get("keywords", []))
    lines = [f"--- За {hours} год ---"]
    if counter:
        for label, n in counter.most_common():
            lines.append(f"<b>{label}</b> - {n}")
    else:
        lines.append("Ключових слів не знайдено")
    return "\n".join(lines)


def build_stats_text():
    body = build_report(12) + "\n\n" + build_report(24)
    return (
        f"<blockquote>=== СТАТИСТИКА ===\n\n{body}\n\n{WATERMARK}</blockquote>"
    )


async def delete_entry(entry):
    ids_by_target = {}
    for target, msg_id in (entry.get("main") or {}).items():
        ids_by_target.setdefault(target, []).append(msg_id)
    comments = entry.get("comments", [])
    if comments and isinstance(comments[0], tuple):
        for target, msg_id in comments:
            ids_by_target.setdefault(target, []).append(msg_id)
    else:
        first_target = next(iter(entry.get("main") or {config.GROUP_D_TARGETS[0]: 0}))
        ids_by_target.setdefault(first_target, []).extend(comments)

    deleted = 0
    for target, ids in ids_by_target.items():
        try:
            await client.delete_messages(target, ids)
            deleted += len(ids)
        except Exception as e:
            print(f"Failed to delete messages in {target}: {e!r}")
    return deleted


@client.on(events.NewMessage(chats=config.SOURCE_CHANNELS))
async def forward_to_group_c(event):
    msg = event.message
    source = chat_name(event.chat, str(event.chat_id))
    print(f"Received message {msg.id} from {source}")
    text = clean_text(msg.raw_text or "")
    body = format_post_html(text)
    lowered = text.lower()
    keywords = detect_keywords(lowered)
    attach_photos = [
        photo
        for kw_list, photo, _label in PHOTO_RULES
        if any(kw in lowered for kw in kw_list) and os.path.exists(photo)
    ]
    if body:
        quoted = f"{body}\n\n{WATERMARK}"
    elif attach_photos or msg.media:
        quoted = WATERMARK
    else:
        quoted = ""
    record_stat("to_c", source=source, keywords=keywords)
    try:
        if attach_photos:
            await client.send_file(
                config.GROUP_C,
                attach_photos,
                caption=quoted,
                parse_mode="html",
            )
            print(f"Attached {len(attach_photos)} photo(s) to message {msg.id}")
        elif msg.media:
            await client.send_file(
                config.GROUP_C, msg.media, caption=quoted, parse_mode="html"
            )
        else:
            await client.send_message(config.GROUP_C, quoted, parse_mode="html")
        print(f"Forwarded message {msg.id} from {source} to group C ({config.GROUP_C})")
    except Exception as e:
        print(f"Failed to send message {msg.id} to group C: {e!r}")


@client.on(events.NewMessage(chats=config.GROUP_C))
async def handle_comment(event):
    msg = event.message
    raw = (msg.raw_text or "").strip().lower()
    if not msg.is_reply or raw == ".stats":
        return

    if raw in {".отмена", ".delete", ".удалить"}:
        try:
            orig = await msg.get_reply_message()
            entry = forwarded_to_d.pop(orig.id, None) if orig else None
            if entry:
                deleted = await delete_entry(entry)
                print(
                    f"Manual recall of {orig.id}: deleted {deleted} "
                    f"message(s) across D targets"
                )
            else:
                print(f"Manual recall: nothing sent for message {orig.id if orig else '?'}")
            await msg.delete()
        except Exception as e:
            print(f"Recall command error: {e!r}")
        return

    comment = clean_text(msg.raw_text or "")
    if not comment:
        return
    try:
        orig = await msg.get_reply_message()
        if not orig:
            return

        orig_text = clean_text(orig.raw_text or "")
        orig_quote = quote_html(orig_text)
        comment_quote = quote_html(comment)

        parts = []
        if orig_quote:
            parts.append(orig_quote)
        parts.append(f"Доп коммент.\n{comment_quote}")
        combined = "\n\n".join(parts) + f"\n\n{WATERMARK}"

        entry = {"main": {}, "comments": []}
        for target in config.GROUP_D_TARGETS:
            try:
                if orig.media:
                    sent = await client.send_file(
                        target, orig.media, caption=combined, parse_mode="html"
                    )
                else:
                    sent = await client.send_message(
                        target, combined, parse_mode="html"
                    )
                entry["main"][target] = sent.id
            except Exception as e:
                print(f"Failed to deliver comment to {target}: {e!r}")

        old = forwarded_to_d.get(orig.id)
        if old:
            old["main"].update(
                {t: m for t, m in entry["main"].items() if t not in old["main"]}
            )
            old["comments"].extend(entry["comments"])
        else:
            forwarded_to_d[orig.id] = entry

        record_stat("to_d", msg_id=orig.id)
        print(
            f"Comment on message {orig.id} delivered to D targets "
            f"({len(config.GROUP_D_TARGETS)})"
        )
    except Exception as e:
        print(f"Error handling comment: {e!r}")


@client.on(events.Raw())
async def handle_reactions(update):
    if not isinstance(update, UpdateMessageReactions):
        return
    try:
        if group_c_peer_id is None or utils.get_peer_id(update.peer) != group_c_peer_id:
            return

        total = sum(r.count for r in update.reactions.results)
        print(f"Reaction update in group C, msg {update.msg_id}, total={total}")

        if total == 0:
            entry = forwarded_to_d.pop(update.msg_id, None)
            if entry:
                deleted = await delete_entry(entry)
                print(
                    f"Recalled message {update.msg_id}: deleted {deleted} "
                    f"message(s) across D targets"
                )
            return

        if update.msg_id in forwarded_to_d:
            return

        msg = await client.get_messages(update.peer, ids=update.msg_id)
        if msg:
            main_refs = {}
            for target in config.GROUP_D_TARGETS:
                try:
                    fwd = await msg.forward_to(target)
                    main_refs[target] = fwd.id
                except Exception as e:
                    print(f"Failed to forward to {target}: {e!r}")
            forwarded_to_d[update.msg_id] = {
                "main": main_refs,
                "comments": [],
            }
            record_stat("to_d", msg_id=update.msg_id)
            print(
                f"Forwarded message {msg.id} from group C to "
                f"{len(main_refs)}/{len(config.GROUP_D_TARGETS)} D targets by reaction"
            )
        else:
            print(f"Message {update.msg_id} not found in group C")
    except Exception as e:
        print(f"Error handling reaction: {e!r}")


@client.on(events.NewMessage(pattern=r"^\.stat(?:s)?(?:\s+(\d+))?$"))
async def show_stats(event):
    try:
        hours_str = event.pattern_match.group(1)
        if hours_str:
            hours = int(hours_str)
            if 1 <= hours <= 24:
                text = (
                    "<blockquote>"
                    + build_report(hours)
                    + f"\n\n{WATERMARK}"
                    + "</blockquote>"
                )
            else:
                text = "<blockquote>Введіть від 1 до 24</blockquote>"
        else:
            text = build_stats_text()
        await event.respond(text, parse_mode="html")
        await event.delete()
        print(f"Stats sent on request from {event.sender_id}")
    except Exception as e:
        print(f"Stats command error: {e!r}")


async def stats_cleanup_loop():
    while True:
        await asyncio.sleep(1800)
        try:
            save_stats(load_stats())
            print("Stats cleanup done")
        except Exception as e:
            print(f"Stats cleanup error: {e!r}")


async def main():
    global group_c_peer_id
    await client.start()

    print("Caching entities (dialogs)...")
    async for _dialog in client.iter_dialogs():
        pass

    try:
        entity = await client.get_entity(config.GROUP_C)
    except ValueError:
        entity = None
        async for d in client.iter_dialogs():
            if d.id == config.GROUP_C:
                entity = d.entity
                break

    group_c_peer_id = utils.get_peer_id(entity)
    print(f"Watching group C ({group_c_peer_id}) for reactions...")
    print("Bot started. Listening for messages and reactions...")
    asyncio.create_task(stats_cleanup_loop())
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
