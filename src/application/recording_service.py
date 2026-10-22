"""
Serviço de gravação: localiza gravações do Meet no Google Drive
e prepara o link de incorporação para publicação na plataforma.

Status: Google Drive (busca) → implementado
        Plataforma AVAMEC (publicação) → pendente (ver TODO abaixo)

Fluxo:
  1. O Meet grava automaticamente no Drive do organizador
     (ativado pelo bot principal via configurar_space)
  2. Job periódico chama rodar_gravacoes() após o término das aulas
  3. Para cada aula processada com sucesso nas últimas 24h, busca
     o arquivo de gravação no Drive por nome e data
  4. Gera link de incorporação e tenta publicar na plataforma
  5. Falha → incidente no dashboard + alerta via Discord/webhook
"""

import datetime
import logging
import sqlite3
from typing import Optional

from src.shared.notifications import (
    DiscordNotificationChannel,
    EmailNotificationChannel,
    GoogleChatNotificationChannel,
    NotificationRouter,
    WebhookNotificationChannel,
)

logger = logging.getLogger(__name__)

_MIME_MEET_RECORDING = "video/mp4"
_NOME_PREFIXO_MEET = "Gravação de"  # padrão do Google Meet em pt-BR


# ── Busca no Drive ─────────────────────────────────────────────────────────────

def buscar_gravacao_no_drive(drive_service, titulo_evento: str, data_evento: datetime.date) -> Optional[dict]:
    """Busca no Google Drive a gravação de um evento pelo título e data.

    Janela de busca: dia do evento + 1 dia seguinte (gravação pode terminar
    após meia-noite e o processamento do Meet leva alguns minutos após o fim).
    """
    data_min = datetime.datetime.combine(data_evento, datetime.time.min).isoformat() + "Z"
    data_max = datetime.datetime.combine(
        data_evento + datetime.timedelta(days=1), datetime.time.max
    ).isoformat() + "Z"

    query = (
        f"mimeType='{_MIME_MEET_RECORDING}'"
        f" and name contains '{_NOME_PREFIXO_MEET}'"
        f" and createdTime >= '{data_min}'"
        f" and createdTime <= '{data_max}'"
        f" and trashed = false"
    )

    try:
        result = drive_service.files().list(
            q=query,
            fields="files(id, name, webViewLink, webContentLink, createdTime)",
            orderBy="createdTime desc",
            pageSize=5,
        ).execute()
        arquivos = result.get("files", [])
        if not arquivos:
            logger.info("Nenhuma gravação encontrada no Drive para '%s' em %s", titulo_evento, data_evento)
            return None

        # Prefere arquivo cujo nome contenha parte do título do evento
        for arquivo in arquivos:
            if titulo_evento.lower()[:20] in arquivo.get("name", "").lower():
                logger.info("Gravação encontrada: %s", arquivo["name"])
                return arquivo

        # Fallback: mais recente do período
        logger.info("Gravação encontrada (sem match de título): %s", arquivos[0]["name"])
        return arquivos[0]

    except Exception as e:
        logger.error("Erro ao buscar gravação no Drive: %s", e)
        return None


def link_incorporacao(arquivo_drive: dict) -> Optional[str]:
    """Gera o link /preview do Drive — adequado para incorporar em iframe."""
    file_id = arquivo_drive.get("id")
    if not file_id:
        return None
    return f"https://drive.google.com/file/d/{file_id}/preview"


def publicar_gravacao_na_plataforma(titulo_evento: str, link: str) -> bool:
    """
    TODO — Publicação na plataforma AVAMEC.

    Para implementar, é necessário:
      1. Confirmar se o Moodle tem Web Services API habilitada
      2. Obter a URL base e token de acesso da plataforma
      3. Identificar o endpoint de criação de recursos de mídia
         (Moodle: mod_resource ou mod_url via Web Services API)
      4. Mapear o título do evento ao ID do curso/turma correspondente

    Enquanto não implementado, loga o link para ação manual.
    Retorna False → incidente é criado no dashboard com o link disponível.
    """
    logger.info("GRAVAÇÃO PRONTA — evento: '%s' | link: %s", titulo_evento, link)
    logger.info("Publicação automática ainda não implementada. Ação manual necessária.")
    return False


# ── Job periódico ──────────────────────────────────────────────────────────────

def rodar_gravacoes(drive_service, gmail_service, config) -> None:
    """Job periódico agendado via recording_schedule.

    Consulta o processing_log das últimas 24h, busca a gravação de cada aula
    no Drive e tenta publicar. Falhas viram incidentes no dashboard e disparam
    alertas nos canais configurados (Discord, webhook, email).
    """
    from src.application.incident_service import IncidentStore, create_incident

    hoje = datetime.date.today()
    store = IncidentStore(config.incidents_db_path)
    router = _criar_router(gmail_service, config)

    with sqlite3.connect(config.incidents_db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT DISTINCT event_id, event_title FROM processing_log
            WHERE status LIKE 'sucesso%'
            AND dry_run = 0
            AND processed_at >= datetime('now', '-24 hours')
        """).fetchall()

    if not rows:
        logger.info("Nenhum evento processado nas últimas 24h — nada a buscar no Drive.")
        return

    logger.info("Buscando gravações para %d evento(s) do dia.", len(rows))

    for row in rows:
        _processar_gravacao(
            drive_service=drive_service,
            store=store,
            router=router,
            event_id=row["event_id"],
            event_title=row["event_title"] or "Evento sem título",
            data=hoje,
        )


def _processar_gravacao(drive_service, store, router, event_id: str, event_title: str, data: datetime.date) -> None:
    from src.application.incident_service import create_incident

    arquivo = buscar_gravacao_no_drive(drive_service, event_title, data)

    if not arquivo:
        logger.warning("Gravação não encontrada no Drive para '%s'.", event_title)
        incidente = create_incident(
            store=store,
            event_id=event_id,
            incident_type="RECORDING_NOT_FOUND",
            summary=f"Gravação não encontrada no Drive para '{event_title}'",
            severity="warning",
            metadata={"meeting_title": event_title},
        )
        router.send(incidente)
        return

    link = link_incorporacao(arquivo)
    logger.info("Gravação encontrada: %s → %s", arquivo.get("name"), link)

    sucesso = publicar_gravacao_na_plataforma(event_title, link)

    if not sucesso:
        incidente = create_incident(
            store=store,
            event_id=event_id,
            incident_type="RECORDING_PUBLISH_FAILED",
            summary=f"Gravação de '{event_title}' pronta — publicação manual necessária",
            severity="warning",
            metadata={
                "meeting_title": event_title,
                "drive_link": arquivo.get("webViewLink", ""),
                "embed_link": link,
                "drive_file_name": arquivo.get("name", ""),
            },
        )
        router.send(incidente)
    else:
        logger.info("Gravação de '%s' publicada com sucesso.", event_title)


def _criar_router(gmail_service, config) -> NotificationRouter:
    canais = []
    if gmail_service:
        canais.append(EmailNotificationChannel(gmail_service))
    if getattr(config, "webhook_url", ""):
        canais.append(WebhookNotificationChannel(config.webhook_url))
    if getattr(config, "discord_webhook_url", ""):
        canais.append(DiscordNotificationChannel(config.discord_webhook_url))
    if getattr(config, "google_chat_webhook_url", ""):
        canais.append(GoogleChatNotificationChannel(config.google_chat_webhook_url))
    return NotificationRouter(canais)
