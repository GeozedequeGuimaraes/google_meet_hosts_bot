"""
Sistema de migrations para o schema SQLite.

Usa PRAGMA user_version como número de versão. Cada migration é uma função
pura que recebe uma Connection e aplica exatamente uma mudança atômica.

Como adicionar uma migration:
    1. Escreva uma função `def mXXX_descricao(conn): ...`
    2. Adicione-a à lista MIGRATIONS na ordem correta.
    3. Nunca altere migrations já aplicadas — crie uma nova.
"""

import logging
import sqlite3
from typing import Callable, List, Tuple

logger = logging.getLogger(__name__)

Migration = Tuple[int, str, Callable[[sqlite3.Connection], None]]


# ── Migrations ────────────────────────────────────────────────────────────────
# Formato: (versão, descrição, função)

def _m001_schema_inicial(conn: sqlite3.Connection) -> None:
    """Schema base criado na v2 — incidents, reprocess_jobs, config_settings."""
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


def _m002_incidents_index_event_status(conn: sqlite3.Connection) -> None:
    """Índice composto para acelerar buscas por (event_id, status)."""
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_incidents_event_status
        ON incidents (event_id, status)
    """)


def _m003_incidents_index_last_seen(conn: sqlite3.Connection) -> None:
    """Índice em last_seen para ordenação DESC eficiente."""
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_incidents_last_seen
        ON incidents (last_seen DESC)
    """)


def _m004_processing_log(conn: sqlite3.Connection) -> None:
    """Log de cada reunião processada pelo bot — registra sucessos e falhas."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processing_log (
            id          TEXT PRIMARY KEY,
            event_id    TEXT NOT NULL,
            event_title TEXT,
            processed_at TEXT NOT NULL,
            status      TEXT NOT NULL,
            dry_run     INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_processing_log_processed_at
        ON processing_log (processed_at DESC)
    """)


MIGRATIONS: List[Migration] = [
    (1, "schema inicial",                      _m001_schema_inicial),
    (2, "índice event_id+status em incidents", _m002_incidents_index_event_status),
    (3, "índice last_seen em incidents",        _m003_incidents_index_last_seen),
    (4, "log de processamento de reuniões",    _m004_processing_log),
]


# ── Runner ────────────────────────────────────────────────────────────────────

def get_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def set_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(f"PRAGMA user_version = {version}")


def run_migrations(db_path: str) -> None:
    """Aplica todas as migrations pendentes de forma atômica."""
    with sqlite3.connect(db_path) as conn:
        current = get_version(conn)
        pending = [(v, desc, fn) for v, desc, fn in MIGRATIONS if v > current]

        if not pending:
            logger.debug("Schema atualizado (versão %d). Nenhuma migration pendente.", current)
            return

        for version, description, migration_fn in pending:
            logger.info("Aplicando migration v%d: %s", version, description)
            migration_fn(conn)
            set_version(conn, version)
            conn.commit()
            logger.info("Migration v%d aplicada com sucesso.", version)
