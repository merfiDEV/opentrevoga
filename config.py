from trevoga.config import load_settings


_settings = load_settings()

API_ID = _settings.api_id
API_HASH = _settings.api_hash
SOURCE_CHANNELS = list(_settings.source_channels)
GROUP_C = _settings.group_c
GROUP_D_TARGETS = list(_settings.group_d_targets)
ADMIN_IDS = list(_settings.admin_ids)
