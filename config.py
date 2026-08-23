import os

from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")

SOURCE_CHANNELS = [
    c.strip() for c in os.getenv("SOURCE_CHANNELS", "").split(",") if c.strip()
]

GROUP_C = int(os.getenv("GROUP_C", "0"))


def _parse_target(value):
    value = value.strip()
    return int(value) if value.lstrip("-").isdigit() else value


GROUP_D_TARGETS = [
    _parse_target(t) for t in os.getenv("GROUP_D_TARGETS", "").split(",") if t.strip()
]

ADMIN_IDS = [
    int(i.strip())
    for i in os.getenv("ADMIN_IDS", "").split(",")
    if i.strip().lstrip("-").isdigit()
]
