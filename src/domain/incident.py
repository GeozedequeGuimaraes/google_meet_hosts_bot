"""
Modelos de domínio para incidentes.

Estas classes representam as entidades centrais do sistema, sem qualquer
dependência de infraestrutura (banco, HTTP, Google API). São a fonte de
verdade sobre o que um Incidente é e quais estados ele pode ter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class IncidentStatus(str, Enum):
    OPEN = "open"
    REPROCESSING = "reprocessing"
    RESOLVED = "resolved"


class IncidentSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class IncidentType(str, Enum):
    COHOST_ASSIGNMENT_FAILED = "COHOST_ASSIGNMENT_FAILED"
    MEET_SPACE_CONFIG_FAILED = "MEET_SPACE_CONFIG_FAILED"
    GOOGLE_API_ERROR = "GOOGLE_API_ERROR"
    EVENT_SKIPPED = "EVENT_SKIPPED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    RECORDING_NOT_FOUND = "RECORDING_NOT_FOUND"
    RECORDING_PUBLISH_FAILED = "RECORDING_PUBLISH_FAILED"


@dataclass
class AttemptEntry:
    timestamp: str
    action: str
    summary: str
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "action": self.action,
            "summary": self.summary,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AttemptEntry":
        return cls(
            timestamp=d.get("timestamp", ""),
            action=d.get("action", ""),
            summary=d.get("summary", ""),
            status=d.get("status", ""),
        )


_KNOWN_META_KEYS = frozenset(
    {"tags", "attempt_history", "meeting_title", "reason", "reprocess_jobs"}
)


@dataclass
class IncidentMetadata:
    tags: List[str] = field(default_factory=list)
    attempt_history: List[AttemptEntry] = field(default_factory=list)
    meeting_title: str = ""
    reason: str = ""
    reprocess_jobs: List[Dict[str, Any]] = field(default_factory=list)
    # Preserva campos desconhecidos para não perder dados legados
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "tags": list(self.tags),
            "attempt_history": [a.to_dict() for a in self.attempt_history],
            "meeting_title": self.meeting_title,
            "reason": self.reason,
            "reprocess_jobs": list(self.reprocess_jobs),
        }
        result.update(self.extra)
        return result

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "IncidentMetadata":
        extra = {k: v for k, v in d.items() if k not in _KNOWN_META_KEYS}
        return cls(
            tags=list(d.get("tags", [])),
            attempt_history=[
                AttemptEntry.from_dict(e)
                for e in d.get("attempt_history", [])
                if isinstance(e, dict)
            ],
            meeting_title=d.get("meeting_title", ""),
            reason=d.get("reason", ""),
            reprocess_jobs=list(d.get("reprocess_jobs", [])),
            extra=extra,
        )


@dataclass
class Incident:
    id: str
    type: IncidentType
    severity: IncidentSeverity
    summary: str
    event_id: str
    status: IncidentStatus
    first_seen: str
    last_seen: str
    retries: int = 0
    user_email: Optional[str] = None
    resolved_at: Optional[str] = None
    metadata: IncidentMetadata = field(default_factory=IncidentMetadata)

    def to_dict(self) -> Dict[str, Any]:
        """Representação dict para compatibilidade com código existente e API."""
        return {
            "id": self.id,
            "type": self.type.value,
            "severity": self.severity.value,
            "summary": self.summary,
            "event_id": self.event_id,
            "status": self.status.value,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "retries": self.retries,
            "user_email": self.user_email,
            "resolved_at": self.resolved_at,
            "metadata": self.metadata.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Incident":
        return cls(
            id=d["id"],
            type=IncidentType(d["type"]),
            severity=IncidentSeverity(d["severity"]),
            summary=d["summary"],
            event_id=d.get("event_id", ""),
            status=IncidentStatus(d["status"]),
            first_seen=d.get("first_seen", ""),
            last_seen=d.get("last_seen", ""),
            retries=int(d.get("retries", 0)),
            user_email=d.get("user_email"),
            resolved_at=d.get("resolved_at"),
            metadata=IncidentMetadata.from_dict(d.get("metadata") or {}),
        )
