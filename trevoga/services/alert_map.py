"""Скріншот офіційної карти тривог України (map.ukrainealarm.com).

Використовує Playwright зі СПРАВЖНІМ (headful) Chrome, бо Cloudflare блокує
headless-запити та прямий доступ до api.ukrainealarm.com (403). Браузер
відкриває сторінку як реальна людина, чекає рендер карти й робить скріншот.

Експорт:
    screenshot_map() -> bytes   (PNG)
    build_map_png()  -> (bytes, caption)
"""

from __future__ import annotations

import asyncio
import io
import logging
from datetime import datetime, timedelta, timezone

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

MAP_URL = "https://map.ukrainealarm.com/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
VIEWPORT = {"width": 1600, "height": 1100}

# Скільки чекати після завантаження, щоб пройшов JS-челендж і підвантажились тайли.
SETTLE_MS = 9000

# Елементи сайту, які треба сховати перед скріншотом (мусор: шапка, банер, лічильник, тулбар).
# Саме замість обрізання картинки — так карта не ріжеться.
JUNK_SELECTORS = (
    ".header",
    ".header-wrapper",
    ".header-container",
    ".bottom-banner",
    "#bottom-banner_a",
    ".toolbar",
    ".online",
)

# Розтягуємо карту на весь вікно після сховування мусору.
EXPAND_CSS = (
    "html, body { margin:0 !important; padding:0 !important; }"
    ".header, .header-wrapper, .header-container, .bottom-banner,"
    "#bottom-banner_a, .toolbar, .online { display:none !important; }"
    ".app, .content, .map, .appHolder {"
    "  top:0 !important; left:0 !important; height:100vh !important; width:100vw !important;"
    "}"
    ".content { position:fixed !important; inset:0 !important; }"
)


async def screenshot_map(*, full_page: bool = False) -> bytes:
    """Відкрити карту як реальна людина та повернути PNG-скріншот."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            # headless=False + окно за межами екрана: Cloudflare бачить справжній
            # Chrome (не headless-детект), але вікно не заважає користувачу.
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--window-position=-32000,-32000",
                "--window-size=1600,1100",
                "--lang=uk-UA",
                "--hide-scrollbars",
                "--mute-audio",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )
        try:
            ctx = await browser.new_context(
                viewport=VIEWPORT,
                locale="uk-UA",
                timezone_id="Europe/Kyiv",
                user_agent=USER_AGENT,
                device_scale_factor=1,
            )
            await ctx.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
                "window.chrome={runtime:{}};"
            )
            page = await ctx.new_page()
            await page.goto(MAP_URL, wait_until="domcontentloaded", timeout=60000)
            await page.add_style_tag(content=EXPAND_CSS)

            # Прибираємо банери згоди, якщо є.
            for sel in (
                "button:has-text('Прийняти')",
                "button:has-text('Accept')",
                "button:has-text('OK')",
                "button:has-text('Погоджуюсь')",
                "[aria-label*='cookie'] button",
            ):
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=600):
                        await el.click()
                        await page.wait_for_timeout(800)
                        break
                except Exception:
                    pass

            # Даємо час на JS-челендж Cloudflare і рендер карти.
            await page.wait_for_timeout(SETTLE_MS)

            png = await page.screenshot(full_page=full_page)
            logger.info("Captured ukrainealarm map (%d bytes)", len(png))
            return png
        finally:
            await browser.close()


def _caption(regions: int | None = None) -> str:
    # Київський час (EET/EEST) незалежно від TZ машини.
    kyiv = timezone(timedelta(hours=3))
    ts = datetime.now(timezone.utc).astimezone(kyiv).strftime("%d.%m.%Y %H:%M")
    return f"Оновлено: {ts} (Київ)"


async def build_map_png(assets_dir=None) -> tuple[bytes, str]:
    """Повернути (JPEG-фото, підпис). assets_dir — для сумісності з попереднім API."""
    png = await screenshot_map()
    return to_photo_jpeg(png), _caption()


def to_photo_jpeg(png: bytes, *, quality: int = 88) -> bytes:
    """Конвертує PNG у JPEG, щоб Telegram гарантовано відправив як ФОТО, а не документ."""
    from PIL import Image

    image = Image.open(io.BytesIO(png)).convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


if __name__ == "__main__":
    import sys

    png = asyncio.run(screenshot_map())
    if "--stdout" in sys.argv:
        # Друкуємо JPEG у stdout (для запуску окремим процесом із botsrc).
        # JPEG — Telegram впевнено відправляє як фото.
        data = to_photo_jpeg(png)
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
    else:
        with open("_ua_map_test.png", "wb") as fh:
            fh.write(png)
        print("png bytes:", len(png), "magic:", png[:8])