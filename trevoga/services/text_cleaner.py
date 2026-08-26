import re
from html import escape
from pathlib import Path


WATERMARK_TEXT = "OpenTrevoga 🕊"
WATERMARK_URL = "https://telegra.ph/OpenTrevoga---trivogi-bez-shumu-08-24"
_watermark_enabled = True
EMOJI_PATTERN = re.compile(
    "["
    "\U0001f000-\U0001faff"
    "\U00002600-\U000027bf"
    "\U00002b00-\U00002bff"
    "\U0001f1e6-\U0001f1ff"
    "\ufe00-\ufe0f\u200d\u20e3"
    "]+"
)
LINK_PATTERN = re.compile(r"(?:https?://|www\.|t\.me/)\S+", re.IGNORECASE)
FOOTER_LINES = {"донецька сова", "чат", "підтримати"}
WATERMARK_PLAIN = EMOJI_PATTERN.sub("", WATERMARK_TEXT).strip()


def watermark() -> str:
    if _watermark_enabled:
        return f'<a href="{WATERMARK_URL}">{WATERMARK_TEXT}</a>'
    return WATERMARK_TEXT


def set_watermark(enabled: bool) -> None:
    global _watermark_enabled
    _watermark_enabled = enabled


def is_watermark_enabled() -> bool:
    return _watermark_enabled


def photo_rules(assets_dir: Path):
    return [
        (
            ("бпла", "шахед", "шахеди", "шахеді", "реактивні"),
            assets_dir / "photo_2026-08-22_14-29-40.jpg",
            "БПЛА/Шахеди",
        ),
        (
            ("каб", "каби", "бандероль", "баражуючі боєприпаси"),
            assets_dir / "cab.jpg",
            "Каби",
        ),
        (("рсзв", "рсзо"), assets_dir / "rszo.jpg", "РСЗВ/РСЗО"),
        (("фпв", "fpv"), assets_dir / "fpv.jpg", "FPV"),
        (
            ("швидкісна", "ракета", "ракети", "ракеті"),
            assets_dir / "svidkisna.jpg",
            "Швидкісна ціль",
        ),
        (
            ("балістичн", "балістик", "балістичні", "балістична", "балістика"),
            assets_dir / "ballistika.jpg",
            "Балістичні ракети",
        ),
    ]


def _keyword_pattern(rules) -> re.Pattern:
    keywords = sorted(
        {keyword for values, _, _ in rules for keyword in values}, key=len, reverse=True
    )
    return re.compile(
        r"(?<![\w-])(" + "|".join(re.escape(word) for word in keywords) + r")(?![\w-])",
        re.IGNORECASE,
    )


def clean_text(text: str) -> str:
    kept = []
    for line in text.splitlines():
        if LINK_PATTERN.search(line):
            continue
        stripped = EMOJI_PATTERN.sub("", line).strip()
        if (
            not stripped
            or stripped.lower() in FOOTER_LINES
            or stripped.lower() == WATERMARK_PLAIN.lower()
        ):
            continue
        kept.append(stripped)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


def format_post_html(text: str, rules) -> str:
    escaped = escape(text).strip()
    if not escaped:
        return ""
    highlighted = _keyword_pattern(rules).sub(r"<b>\1</b>", escaped)
    return f"<blockquote>{highlighted}</blockquote>"


def quote_html(text: str) -> str:
    value = escape(text).strip()
    return f"<blockquote>{value}</blockquote>" if value else ""


def detect_keywords(text: str, rules) -> list[str]:
    lowered = text.lower()
    return [
        label
        for keywords, _, label in rules
        if any(word in lowered for word in keywords)
    ]


def matching_photos(text: str, rules) -> list[Path]:
    lowered = text.lower()
    return [
        path
        for keywords, path, _ in rules
        if any(word in lowered for word in keywords) and path.exists()
    ]
