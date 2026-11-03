import os
import sys
from pathlib import Path

import requests

MODEL_URL = (
    "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/"
    "resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
)
MODEL_DIR = Path(__file__).parent / "models"
MODEL_FILE = MODEL_DIR / "qwen2.5-1.5b-instruct-q4_k_m.gguf"


def download():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    if MODEL_FILE.exists():
        size_mb = MODEL_FILE.stat().st_size / (1024 * 1024)
        print(f"Model already exists: {MODEL_FILE} ({size_mb:.0f} MB)")
        return

    print(f"Downloading Qwen2.5-1.5B Q4_K_M (~1.1 GB)...")
    print(f"URL: {MODEL_URL}")
    print()

    try:
        response = requests.get(MODEL_URL, stream=True, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Failed to download model: {e}", file=sys.stderr)
        print("The bot will use the template-based summarizer as fallback.")
        sys.exit(1)

    total = int(response.headers.get("content-length", 0))
    downloaded = 0

    with open(MODEL_FILE, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded / total * 100
                bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                sys.stdout.write(f"\r{bar} {pct:.0f}% ({downloaded // 1024 // 1024} MB)")
                sys.stdout.flush()

    print(f"\n✅ Model saved to {MODEL_FILE}")


if __name__ == "__main__":
    download()
