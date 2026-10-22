import json
import sqlite3
from typing import Any, Dict

EDITABLE_KEYS = {
    "schedule",
    "recording_schedule",
    "timezone",
    "days_ahead",
    "days_behind",
    "discord_webhook_url",
    "google_chat_webhook_url",
    "webhook_url",
    "report_email_override",
    "calendar_id",
}

DEFAULTS: Dict[str, Any] = {
    "schedule": [],
    "recording_schedule": [],
    "timezone": "America/Recife",
    "days_ahead": 1,
    "days_behind": 0,
    "discord_webhook_url": "",
    "google_chat_webhook_url": "",
    "webhook_url": "",
    "report_email_override": "",
    "calendar_id": "primary",
}


class SettingsStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS config_settings (
                    key        TEXT PRIMARY KEY,
                    value      TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.commit()

    def get_all(self) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT key, value FROM config_settings").fetchall()
        result = dict(DEFAULTS)
        for key, value in rows:
            if key in EDITABLE_KEYS:
                result[key] = json.loads(value)
        return result

    def set_all(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            for key, value in settings.items():
                if key not in EDITABLE_KEYS:
                    continue
                conn.execute(
                    """INSERT INTO config_settings (key, value, updated_at)
                       VALUES (?, ?, datetime('now'))
                       ON CONFLICT(key) DO UPDATE
                       SET value      = excluded.value,
                           updated_at = excluded.updated_at""",
                    (key, json.dumps(value)),
                )
            conn.commit()
        return self.get_all()
