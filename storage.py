from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone

import config

DATA_FILE = os.path.join(config.DATA_DIR, "data.json")
_lock = threading.Lock()


def _ensure_dir():
    os.makedirs(config.DATA_DIR, exist_ok=True)


def _load() -> dict:
    _ensure_dir()
    if not os.path.exists(DATA_FILE):
        return {"guilds": {}, "summaries": []}
    with _lock:
        with open(DATA_FILE, "r") as f:
            return json.load(f)


def _save(data: dict):
    _ensure_dir()
    with _lock:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)


def _guild_key(guild_id: int) -> str:
    return str(guild_id)


def _channel_key(channel_id: int) -> str:
    return str(channel_id)


# --- channel settings ---

def is_channel_enabled(guild_id: int, channel_id: int) -> bool:
    data = _load()
    g = data["guilds"].get(_guild_key(guild_id))
    if not g:
        return False
    ch = g.get("channels", {}).get(_channel_key(channel_id))
    return ch is not None and ch.get("enabled", False)


def set_channel_enabled(guild_id: int, channel_id: int, enabled: bool):
    data = _load()
    g = data["guilds"].setdefault(_guild_key(guild_id), {"channels": {}})
    g.setdefault("channels", {})[_channel_key(channel_id)] = {"enabled": enabled}
    _save(data)


def get_enabled_channels(guild_id: int) -> list[int]:
    data = _load()
    g = data["guilds"].get(_guild_key(guild_id))
    if not g:
        return []
    return [
        int(cid) for cid, ch in g.get("channels", {}).items()
        if ch.get("enabled")
    ]


def get_all_channel_settings(guild_id: int) -> list[dict]:
    data = _load()
    g = data["guilds"].get(_guild_key(guild_id))
    if not g:
        return []
    return [
        {"channel_id": int(cid), "enabled": ch.get("enabled", False)}
        for cid, ch in g.get("channels", {}).items()
    ]


# --- summary channel ---

def get_summary_channel(guild_id: int) -> int | None:
    data = _load()
    g = data["guilds"].get(_guild_key(guild_id))
    if not g:
        return None
    return g.get("summary_channel_id")


def set_summary_channel(guild_id: int, channel_id: int):
    data = _load()
    g = data["guilds"].setdefault(_guild_key(guild_id), {"channels": {}})
    g["summary_channel_id"] = channel_id
    _save(data)


# --- summaries ---

def save_summary(
    guild_id: int,
    channel_id: int,
    date_str: str,
    summary: str,
    message_count: int,
):
    data = _load()
    data["summaries"].append({
        "guild_id": guild_id,
        "channel_id": channel_id,
        "date": date_str,
        "summary": summary,
        "message_count": message_count,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    _save(data)
