"""
Repositório de incidentes — camada exclusiva de acesso a dados.

Responsabilidade única: traduzir entre o banco SQLite e os modelos de domínio.
Nenhuma regra de negócio aqui — só SQL e mapeamento de linhas para objetos.
"""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.domain.incident import (
    AttemptEntry,
    Incident,
    IncidentMetadata,
    IncidentSeverity,
    IncidentStatus,
    IncidentType,
)

_COLUMNS = (
    "id", "type", "severity", "summary", "event_id", "user_email",
    "status", "retries", "first_seen", "last_seen", "resolved_at", "metadata",
)

_SELECT_ALL = f"SELECT {', '.join(_COLUMNS)} FROM incidents"


class IncidentRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _parse_meta(raw: Optional[str]) -> IncidentMetadata:
        try:
            d = json.loads(raw or "{}")
        except json.JSONDecodeError:
            d = {}
        return IncidentMetadata.from_dict(d)

    @staticmethod
    def _dump_meta(meta: IncidentMetadata) -> str:
        return json.dumps(meta.to_dict(), ensure_ascii=False)

    def _row_to_incident(self, row: sqlite3.Row) -> Incident:
        d = dict(row)
        try:
            inc_type = IncidentType(d["type"])
        except ValueError:
            inc_type = IncidentType.MANUAL_REVIEW_REQUIRED
        try:
            severity = IncidentSeverity(d["severity"])
        except ValueError:
            severity = IncidentSeverity.WARNING
        try:
            status = IncidentStatus(d["status"])
        except ValueError:
            status = IncidentStatus.OPEN

        return Incident(
            id=d["id"],
            type=inc_type,
            severity=severity,
            summary=d["summary"],
            event_id=d.get("event_id") or "",
            user_email=d.get("user_email"),
            status=status,
            retries=int(d.get("retries") or 0),
            first_seen=d.get("first_seen") or "",
            last_seen=d.get("last_seen") or "",
            resolved_at=d.get("resolved_at"),
            metadata=self._parse_meta(d.get("metadata")),
        )

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ── reads ─────────────────────────────────────────────────────────────────

    def get_by_id(self, incident_id: str) -> Incident:
        with self._conn() as conn:
            row = conn.execute(
                f"{_SELECT_ALL} WHERE id = ?", (incident_id,)
            ).fetchone()
        if not row:
            raise KeyError(f"Incidente não encontrado: {incident_id}")
        return self._row_to_incident(row)

    def find_open(
        self,
        event_id: str,
        incident_type: IncidentType,
        user_email: Optional[str] = None,
    ) -> Optional[Incident]:
        sql = f"{_SELECT_ALL} WHERE event_id = ? AND type = ? AND status = 'open'"
        params: List = [event_id, incident_type.value]
        if user_email is not None:
            sql += " AND user_email = ?"
            params.append(user_email)
        sql += " ORDER BY last_seen DESC LIMIT 1"
        with self._conn() as conn:
            row = conn.execute(sql, params).fetchone()
        return self._row_to_incident(row) if row else None

    def list(
        self,
        *,
        include_resolved: bool = False,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        event_id: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[Incident]:
        clauses, params = [], []
        if not include_resolved:
            clauses.append("status != 'resolved'")
        if severity:
            clauses.append("severity = ?")
            params.append(severity)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if event_id:
            clauses.append("event_id = ?")
            params.append(event_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"{_SELECT_ALL} {where} ORDER BY last_seen DESC"
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        incidents = [self._row_to_incident(r) for r in rows]
        if tag:
            incidents = [i for i in incidents if tag in i.metadata.tags]
        return incidents

    # ── writes ────────────────────────────────────────────────────────────────

    def insert(self, incident: Incident) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO incidents
                   (id, type, severity, summary, event_id, user_email,
                    status, retries, first_seen, last_seen, resolved_at, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    incident.id,
                    incident.type.value,
                    incident.severity.value,
                    incident.summary,
                    incident.event_id,
                    incident.user_email,
                    incident.status.value,
                    incident.retries,
                    incident.first_seen,
                    incident.last_seen,
                    incident.resolved_at,
                    self._dump_meta(incident.metadata),
                ),
            )
            conn.commit()

    def update_status(
        self,
        incident_id: str,
        status: IncidentStatus,
        *,
        resolved_at: Optional[str] = None,
        metadata: Optional[IncidentMetadata] = None,
    ) -> None:
        now = self._now()
        updates = ["status = ?", "last_seen = ?"]
        params: List = [status.value, now]
        if resolved_at is not None:
            updates.append("resolved_at = ?")
            params.append(resolved_at)
        if metadata is not None:
            updates.append("metadata = ?")
            params.append(self._dump_meta(metadata))
        params.append(incident_id)
        with self._conn() as conn:
            conn.execute(
                f"UPDATE incidents SET {', '.join(updates)} WHERE id = ?", params
            )
            conn.commit()

    def update_metadata(self, incident_id: str, metadata: IncidentMetadata) -> None:
        now = self._now()
        with self._conn() as conn:
            conn.execute(
                "UPDATE incidents SET metadata = ?, last_seen = ? WHERE id = ?",
                (self._dump_meta(metadata), now, incident_id),
            )
            conn.commit()

    def increment_retries(self, incident_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE incidents SET retries = retries + 1, last_seen = ? WHERE id = ?",
                (self._now(), incident_id),
            )
            conn.commit()
