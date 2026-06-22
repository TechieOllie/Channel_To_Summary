import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SUMMARY_TIME = os.getenv("SUMMARY_TIME", "23:59")
MESSAGE_FETCH_LIMIT = int(os.getenv("MESSAGE_FETCH_LIMIT", "500"))
DATA_DIR = os.getenv("DATA_DIR", "data")
LLAMA_MODEL_PATH = os.getenv("LLAMA_MODEL_PATH", "models/qwen2.5-1.5b-instruct-q4_k_m.gguf")
