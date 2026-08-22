import os

from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")

SOURCE_CHANNELS = [
    c.strip() for c in os.getenv("SOURCE_CHANNELS", "").split(",") if c.strip()
]

GROUP_C = int(os.getenv("GROUP_C", "0"))
GROUP_D = int(os.getenv("GROUP_D", "0"))
