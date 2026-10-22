"""
Schemas Pydantic para validação de entrada/saída da API do dashboard.

Separa o contrato da API da representação interna — mudanças de campo
no domínio não quebram a API sem intenção explícita.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ── Configurações ──────────────────────────────────────────────────────────

class SettingsRequest(BaseModel):
    schedule: List[str] = Field(default_factory=list)
    recording_schedule: List[str] = Field(default_factory=list)
    timezone: str = "America/Recife"
    days_ahead: int = Field(default=1, ge=0, le=30)
    days_behind: int = Field(default=0, ge=0, le=30)
    calendar_id: str = "primary"
    report_email_override: str = ""
    discord_webhook_url: str = ""
    google_chat_webhook_url: str = ""
    webhook_url: str = ""

    @field_validator("schedule", "recording_schedule")
    @classmethod
    def validate_schedule(cls, v: List[str]) -> List[str]:
        for entry in v:
            parts = entry.split(":")
            if len(parts) != 2:
                raise ValueError(f"Horário inválido: {entry!r} — use HH:MM")
            h, m = parts
            if not (h.isdigit() and m.isdigit()):
                raise ValueError(f"Horário inválido: {entry!r}")
            if not (0 <= int(h) <= 23 and 0 <= int(m) <= 59):
                raise ValueError(f"Horário fora do intervalo: {entry!r}")
        return v

    @field_validator("calendar_id")
    @classmethod
    def calendar_id_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("calendar_id não pode ser vazio")
        return v.strip()


class SettingsResponse(SettingsRequest):
    pass


# ── Incidentes ─────────────────────────────────────────────────────────────

class IncidentMetadataSchema(BaseModel):
    tags: List[str] = Field(default_factory=list)
    attempt_history: List[Dict[str, Any]] = Field(default_factory=list)
    meeting_title: str = ""
    reason: str = ""
    reprocess_jobs: List[Any] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class IncidentResponse(BaseModel):
    id: str
    type: str
    severity: str
    status: str
    summary: str
    event_id: Optional[str] = None
    user_email: Optional[str] = None
    retries: int = 0
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    resolved_at: Optional[str] = None
    metadata: IncidentMetadataSchema = Field(default_factory=IncidentMetadataSchema)

    model_config = {"extra": "allow"}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "IncidentResponse":
        return cls.model_validate(d)


# ── Reprocessamento ────────────────────────────────────────────────────────

class ReprocessJobResponse(BaseModel):
    id: str
    incident_id: str
    event_id: Optional[str] = None
    status: str
    requested_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ── Tags ───────────────────────────────────────────────────────────────────

class TagsRequest(BaseModel):
    tags: List[str] = Field(..., min_length=1)

    @field_validator("tags")
    @classmethod
    def tags_not_empty(cls, v: List[str]) -> List[str]:
        cleaned = [t.strip().lower() for t in v if t.strip()]
        if not cleaned:
            raise ValueError("Lista de tags não pode ser vazia")
        return cleaned
