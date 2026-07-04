import logging
import os
import sqlite3

log = logging.getLogger(__name__)


class Memory:
    def __init__(self, db_path: str = "data/memory.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._init()

    def _init(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS summaries (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id     INTEGER NOT NULL,
                summary        TEXT    NOT NULL,
                message_count  INTEGER DEFAULT 0,
                created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS channel_configs (
                channel_id        INTEGER PRIMARY KEY,
                post_in_channel   INTEGER NOT NULL DEFAULT 1,
                summary_channel_id INTEGER
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        self.conn.commit()
        log.info("Database initialised at %s", self.db_path)

    # --- summaries ------------------------------------------------------------

    def get_recent_summaries(self, channel_id: int, limit: int = 5) -> list[tuple[str, str]]:
        rows = self.conn.execute(
            "SELECT summary, created_at FROM summaries "
            "WHERE channel_id = ? ORDER BY created_at DESC LIMIT ?",
            (channel_id, limit),
        ).fetchall()
        return rows

    def save_summary(self, channel_id: int, summary: str, message_count: int = 0):
        self.conn.execute(
            "INSERT INTO summaries (channel_id, summary, message_count) VALUES (?, ?, ?)",
            (channel_id, summary, message_count),
        )
        self.conn.commit()

    # --- channel config -------------------------------------------------------

    def get_channel_configs(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT channel_id, post_in_channel, summary_channel_id FROM channel_configs"
        ).fetchall()
        return [
            {
                "channel_id": r[0],
                "post_in_channel": bool(r[1]),
                "summary_channel_id": r[2],
            }
            for r in rows
        ]

    def set_channel_config(
        self,
        channel_id: int,
        post_in_channel: bool = True,
        summary_channel_id: int | None = None,
    ):
        self.conn.execute(
            "INSERT OR REPLACE INTO channel_configs (channel_id, post_in_channel, summary_channel_id) "
            "VALUES (?, ?, ?)",
            (channel_id, int(post_in_channel), summary_channel_id),
        )
        self.conn.commit()

    def remove_channel_config(self, channel_id: int):
        self.conn.execute(
            "DELETE FROM channel_configs WHERE channel_id = ?", (channel_id,)
        )
        self.conn.commit()

    # --- bot settings ---------------------------------------------------------

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM bot_settings WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else default

    def set_setting(self, key: str, value: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        self.conn.commit()

    def close(self):
        self.conn.close()
