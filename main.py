import asyncio
import json
import os
import re
import time
from collections import Counter

from telethon import TelegramClient, events, utils
from telethon.tl.types import UpdateMessageReactions

import config

client = TelegramClient("session", config.API_ID, config.API_HASH)
forwarded_to_d = {}
group_c_peer_id = None

STATS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stats.json")
STATS_TTL = 24 * 3600

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
]


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
            lines.append(f"{label} - {n}")
    else:
        lines.append("Ключових слів не знайдено")
    return "\n".join(lines)


def build_stats_text():
    return "=== СТАТИСТИКА ===\n\n" + build_report(12) + "\n\n" + build_report(24)


@client.on(events.NewMessage(chats=config.SOURCE_CHANNELS))
async def forward_to_group_c(event):
    msg = event.message
    source = chat_name(event.chat, str(event.chat_id))
    print(f"Received message {msg.id} from {source}")
    text = clean_text(msg.text or "")
    quoted = f"<blockquote>{text}</blockquote>" if text else ""
    lowered = text.lower()
    keywords = detect_keywords(lowered)
    attach_photos = [
        photo
        for kw_list, photo, _label in PHOTO_RULES
        if any(kw in lowered for kw in kw_list) and os.path.exists(photo)
    ]
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
        record_stat("to_c", source=source, keywords=keywords)
    except Exception as e:
        print(f"Failed to send message {msg.id} to group C: {e!r}")


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
            ref = forwarded_to_d.pop(update.msg_id, None)
            if ref:
                await client.delete_messages(ref[0], [ref[1]])
                print(
                    f"Recalled message {update.msg_id}: deleted {ref[1]} "
                    f"from group D ({config.GROUP_D})"
                )
            return

        if update.msg_id in forwarded_to_d:
            return

        msg = await client.get_messages(update.peer, ids=update.msg_id)
        if msg:
            fwd = await msg.forward_to(config.GROUP_D)
            forwarded_to_d[update.msg_id] = (fwd.chat_id, fwd.id)
            record_stat("to_d", msg_id=update.msg_id)
            print(
                f"Forwarded message {msg.id} from group C to group D "
                f"({config.GROUP_D}) by reaction"
            )
        else:
            print(f"Message {update.msg_id} not found in group C")
    except Exception as e:
        print(f"Error handling reaction: {e!r}")


@client.on(events.NewMessage(chats=config.GROUP_C, pattern=r"^\.stats$"))
async def show_stats(event):
    try:
        await event.respond(build_stats_text())
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
