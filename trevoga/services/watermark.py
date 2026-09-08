import asyncio
import shutil
from pathlib import Path


async def apply_watermark(source: Path, output: Path, text: str = "#OpenTrevoga") -> None:
    """Накладывает текст внизу изображения через ffmpeg."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required for image watermarking")
    drawtext = (
        f"drawtext=text='{text}':fontcolor=black:fontsize=28:"
        "x=(w-text_w)/2:y=h-th-24"
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
