import os
import yaml
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List


@dataclass
class Config:
    calendar_id: str
    days_ahead: int
    days_behind: int
    report_email_override: str
    credentials_path: str
    token_path: str
    log_level: str
    incidents_db_path: str = "incidents.db"
    discord_webhook_url: str = ""
    google_chat_webhook_url: str = ""
    webhook_url: str = ""
    schedule: List[str] = field(default_factory=list)
    recording_schedule: List[str] = field(default_factory=list)
    timezone: str = "America/Recife"
    dry_run: bool = False


def load_config(path="config.yaml"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except FileNotFoundError:
        raw = {}

    # Env vars sobrepõem o YAML — útil no Render sem config.yaml no container
    def _e(key, fallback):
        return os.getenv(key) or fallback

    dry_run_raw = os.getenv("DRY_RUN", str(raw.get("dry_run", False))).lower()

    return Config(
        calendar_id=_e("CALENDAR_ID", raw.get("calendar_id", "primary")),
        days_ahead=int(_e("DAYS_AHEAD", raw.get("days_ahead", 1))),
        days_behind=int(_e("DAYS_BEHIND", raw.get("days_behind", 0))),
        report_email_override=_e("REPORT_EMAIL", raw.get("report_email_override", "")),
        credentials_path=_e("CREDENTIALS_PATH", raw.get("credentials_path", "credentials.json")),
        token_path=_e("TOKEN_PATH", raw.get("token_path", "token.json")),
        log_level=_e("LOG_LEVEL", raw.get("log_level", "INFO")),
        incidents_db_path=_e("INCIDENTS_DB", raw.get("incidents_db_path", "data/incidents.db")),
        webhook_url=_e("WEBHOOK_URL", raw.get("webhook_url", "")),
        discord_webhook_url=_e("DISCORD_WEBHOOK_URL", raw.get("discord_webhook_url", "")),
        google_chat_webhook_url=_e("GOOGLE_CHAT_WEBHOOK_URL", raw.get("google_chat_webhook_url", "")),
        schedule=raw.get("schedule", []),
        recording_schedule=raw.get("recording_schedule", []),
        timezone=_e("TIMEZONE", raw.get("timezone", "America/Recife")),
        dry_run=dry_run_raw in ("1", "true", "yes"),
    )


def apply_db_settings(config: "Config", settings: Dict[str, Any]) -> "Config":
    """Retorna novo Config com valores do banco sobrepondo os do YAML."""
    return replace(
        config,
        schedule=settings.get("schedule", config.schedule),
        recording_schedule=settings.get("recording_schedule", config.recording_schedule),
        timezone=settings.get("timezone", config.timezone),
        days_ahead=int(settings.get("days_ahead", config.days_ahead)),
        days_behind=int(settings.get("days_behind", config.days_behind)),
        discord_webhook_url=settings.get("discord_webhook_url", config.discord_webhook_url),
        google_chat_webhook_url=settings.get("google_chat_webhook_url", config.google_chat_webhook_url),
        webhook_url=settings.get("webhook_url", config.webhook_url),
        report_email_override=settings.get("report_email_override", config.report_email_override),
        calendar_id=settings.get("calendar_id", config.calendar_id),
    )
