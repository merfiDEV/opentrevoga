import asyncio
import os
import re
from telethon import TelegramClient, events, utils
from telethon.tl.types import UpdateMessageReactions
import config

client = TelegramClient("session", config.API_ID, config.API_HASH)
forwarded_liked_messages = set()
group_c_peer_id = None

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
    (("бпла", "шахед", "шахеди", "шахеді", "реактивні"), r"D:\code\trevoga\asseti\photo_2026-08-22_14-29-40.jpg"),
    (
        ("каб", "каби", "бандероль", "баражуючі боєприпаси"),
        r"D:\code\trevoga\asseti\cab.jpg",
    ),
    (("рсзв", "рсзо"), r"D:\code\trevoga\asseti\rszo.jpg"),
    (("фпв", "fpv"), r"D:\code\trevoga\asseti\fpv.jpg"),
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


def chat_name(chat, fallback=""):
    username = getattr(chat, "username", None)
    if username:
        return f"@{username}"
    title = getattr(chat, "title", None)
    if title:
        return title
    return fallback or str(getattr(chat, "id", "?"))


@client.on(events.NewMessage(chats=config.SOURCE_CHANNELS))
async def forward_to_group_c(event):
    msg = event.message
    source = chat_name(event.chat, str(event.chat_id))
    print(f"Received message {msg.id} from {source}")
    text = clean_text(msg.text or "")
    quoted = f"<blockquote>{text}</blockquote>" if text else ""
    lowered = text.lower()
    attach_photo = None
    for keywords, photo in PHOTO_RULES:
        if any(kw in lowered for kw in keywords) and os.path.exists(photo):
            attach_photo = photo
            break
    try:
        if attach_photo:
            await client.send_file(
                config.GROUP_C, attach_photo, caption=quoted, parse_mode="html"
            )
            print(f"Attached photo {attach_photo} to message {msg.id}")
        elif msg.media:
            await client.send_file(
                config.GROUP_C, msg.media, caption=quoted, parse_mode="html"
            )
        else:
            await client.send_message(config.GROUP_C, quoted, parse_mode="html")
        print(f"Forwarded message {msg.id} from {source} to group C ({config.GROUP_C})")
    except Exception as e:
        print(f"Failed to send message {msg.id} to group C: {e!r}")


@client.on(events.Raw())
async def handle_reactions(update):
    if not isinstance(update, UpdateMessageReactions):
        return
    try:
        if group_c_peer_id is None or utils.get_peer_id(update.peer) != group_c_peer_id:
            return

        has_reaction = any(r.count > 0 for r in update.reactions.results)
        print(f"Reaction update in group C, msg {update.msg_id}, reaction={has_reaction}")

        if not has_reaction or update.msg_id in forwarded_liked_messages:
            return

        msg = await client.get_messages(update.peer, ids=update.msg_id)
        if msg:
            await msg.forward_to(config.GROUP_D)
            forwarded_liked_messages.add(update.msg_id)
            print(f"Forwarded message {msg.id} from group C to group D ({config.GROUP_D}) by reaction")
        else:
            print(f"Message {update.msg_id} not found in group C")
    except Exception as e:
        print(f"Error handling reaction: {e!r}")


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
    print(f"Watching group C ({group_c_peer_id}) for heart reactions...")
    print("Bot started. Listening for messages and reactions...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
