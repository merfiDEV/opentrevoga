"""Швидкий рендер карти тревог (JPEG-фото) через теплий браузер.

v2: замість холодного subprocess-запуску Playwright на кожен /map
використовуємо singleton-рендерер з alert_map, який тримає браузер
теплим між викликами і кешує результат. Перший виклик прогріває
браузер, наступні — за ~2-3 с.

Функції:
    render_map_photo() -> bytes        (JPEG, сумісність зі старим API)
    shutdown_map_renderer() -> None    (закрити браузер при зупинці)
"""

from __future__ import annotations

from trevoga.services.alert_map import render_map_jpeg, shutdown_renderer


async def render_map_photo() -> bytes:
    """Повертає JPEG-байти карти тревог (теплий браузер + кеш).

    Raises:
        RuntimeError: якщо рендер не вдався.
    """
    return await render_map_jpeg()


async def shutdown_map_renderer() -> None:
    """Акуратно закрити теплий браузер карти при зупинці бота."""
    await shutdown_renderer()


# Зворотна сумісність зі старою назвою.
render_map_png = render_map_photo