"""
Reprocessamento imediato de um incidente específico.

Chamado pelo dashboard quando a equipe clica "Reprocessar". Roda como
background task do FastAPI — não bloqueia a resposta HTTP.

Fluxo:
  1. Autentica com Google (reutiliza token existente)
  2. Busca o evento no Calendar pelo event_id do incidente
  3. Chama processar_evento (mesma lógica do ciclo normal do bot)
  4. Atualiza o status do reprocess_job no banco
"""

import datetime
import logging
import sqlite3

logger = logging.getLogger(__name__)


def reprocessar_incidente(
    *,
    incident_id: str,
    event_id: str,
    db_path: str,
    credentials_path: str,
    token_path: str,
    config,
) -> None:
    """Executa o reprocessamento de um evento específico.

    Projetado para rodar como FastAPI BackgroundTask — qualquer exceção
    não propagada é logada e registrada no job, sem derrubar o servidor.
    """
    from src.infrastructure.google.auth import construir_servicos
    from src.infrastructure.google.calendar_gateway import listar_eventos_do_periodo
    from src.infrastructure.google.color_state import resolver_color_id_por_nome, STATUS_NOMES
    from src.application.orchestrator import processar_evento
    from src.application.incident_service import IncidentStore

    logger.info("Reprocessamento iniciado — incidente=%s evento=%s", incident_id, event_id)
    store = IncidentStore(db_path)

    try:
        calendar, meet, _gmail, _drive = construir_servicos(credentials_path, token_path)

        # Janela ampla para encontrar o evento independente da data
        hoje = datetime.date.today()
        eventos = listar_eventos_do_periodo(
            calendar, config.calendar_id,
            hoje - datetime.timedelta(days=60),
            hoje + datetime.timedelta(days=60),
        )
        evento = next((e for e in eventos if e["id"] == event_id), None)

        if not evento:
            logger.warning("Evento %s não encontrado no Calendar", event_id)
            _set_job_status(db_path, incident_id, "failed", "Evento não encontrado no Calendar")
            return

        cores_id = {
            chave: resolver_color_id_por_nome(calendar, nome)  # pode ser None em contas sem Workspace
            for chave, nome in STATUS_NOMES.items()
        }

        # incident_store=None: evita criar incidente duplicado durante reprocessamento.
        # O incidente original é atualizado manualmente abaixo conforme o resultado.
        resultado = processar_evento(
            calendar, meet, config.calendar_id,
            evento, cores_id,
            incident_store=None,
            notification_router=None,
        )

        sucesso = resultado["status"].startswith("sucesso")

        if sucesso:
            store.resolve_incident(incident_id)
        else:
            store.mark_retried(incident_id)  # sinaliza que a tentativa ocorreu sem mudar status

        _set_job_status(
            db_path, incident_id,
            "success" if sucesso else "failed",
            resultado["status"],
        )
        logger.info("Reprocessamento concluído — %s: %s", incident_id, resultado["status"])

    except Exception as e:
        logger.error("Erro no reprocessamento de %s: %s", incident_id, e)
        _set_job_status(db_path, incident_id, "failed", str(e))


def _set_job_status(db_path: str, incident_id: str, status: str, error: str = None) -> None:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with sqlite3.connect(db_path) as conn:
        # Atualiza o job mais recente em fila para este incidente
        row = conn.execute(
            """SELECT id FROM reprocess_jobs
               WHERE incident_id = ? AND status = 'queued'
               ORDER BY requested_at DESC LIMIT 1""",
            (incident_id,),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE reprocess_jobs SET status = ?, finished_at = ?, error = ? WHERE id = ?",
                (status, now, error, row[0]),
            )
            conn.commit()
