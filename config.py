from datetime import timezone
import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SUMMARY_TIME = os.getenv("SUMMARY_TIME", "23:59")
SUMMARY_TIMEZONE = os.getenv("SUMMARY_TIMEZONE", "UTC")
MESSAGE_FETCH_LIMIT = int(os.getenv("MESSAGE_FETCH_LIMIT", "500"))
DATA_DIR = os.getenv("DATA_DIR", "data")
LLAMA_MODEL_PATH = os.getenv("LLAMA_MODEL_PATH", "models/qwen2.5-1.5b-instruct-q4_k_m.gguf")

SUMMARY_TZ = ZoneInfo(SUMMARY_TIMEZONE) if SUMMARY_TIMEZONE != "UTC" else timezone.utc
