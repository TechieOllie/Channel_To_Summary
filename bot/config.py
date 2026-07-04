import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    def __init__(self):
        self.token: str = os.environ["DISCORD_TOKEN"]
        self.ollama_url: str = os.environ.get("OLLAMA_URL", "http://ollama:11434")
