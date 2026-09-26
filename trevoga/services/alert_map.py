"""Скріншот офіційної карти тривог України (map.ukrainealarm.com).

Використовує Playwright зі СПРАВЖНІМ (headful) Chrome, бо Cloudflare блокує
headless-запити та прямий доступ до api.ukrainealarm.com (403). Браузер
відкриває сторінку як реальна людина, чекає рендер карти й робить скріншот.

ШВИДКИЙ РЕЖИМ (v3):
    * ОДИН «теплий» браузер + сторінка живуть між викликами (AlertMapRenderer):
      після першого прогреву Cloudflare-челлендж вже пройдено — наступні
      .map робляться за ~2-3 с.
    * ПЕРСИСТЕНТНИЙ ПРОФІЛЬ Chrome (user_data_dir): Cloudflare-cookie та
      пройдений челлендж зберігаються на диску, тож навіть після рестарту
      бота або ручного закриття браузера челлендж НЕ проходиться заново.
    * очікування УМОВИ (появи тайлів карти) замість сліпого sleep;
    * in-memory кеш з TTL — повторні запити миттєві;
    * анти-дублі: паралельні .map не запускають кілька рендерів.

Керування через env (усі опційні):
    MAP_PROFILE_DIR      — каталог персистентного профілю Chrome
                           (default: <repo>/.chrome-profile)
    MAP_CACHE_TTL        — TTL кешу в секундах (default: 25; 0 = без кешу)
    MAP_HEADLESS         — "1" щоб спробувати headless=new (default: headful)

Експорт:
    screenshot_map() -> bytes            (PNG, разовий холодний запуск)
    build_map_png()  -> (bytes, caption)  (JPEG + підпис)
    render_map_jpeg() -> bytes            (швидкий шлях через warm renderer)
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent

MAP_URL = "https://map.ukrainealarm.com/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
VIEWPORT = {"width": 1600, "height": 1100}


def _env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


# Скільки чекати після завантаження, якщо НЕ вдалося дочекатися умови (фолбэк).
SETTLE_MS = 2500
# Максимум, скільки чекати появи тайлів/карти після навігації.
READY_TIMEOUT_MS = 15000
# TTL кешу готового JPEG (0 = без кешу, завжди свіжий рендер).
CACHE_TTL_SECONDS = _env_float("MAP_CACHE_TTL", 25.0)
# Персистентний профіль Chrome (cookie Cloudflare переживають рестарт).
PROFILE_DIR = Path(
    os.getenv("MAP_PROFILE_DIR", "").strip() or (BASE_DIR / ".chrome-profile")
)
# Спробувати headless=new (за замовчуванням headful — Cloudflare надійніше пускає).
HEADLESS = _env_flag("MAP_HEADLESS")

# Елементи сайту, які треба сховати перед скріншотом (мусор: шапка, банер, лічильник, тулбар).
JUNK_SELECTORS = (
    ".header",
    ".header-wrapper",
    ".header-container",
    ".bottom-banner",
    "#bottom-banner_a",
    ".toolbar",
    ".online",
)

# Розтягуємо карту на весь екран після сховування мусору.
EXPAND_CSS = (
    "html, body { margin:0 !important; padding:0 !important; }"
    ".header, .header-wrapper, .header-container, .bottom-banner,"
    "#bottom-banner_a, .toolbar, .online { display:none !important; }"
    ".app, .content, .map, .appHolder {"
    "  top:0 !important; left:0 !important; height:100vh !important; width:100vw !important;"
    "}"
    ".content { position:fixed !important; inset:0 !important; }"
)

# Селектори, які з'являються лише коли карта реально відрендерилась.
# Будь-який з них = можна робити скріншот (без сліпого sleep).
MAP_READY_SELECTORS = (
    ".leaflet-container",
    ".leaflet-tile-loaded",
    ".map",
    "canvas",
)

_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--window-position=-32000,-32000",
    "--window-size=1600,1100",
    "--lang=uk-UA",
    "--hide-scrollbars",
    "--mute-audio",
    "--no-first-run",
    "--no-default-browser-check",
]

_INIT_SCRIPT = (
    "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
    "window.chrome={runtime:{}};"
)


def to_photo_jpeg(png: bytes, *, quality: int = 88) -> bytes:
    """Конвертує PNG у JPEG, щоб Telegram гарантовано відправив як ФОТО, а не документ."""
    from PIL import Image

    image = Image.open(io.BytesIO(png)).convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


def _caption(regions: int | None = None) -> str:
    # Київський час (EET/EEST) незалежно від TZ машини.
    kyiv = timezone(timedelta(hours=3))
    ts = datetime.now(timezone.utc).astimezone(kyiv).strftime("%d.%m.%Y %H:%M")
    return f"Оновлено: {ts} (Київ)"


async def _prepare_page(page) -> None:
    """Застосувати CSS-розширення та прибрати банери згоди на сторінці."""
    await page.add_style_tag(content=EXPAND_CSS)
    for sel in (
        "button:has-text('Прийняти')",
        "button:has-text('Accept')",
        "button:has-text('OK')",
        "button:has-text('Погоджуюсь')",
        "[aria-label*='cookie'] button",
    ):
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=400):
                await el.click()
                await page.wait_for_timeout(500)
                break
        except Exception:
            pass


async def _wait_map_ready(page) -> None:
    """Чекати появи тайлів карти (умова), а не сліпої паузи."""
    for sel in MAP_READY_SELECTORS:
        try:
            await page.wait_for_selector(sel, timeout=READY_TIMEOUT_MS, state="attached")
            # Дати тайлам долетіти після появи контейнера.
            await page.wait_for_timeout(1200)
            return
        except Exception:
            continue
    # Фолбэк — коротка пауза.
    await page.wait_for_timeout(SETTLE_MS)


class AlertMapRenderer:
    """Тримає один «теплий» браузер+сторінку та робить швидкі скріншоти.

    Використовує ПЕРСИСТЕНТНИЙ профіль Chrome (launch_persistent_context),
    тому Cloudflare-cookie зберігаються на диску між рестартами — челлендж
    проходиться лише один раз (при першому запуску на цій машині).

    Перший виклик прогріває браузер (~5-8 с, якщо челлендж ще не пройдено).
    Далі кожен виклик — reload + очікування тайлів + скріншот (~2-3 с).
    Результат кешується на CACHE_TTL_SECONDS.
    """

    def __init__(self) -> None:
        self._pw = None
        self._context = None
        self._page = None
        self._lock = asyncio.Lock()
        self._cache: bytes | None = None
        self._cache_ts: float = 0.0

    async def _ensure_browser(self) -> bool:
        """Підняти браузер, якщо він закритий/мертвий.

        Повертає True, якщо браузер був ПІДНЯТИЙ ЩОЙНО (сторінка вже
        завантажена і прогріта — скріншот можна робити одразу, БЕЗ reload).
        Повертає False, якщо використано вже живий теплий браузер.
        """
        if self._page is not None and not self._page.is_closed():
            return False
        await self._close_browser()
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        self._pw = await async_playwright().start()
        # Персистентний контекст: профіль (cookie, localStorage) живе на диску.
        self._context = await self._pw.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=HEADLESS,
            args=_LAUNCH_ARGS,
            viewport=VIEWPORT,
            locale="uk-UA",
            timezone_id="Europe/Kyiv",
            user_agent=USER_AGENT,
            device_scale_factor=1,
        )
        await self._context.add_init_script(_INIT_SCRIPT)
        pages = self._context.pages
        self._page = pages[0] if pages else await self._context.new_page()
        await self._page.goto(MAP_URL, wait_until="domcontentloaded", timeout=60000)
        await _prepare_page(self._page)
        await _wait_map_ready(self._page)
        logger.info("Alert map browser warmed up (profile=%s)", PROFILE_DIR)
        return True

    async def _close_browser(self) -> None:
        for closer in (
            getattr(self._context, "close", None),
            getattr(self._pw, "stop", None),
        ):
            if closer is None:
                continue
            try:
                await closer()
            except Exception:
                pass
        self._page = None
        self._context = None
        self._pw = None

    async def screenshot(self) -> bytes:
        """Повернути PNG-скріншот, перевикористовуючи теплий браузер."""
        async with self._lock:
            try:
                fresh = await self._ensure_browser()
                if not fresh:
                    # Теплий браузер: оновлюємо дані карти через reload.
                    try:
                        await self._page.reload(
                            wait_until="domcontentloaded", timeout=30000
                        )
                    except Exception:
                        # reload не вдався — піднімаємо сторінку заново.
                        await self._close_browser()
                        await self._ensure_browser()
                    await _prepare_page(self._page)
                    await _wait_map_ready(self._page)
                # fresh=True: сторінка вже завантажена і прогріта в
                # _ensure_browser — reload тут НЕ потрібен.
                return await self._page.screenshot()
            except Exception:
                logger.exception("Warm map render failed; recycling browser")
                await self._close_browser()
                raise

    async def jpeg(self, *, use_cache: bool = True) -> bytes:
        """Швидкий шлях: кешований JPEG, інакше — теплий рендер + кеш."""
        now = time.monotonic()
        if (
            use_cache
            and CACHE_TTL_SECONDS > 0
            and self._cache is not None
            and now - self._cache_ts < CACHE_TTL_SECONDS
        ):
            return self._cache
        png = await self.screenshot()
        data = to_photo_jpeg(png)
        self._cache = data
        self._cache_ts = time.monotonic()
        return data

    async def aclose(self) -> None:
        async with self._lock:
            await self._close_browser()


_renderer: AlertMapRenderer | None = None


def get_renderer() -> AlertMapRenderer:
    """Singleton-рендерер на процес (теплий браузер переживає виклики)."""
    global _renderer
    if _renderer is None:
        _renderer = AlertMapRenderer()
    return _renderer


async def render_map_jpeg(*, use_cache: bool = True) -> bytes:
    """Швидкий публічний API: JPEG-байти карти (теплий браузер + кеш)."""
    return await get_renderer().jpeg(use_cache=use_cache)


async def shutdown_renderer() -> None:
    """Акуратно закрити теплий браузер (викликати при зупинці бота)."""
    global _renderer
    if _renderer is not None:
        await _renderer.aclose()
        _renderer = None


async def screenshot_map(*, full_page: bool = False) -> bytes:
    """Разовий холодний запуск (сумісність зі старим API та тестами)."""
    async with async_playwright() as pw:
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=HEADLESS,
            args=_LAUNCH_ARGS,
            viewport=VIEWPORT,
            locale="uk-UA",
            timezone_id="Europe/Kyiv",
            user_agent=USER_AGENT,
            device_scale_factor=1,
        )
        try:
            await ctx.add_init_script(_INIT_SCRIPT)
            pages = ctx.pages
            page = pages[0] if pages else await ctx.new_page()
            await page.goto(MAP_URL, wait_until="domcontentloaded", timeout=60000)
            await _prepare_page(page)
            await _wait_map_ready(page)
            png = await page.screenshot(full_page=full_page)
            logger.info("Captured ukrainealarm map (%d bytes)", len(png))
            return png
        finally:
            await ctx.close()


async def build_map_png(assets_dir=None) -> tuple[bytes, str]:
    """Повернути (JPEG-фото, підпис), використовуючи ШВИДКИЙ теплий рендер."""
    data = await render_map_jpeg()
    return data, _caption()


if __name__ == "__main__":
    import sys

    if "--warm" in sys.argv:
        # Замір швидкості: перший (холодний) і другий (теплий) рендери.
        async def _bench() -> None:
            t0 = time.monotonic()
            first = await render_map_jpeg(use_cache=False)
            t1 = time.monotonic()
            second = await render_map_jpeg(use_cache=False)
            t2 = time.monotonic()
            print(f"cold: {t1 - t0:.2f}s ({len(first)} bytes)")
            print(f"warm: {t2 - t1:.2f}s ({len(second)} bytes)")
            await shutdown_renderer()

        asyncio.run(_bench())
    else:
        png = asyncio.run(screenshot_map())
        if "--stdout" in sys.argv:
            data = to_photo_jpeg(png)
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
        else:
            with open("_ua_map_test.png", "wb") as fh:
                fh.write(png)
            print("png bytes:", len(png), "magic:", png[:8])