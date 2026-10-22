"""
Caso de uso: registra e deduplica incidentes.

Ponto de entrada único para criação de incidentes — garante que todo código
de negócio que cria incidentes passe por aqui.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.incidents import IncidentStore, create_incident


def registrar(
    *,
    store: IncidentStore,
    event_id: str,
    incident_type: str,
    summary: str,
    severity: str,
    user_email: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return create_incident(
        store=store,
        event_id=event_id,
        incident_type=incident_type,
        summary=summary,
        severity=severity,
        user_email=user_email,
        metadata=metadata,
    )
