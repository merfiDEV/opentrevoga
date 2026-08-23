import pytest

from trevoga.config import Settings


def test_invalid_settings_are_rejected(tmp_path):
    settings = Settings(
        api_id=0,
        api_hash="",
        source_channels=(),
        group_c=0,
        group_d_targets=(),
        admin_ids=(),
        database_path=tmp_path / "db",
        session_path=tmp_path / "session",
        assets_dir=tmp_path,
        ai_mode=False,
        ai_api_base="http://localhost/v1",
        ai_model="model",
        ai_api_key="",
        ai_check_delay=5,
        ai_timeout=60,
        ai_fix_api_base="http://localhost/v1",
        ai_fix_model="model",
        ai_fix_api_key="",
        ai_fix_timeout=60,
    )
    with pytest.raises(ValueError):
        settings.validate()
