"""
Caso de uso: configura uma reunião do Meet.

Orquestra a sequência: resolver espaço → configurar acesso → promover convidados.
Sem dependências de infraestrutura direta — recebe os gateways como parâmetros.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def executar(
    *,
    meet_service,
    calendar_service,
    calendar_id: str,
    evento: Dict[str, Any],
    cores_id: Dict[str, str],
    incident_store=None,
    notification_router=None,
) -> Dict[str, Any]:
    """Delega para o orchestrator existente mantendo compatibilidade."""
    from src.orchestrator import processar_evento
    return processar_evento(
        calendar_service, meet_service, calendar_id,
        evento, cores_id,
        incident_store=incident_store,
        notification_router=notification_router,
    )
