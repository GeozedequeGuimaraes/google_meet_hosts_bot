"""
Serviço de incidentes — camada de negócio.

Responsabilidade: regras de estado (deduplicação, máquina de estados,
geração de IDs), coordenando o repositório de dados. Não contém SQL.

A interface pública retorna Dict para compatibilidade com dashboard.py e
orchestrator.py existentes. Internamente tudo é modelado via domain.Incident.
"""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.domain.incident import (
    AttemptEntry,
    Incident,
    IncidentMetadata,
    IncidentSeverity,
    IncidentStatus,
    IncidentType,
)
from src.migrations.runner import run_migrations
from src.infrastructure.persistence.incident_repository import IncidentRepository


# Mantidos para validação de entrada vinda de código legado / API
VALID_SEVERITIES = {s.value for s in IncidentSeverity}
VALID_TYPES = {t.value for t in IncidentType}


class IncidentStore:
    """Serviço de gerenciamento de incidentes.

    Orquestra criação, deduplicação, transições de estado e histórico de
    tentativas. Delega todo acesso a dados ao IncidentRepository.
    """

    def __init__(self, db_path: str = "incidents.db"):
        self.db_path = db_path
        run_migrations(db_path)          # garante schema atualizado antes de qualquer acesso
        self._repo = IncidentRepository(db_path)
        self._init_db()

    # ── inicialização ──────────────────────────────────────────────────────

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    event_id TEXT,
                    user_email TEXT,
                    status TEXT NOT NULL DEFAULT 'open',
                    retries INTEGER NOT NULL DEFAULT 0,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    resolved_at TEXT,
                    metadata TEXT NOT NULL DEFAULT '{}'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reprocess_jobs (
                    id TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    event_id TEXT,
                    status TEXT NOT NULL DEFAULT 'queued',
                    requested_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    error TEXT,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY (incident_id) REFERENCES incidents(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS config_settings (
                    key        TEXT PRIMARY KEY,
                    value      TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.commit()

    # ── helpers internos ───────────────────────────────────────────────────

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _make_id(incident_type: str, event_id: str, user_email: Optional[str]) -> str:
        ts = int(datetime.now(timezone.utc).timestamp())
        return f"{incident_type}:{event_id}:{user_email or 'system'}:{ts}"

    # ── leituras ───────────────────────────────────────────────────────────

    def get_by_id(self, incident_id: str) -> Dict[str, Any]:
        return self._repo.get_by_id(incident_id).to_dict()

    def list_open_incidents(self) -> List[Dict[str, Any]]:
        return self.list_incidents(include_resolved=False)

    def list_incidents(
        self,
        *,
        include_resolved: bool = False,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        event_id: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        incidents = self._repo.list(
            include_resolved=include_resolved,
            severity=severity,
            status=status,
            event_id=event_id,
            tag=tag,
        )
        return [i.to_dict() for i in incidents]

    def list_reprocess_jobs(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM reprocess_jobs WHERE 1=1"
        params: List[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY requested_at DESC"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
        return [
            {
                "id": row["id"],
                "incident_id": row["incident_id"],
                "event_id": row["event_id"],
                "status": row["status"],
                "requested_at": row["requested_at"],
                "started_at": row["started_at"],
                "finished_at": row["finished_at"],
                "error": row["error"],
                "metadata": json.loads(row["metadata"] or "{}"),
            }
            for row in rows
        ]

    # ── escrita: criação / deduplicação ───────────────────────────────────

    def create_or_update(
        self,
        *,
        event_id: str,
        incident_type: str,
        summary: str,
        severity: str,
        user_email: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if severity not in VALID_SEVERITIES:
            raise ValueError(f"Severidade inválida: {severity}")
        if incident_type not in VALID_TYPES:
            raise ValueError(f"Tipo inválido: {incident_type}")

        inc_type = IncidentType(incident_type)
        inc_severity = IncidentSeverity(severity)
        now = self._now()

        existing = self._repo.find_open(inc_type, inc_type, user_email) if False else \
                   self._repo.find_open(event_id, inc_type, user_email)

        if existing:
            # Atualiza incidente existente — incrementa retries, appenda histórico
            existing.metadata.attempt_history.append(AttemptEntry(
                timestamp=now, action="retry", summary=summary, status="repeated",
            ))
            existing.metadata.meeting_title = summary
            existing.severity = inc_severity
            existing.summary = summary
            self._repo.increment_retries(existing.id)
            self._repo.update_metadata(existing.id, existing.metadata)
            return self._repo.get_by_id(existing.id).to_dict()

        # Novo incidente
        meta = IncidentMetadata.from_dict(metadata or {})
        meta.meeting_title = meta.meeting_title or summary
        meta.attempt_history.append(AttemptEntry(
            timestamp=now, action="created", summary=summary, status="open",
        ))

        incident = Incident(
            id=self._make_id(incident_type, event_id, user_email),
            type=inc_type,
            severity=inc_severity,
            summary=summary,
            event_id=event_id,
            user_email=user_email,
            status=IncidentStatus.OPEN,
            retries=1,
            first_seen=now,
            last_seen=now,
            metadata=meta,
        )
        self._repo.insert(incident)
        return incident.to_dict()

    # ── escrita: transições de estado ──────────────────────────────────────

    def request_manual_reprocess(self, incident_id: str) -> Dict[str, Any]:
        incident = self._repo.get_by_id(incident_id)
        now = self._now()
        job_id = f"reprocess:{incident_id}:{int(datetime.now(timezone.utc).timestamp())}"

        incident.metadata.attempt_history.append(AttemptEntry(
            timestamp=now, action="manual_reprocess",
            summary="Solicitado reprocessamento manual", status="queued",
        ))
        incident.metadata.reprocess_jobs.append(job_id)
        incident.metadata.extra["reprocess_requested"] = True
        incident.metadata.extra["manual_reprocess"] = True

        self._repo.update_status(
            incident_id,
            IncidentStatus.REPROCESSING,
            metadata=incident.metadata,
        )
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO reprocess_jobs
                   (id, incident_id, event_id, status, requested_at, metadata)
                   VALUES (?, ?, ?, 'queued', ?, ?)""",
                (job_id, incident_id, incident.event_id, now,
                 json.dumps({"source": "dashboard"}, ensure_ascii=False)),
            )
            conn.commit()
        return self._repo.get_by_id(incident_id).to_dict()

    def resolve_incident(
        self, incident_id: str, resolved_at: Optional[str] = None
    ) -> Dict[str, Any]:
        incident = self._repo.get_by_id(incident_id)
        now = resolved_at or self._now()
        incident.metadata.attempt_history.append(AttemptEntry(
            timestamp=now, action="resolve",
            summary="Incidente encerrado", status="closed",
        ))
        self._repo.update_status(
            incident_id,
            IncidentStatus.RESOLVED,
            resolved_at=now,
            metadata=incident.metadata,
        )
        return self._repo.get_by_id(incident_id).to_dict()

    def reopen_incident(self, incident_id: str) -> Dict[str, Any]:
        incident = self._repo.get_by_id(incident_id)
        now = self._now()
        incident.metadata.attempt_history.append(AttemptEntry(
            timestamp=now, action="reopen",
            summary="Devolvido ao Dashboard pela equipe", status="open",
        ))
        self._repo.update_status(
            incident_id,
            IncidentStatus.OPEN,
            resolved_at=None,
            metadata=incident.metadata,
        )
        return self._repo.get_by_id(incident_id).to_dict()

    def log_processing(self, event_id: str, event_title: str, status: str, dry_run: bool = False) -> None:
        """Registra cada reunião processada — sucesso ou falha — para os KPIs do dashboard."""
        import uuid
        now = self._now()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR IGNORE INTO processing_log
                   (id, event_id, event_title, processed_at, status, dry_run)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), event_id, event_title, now, status, int(dry_run)),
            )
            conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        """Retorna métricas reais para os KPIs do dashboard."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute("SELECT COUNT(*) FROM processing_log WHERE dry_run = 0").fetchone()[0]
            success = conn.execute(
                "SELECT COUNT(*) FROM processing_log WHERE status LIKE 'sucesso%' AND dry_run = 0"
            ).fetchone()[0]
            by_day = conn.execute("""
                SELECT strftime('%w', processed_at) as dow, COUNT(*) as cnt
                FROM processing_log WHERE dry_run = 0
                AND processed_at >= datetime('now', '-7 days')
                GROUP BY dow
            """).fetchall()
            by_type = conn.execute("""
                SELECT status, COUNT(*) as cnt
                FROM processing_log WHERE dry_run = 0
                GROUP BY status
            """).fetchall()
        return {
            "total_processed": total,
            "total_success": success,
            "automation_pct": round((success / total * 100) if total else 0),
            "by_day": {r["dow"]: r["cnt"] for r in by_day},
            "by_type": {r["status"]: r["cnt"] for r in by_type},
        }

    def mark_retried(self, incident_id: str) -> Dict[str, Any]:
        """Incrementa retries sem mudar status — sinaliza que uma tentativa ocorreu."""
        self._repo.increment_retries(incident_id)
        return self._repo.get_by_id(incident_id).to_dict()

    def add_tags(self, incident_id: str, tags: List[str]) -> Dict[str, Any]:
        incident = self._repo.get_by_id(incident_id)
        current = set(incident.metadata.tags)
        for tag in tags:
            value = str(tag).strip()
            if value:
                current.add(value)
        incident.metadata.tags = sorted(current)
        self._repo.update_metadata(incident_id, incident.metadata)
        return self._repo.get_by_id(incident_id).to_dict()


def create_incident(
    *,
    store: IncidentStore,
    event_id: str,
    incident_type: str,
    summary: str,
    severity: str,
    user_email: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return store.create_or_update(
        event_id=event_id,
        incident_type=incident_type,
        summary=summary,
        severity=severity,
        user_email=user_email,
        metadata=metadata,
    )
