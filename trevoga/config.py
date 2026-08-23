import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent


def _env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


def _parse_target(value: str) -> int | str:
    value = value.strip()
    return int(value) if value.lstrip("-").isdigit() else value


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    source_channels: tuple[str, ...]
    group_c: int
    group_d_targets: tuple[int | str, ...]
    admin_ids: tuple[int, ...]
    database_path: Path
    session_path: Path
    assets_dir: Path
    ai_mode: bool
    ai_api_base: str
    ai_model: str
    ai_api_key: str
    ai_check_delay: float
    ai_timeout: float
    ai_fix_api_base: str
    ai_fix_model: str
    ai_fix_api_key: str
    ai_fix_timeout: float

    def validate(self) -> None:
        errors = []
        if not self.api_id:
            errors.append("API_ID is required")
        if not self.api_hash:
            errors.append("API_HASH is required")
        if not self.source_channels:
            errors.append("SOURCE_CHANNELS must contain at least one channel")
        if not self.group_c:
            errors.append("GROUP_C is required")
        if not self.group_d_targets:
            errors.append("GROUP_D_TARGETS must contain at least one target")
        if errors:
            raise ValueError("Invalid configuration: " + "; ".join(errors))


def load_settings() -> Settings:
    load_dotenv(BASE_DIR / ".env")
    ai_base = os.getenv("AI_API_BASE", "http://127.0.0.1:8000/v1").rstrip("/")
    ai_model = os.getenv("AI_MODEL", "deepseek-v4-flash")
    ai_key = os.getenv("AI_API_KEY", "").strip()
    ai_timeout = _env_float("AI_TIMEOUT", 60.0)
    return Settings(
        api_id=int(os.getenv("API_ID", "0")),
        api_hash=os.getenv("API_HASH", ""),
        source_channels=tuple(
            value.strip()
            for value in os.getenv("SOURCE_CHANNELS", "").split(",")
            if value.strip()
        ),
        group_c=int(os.getenv("GROUP_C", "0")),
        group_d_targets=tuple(
            _parse_target(value)
            for value in os.getenv("GROUP_D_TARGETS", "").split(",")
            if value.strip()
        ),
        admin_ids=tuple(
            int(value.strip())
            for value in os.getenv("ADMIN_IDS", "").split(",")
            if value.strip().lstrip("-").isdigit()
        ),
        database_path=BASE_DIR / os.getenv("DATABASE_FILE_NAME", "trevoga.db"),
        session_path=BASE_DIR / os.getenv("SESSION_FILE_NAME", "session"),
        assets_dir=BASE_DIR / "asseti",
        ai_mode=_env_flag("AI_MODE"),
        ai_api_base=ai_base,
        ai_model=ai_model,
        ai_api_key=ai_key,
        ai_check_delay=_env_float("AI_CHECK_DELAY", 5.0),
        ai_timeout=ai_timeout,
        ai_fix_api_base=(os.getenv("AI_FIX_API_BASE") or ai_base).rstrip("/"),
        ai_fix_model=os.getenv("AI_FIX_MODEL") or ai_model,
        ai_fix_api_key=os.getenv("AI_FIX_API_KEY") or ai_key,
        ai_fix_timeout=_env_float("AI_FIX_TIMEOUT", ai_timeout),
    )
