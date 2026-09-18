"""Runtime health metrics for the .health command.

Keeps a tiny in-memory snapshot: process uptime, FloodWait counter and the
last ERROR-level log record. No external dependencies.
"""

import logging
import time

STARTED_AT = time.monotonic()
_FLOODWAIT_COUNT = 0
_last_error: str | None = None
_last_error_at: float | None = None


def record_floodwait() -> None:
    global _FLOODWAIT_COUNT
    _FLOODWAIT_COUNT += 1


def floodwait_count() -> int:
    return _FLOODWAIT_COUNT


def uptime_seconds() -> float:
    return time.monotonic() - STARTED_AT


def last_error() -> tuple[str | None, float | None]:
    """Return (message, unix timestamp) of the latest ERROR-level record."""
    return _last_error, _last_error_at


class LastErrorHandler(logging.Handler):
    """Keep the most recent ERROR/CRITICAL log record in memory."""

    def emit(self, record: logging.LogRecord) -> None:
        global _last_error, _last_error_at
        if record.levelno >= logging.ERROR:
            try:
                _last_error = self.format(record)
                _last_error_at = time.time()
            except Exception:  # pragma: no cover - defensive
                pass


def format_uptime(seconds: float) -> str:
    total = int(seconds)
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}д")
    if hours or days:
        parts.append(f"{hours}г")
    parts.append(f"{minutes}х")
    parts.append(f"{secs}с")
    return " ".join(parts)


def format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if value < 1024 or unit == "ТБ":
            return f"{value:.1f} {unit}" if unit != "Б" else f"{int(value)} {unit}"
        value /= 1024
    return f"{value:.1f} ТБ"
