"""
Migração pontual: regenera o campo summary dos incidentes existentes
usando _gerar_summary, que produz texto mais útil que o genérico original.

Uso:
    python scripts/migrar_summaries.py
    python scripts/migrar_summaries.py --db data/incidents.db
    python scripts/migrar_summaries.py --dry-run
"""

import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.application.orchestrator import _gerar_summary


def migrar(db_path: str, dry_run: bool) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, type, user_email, summary, metadata FROM incidents").fetchall()

    atualizados = 0
    for row in rows:
        meta = json.loads(row["metadata"] or "{}")
        titulo = meta.get("title") or row["summary"]
        motivo = meta.get("reason")
        email  = row["user_email"]

        novo = _gerar_summary(row["type"], titulo, email=email, motivo=motivo)

        if novo == row["summary"]:
            continue

        print(f"  {row['id'][:50]}")
        print(f"    antes:  {row['summary'][:80]}")
        print(f"    depois: {novo[:80]}")

        if not dry_run:
            conn.execute("UPDATE incidents SET summary = ? WHERE id = ?", (novo, row["id"]))
        atualizados += 1

    if not dry_run:
        conn.commit()

    conn.close()
    modo = "[DRY RUN] " if dry_run else ""
    print(f"\n{modo}{atualizados} incidente(s) atualizados em '{db_path}'.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db",      default=os.getenv("INCIDENTS_DB", "data/incidents.db"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    migrar(args.db, args.dry_run)
