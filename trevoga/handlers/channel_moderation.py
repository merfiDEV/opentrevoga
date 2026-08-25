import asyncio
import logging
import shutil
import tempfile
from html import escape
from pathlib import Path

from telethon import events

from trevoga.services.text_cleaner import WATERMARK_TEXT, watermark


logger = logging.getLogger(__name__)
VISUAL_MEDIA_SUFFIXES = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
}


def register(client, context):
    if not context.settings.channel_moderation_enabled:
        return

    @client.on(events.NewMessage(chats=context.settings.channel_targets))
    async def reupload_admin_message(event):
        message = event.message
        # Channel posts do not reliably expose the admin sender_id. The handler is
        # restricted to configured broadcast channels and ignores its own copies.
        if message.grouped_id or WATERMARK_TEXT in (message.raw_text or ""):
            return
        try:
            await _replace_messages(client, event.chat_id, [message])
        except Exception:
            logger.exception("Failed to moderate channel message %s", message.id)

    @client.on(events.Album(chats=context.settings.channel_targets))
    async def reupload_admin_album(event):
        if any(
            WATERMARK_TEXT in (message.raw_text or "") for message in event.messages
        ):
            return
        try:
            await _replace_messages(client, event.chat_id, event.messages)
        except Exception:
            logger.exception(
                "Failed to moderate channel album %s", event.messages[0].id
            )


async def _replace_messages(client, target, messages):
    text = next((message.raw_text for message in messages if message.raw_text), "")
    caption = f"{escape(text)}\n\n{watermark()}" if text else watermark()
    media = [message for message in messages if message.media]
    if not media:
        await client.send_message(
            target, caption, parse_mode="html", link_preview=False
        )
        await client.delete_messages(target, [message.id for message in messages])
        return

    with tempfile.TemporaryDirectory(prefix="trevoga-channel-") as directory:
        outputs = []
        for message in media:
            downloaded = await client.download_media(message, file=directory)
            if not downloaded:
                raise RuntimeError(
                    f"failed to download media from message {message.id}"
                )
            source = Path(downloaded)
            if source.suffix.lower() in VISUAL_MEDIA_SUFFIXES:
                output = source.with_name(f"watermarked-{source.name}")
                await _watermark_media(source, output)
            else:
                output = source
            outputs.append(output)
        await client.send_file(
            target,
            outputs,
            caption=caption,
            parse_mode="html",
            link_preview=False,
        )
        await client.delete_messages(target, [message.id for message in messages])


async def _watermark_media(source: Path, output: Path) -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required for channel media watermarking")
    drawtext = (
        "drawtext=text='OpenTrevoga':fontcolor=white:fontsize=28:"
        "box=1:boxcolor=black@0.55:boxborderw=8:x=24:y=h-th-24"
    )
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-vf",
        drawtext,
        "-codec:a",
        "copy",
        str(output),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode:
        raise RuntimeError(stderr.decode(errors="replace")[-1000:])
