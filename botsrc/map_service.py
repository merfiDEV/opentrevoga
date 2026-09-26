"""Запуск тяжкого скріншота карти тревог у окремому процесі (JPEG-фото).

Playwright з headful Chrome може падати/зависати або конфліктувати з
asyncio-loop aiogram (Proactor на Windows). Тому рендер виконується
окремим процесом через subprocess, а бот отримує готові JPEG-байти.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
TIMEOUT_SECONDS = 120

JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG"


async def render_map_photo() -> bytes:
    """Повертає JPEG-байти карти тревог (у окремому процесі).

    Raises:
        RuntimeError: якщо рендер не вдався або перевищено таймаут.
    """
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "trevoga.services.alert_map",
        "--stdout",
        cwd=str(BASE_DIR),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError as error:
        process.kill()
        await process.wait()
        raise RuntimeError("Перевищено час очікування рендера карти") from error

    is_image = stdout.startswith(JPEG_MAGIC) or stdout.startswith(PNG_MAGIC)
    if process.returncode != 0 or not is_image:
        detail = stderr.decode("utf-8", "replace").strip().splitlines()
        tail = " | ".join(detail[-3:]) if detail else f"exit code {process.returncode}"
        logger.error("Map render failed: %s", tail)
        raise RuntimeError(tail)
    return stdout


# Зворотна сумісність зі старою назвою.
render_map_png = render_map_photo