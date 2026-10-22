

"""
Orquestrador principal: substitui o loop gigante da v1 (rodar_bot_google)
por uma sequencia de chamadas de API, sem navegador nenhum.
"""

import logging
import datetime
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from src.shared.retry import with_backoff

_MAX_WORKERS = 10  # paralela segura sem estourar rate limits da Google API

from src.infrastructure.google.calendar_gateway import (
    listar_eventos_do_periodo,
    evento_tem_meet,
    obter_convidados,
    extrair_emails_da_descricao,
    adicionar_convidados_ao_evento,
    atualizar_cor_do_evento,
)
from src.infrastructure.google.meet_gateway import resolver_nome_do_space_com_servico, configurar_space, promover_convidados
from src.infrastructure.google.color_state import resolver_color_id_por_nome, STATUS_NOMES
from src.infrastructure.google.gmail_gateway import enviar_email_coorganizador, enviar_relatorio
from src.application.incident_service import IncidentStore, create_incident
from src.shared.notifications import (
    DiscordNotificationChannel,
    EmailNotificationChannel,
    GoogleChatNotificationChannel,
    NotificationRouter,
    WebhookNotificationChannel,
)

logger = logging.getLogger(__name__)


def _criar_router_notificacoes(gmail_service=None, webhook_url=None, discord_webhook_url=None, google_chat_webhook_url=None):
    canais = []
    if gmail_service is not None:
        canais.append(EmailNotificationChannel(gmail_service))
    if webhook_url:
        canais.append(WebhookNotificationChannel(webhook_url))
    if discord_webhook_url:
        canais.append(DiscordNotificationChannel(discord_webhook_url))
    if google_chat_webhook_url:
        canais.append(GoogleChatNotificationChannel(google_chat_webhook_url))
    return NotificationRouter(canais)


_DOMINIOS_EXTERNOS = {"hotmail.com", "outlook.com", "yahoo.com", "icloud.com", "live.com"}


def _gerar_summary(incident_type: str, titulo: str, *, email: str = None, motivo: str = None) -> str:
    if incident_type == "COHOST_ASSIGNMENT_FAILED":
        if email:
            dominio = email.split("@")[-1].lower()
            if dominio in _DOMINIOS_EXTERNOS:
                return f"E-mail externo não aceito pelo Meet: {email}"
            if motivo and "PERMISSION" in motivo.upper():
                return f"Sem permissão para adicionar {email} como coorganizador"
            if motivo and ("NOT_FOUND" in motivo.upper() or "404" in motivo):
                return f"Usuário não encontrado no Google: {email}"
        return f"Falha ao adicionar {email or 'convidado'} como coorganizador"

    if incident_type == "MEET_SPACE_CONFIG_FAILED":
        erro = motivo or ""
        campo = re.search(r'Unknown name ["\']?(\w+)["\']?', erro)
        if campo:
            return f"Campo inválido na API do Meet: {campo.group(1)}"
        if "PERMISSION_DENIED" in erro or '"403"' in erro or "HttpError 403" in erro:
            return f"Sem permissão para configurar o Meet de '{titulo}'"
        if "NOT_FOUND" in erro or "HttpError 404" in erro:
            return f"Espaço do Meet não encontrado para '{titulo}'"
        match = re.search(r"HttpError (\d+)", erro)
        if match:
            return f"Erro {match.group(1)} ao configurar o Meet de '{titulo}'"
        return f"Falha ao configurar o Meet de '{titulo}'"

    return f"Incidente em '{titulo}'"


def _gerar_tags(incident_type: str, evento: dict, incidente: dict, user_email: str = None) -> list:
    tags = []

    start = evento.get("start", {})
    data_str = start.get("dateTime", start.get("date", ""))
    if data_str:
        try:
            if datetime.date.fromisoformat(data_str[:10]) == datetime.date.today():
                tags.append("encontro-hoje")
        except ValueError:
            pass

    if incident_type == "COHOST_ASSIGNMENT_FAILED":
        tags.append("email-externo")
        if user_email:
            dominio = user_email.split("@")[-1].lower()
            if dominio in _DOMINIOS_EXTERNOS:
                tags.append(dominio.split(".")[0])  # ex: hotmail, outlook
    elif incident_type == "MEET_SPACE_CONFIG_FAILED":
        tags.append("meet-falhou")

    if incidente.get("retries", 0) > 1:
        tags.append("retentativa")

    return tags


def processar_evento(calendar_service, meet_service, calendar_id, evento, cores_id, incident_store=None, notification_router=None, dry_run=False):
    event_id = evento["id"]
    titulo = evento.get("summary", "Evento sem titulo")
    logger.info("Processando evento: %s", titulo)

    convidados = obter_convidados(evento)

    emails_da_descricao = extrair_emails_da_descricao(evento)
    emails_atuais = {c["email"].lower() for c in convidados}
    novos_emails = [e for e in emails_da_descricao if e.lower() not in emails_atuais]
    if novos_emails:
        evento = adicionar_convidados_ao_evento(calendar_service, calendar_id, event_id, evento, novos_emails)
        for email in novos_emails:
            convidados.append({"nome": email.split("@")[0], "email": email})

    _resolver = with_backoff(max_attempts=3, base_delay=2.0)(resolver_nome_do_space_com_servico)
    _configurar = with_backoff(max_attempts=3, base_delay=2.0)(configurar_space)

    try:
        space_name = _resolver(meet_service, evento)
        if dry_run:
            logger.info("[DRY RUN] Configuraria o Meet de '%s' (%s)", titulo, space_name)
        else:
            _configurar(meet_service, space_name)
    except Exception as e:
        logger.error("Nao foi possivel configurar o espaco do Meet para '%s': %s", titulo, e)
        if incident_store is not None:
            incidente = create_incident(
                store=incident_store,
                event_id=event_id,
                incident_type="MEET_SPACE_CONFIG_FAILED",
                summary=_gerar_summary("MEET_SPACE_CONFIG_FAILED", titulo, motivo=str(e)),
                severity="error",
                user_email=None,
                metadata={"title": titulo, "reason": str(e)},
            )
            tags = _gerar_tags("MEET_SPACE_CONFIG_FAILED", evento, incidente)
            if tags:
                incident_store.add_tags(incidente["id"], tags)
            if notification_router is not None:
                notification_router.send(incidente)
        if not dry_run:
            atualizar_cor_do_evento(calendar_service, calendar_id, event_id, cores_id["falha_coorganizador_aviso"])
        if incident_store is not None:
            incident_store.log_processing(event_id, titulo, "falha_configuracao", dry_run=dry_run)
        return {"status": "falha_configuracao", "titulo": titulo, "falhados": convidados}

    if not convidados:
        if not dry_run:
            atualizar_cor_do_evento(calendar_service, calendar_id, event_id, cores_id["sucesso_sem_coorganizador"])
        if incident_store is not None:
            incident_store.log_processing(event_id, titulo, "sucesso_sem_coorganizador", dry_run=dry_run)
        return {"status": "sucesso_sem_coorganizador", "titulo": titulo, "falhados": []}

    if dry_run:
        logger.info("[DRY RUN] Adicionaria como co-org: %s", [c["email"] for c in convidados])
        return {"status": "sucesso_com_coorganizador", "titulo": titulo, "falhados": []}

    _, falhados = promover_convidados(meet_service, space_name, convidados)

    if falhados:
        if incident_store is not None:
            for convidado in falhados:
                incidente = create_incident(
                    store=incident_store,
                    event_id=event_id,
                    incident_type="COHOST_ASSIGNMENT_FAILED",
                    summary=_gerar_summary("COHOST_ASSIGNMENT_FAILED", titulo, email=convidado.get("email"), motivo=convidado.get("motivo")),
                    severity="warning",
                    user_email=convidado.get("email"),
                    metadata={"title": titulo, "reason": convidado.get("motivo") or "cohost_assignment_failed"},
                )
                tags = _gerar_tags("COHOST_ASSIGNMENT_FAILED", evento, incidente, user_email=convidado.get("email"))
                if tags:
                    incident_store.add_tags(incidente["id"], tags)
                if notification_router is not None:
                    notification_router.send(incidente)
        if not dry_run:
            atualizar_cor_do_evento(calendar_service, calendar_id, event_id, cores_id["falha_coorganizador_aviso"])
        status = "falha_parcial"
    else:
        if not dry_run:
            atualizar_cor_do_evento(calendar_service, calendar_id, event_id, cores_id["sucesso_com_coorganizador"])
        status = "sucesso_com_coorganizador"

    if incident_store is not None:
        incident_store.log_processing(event_id, titulo, status, dry_run=dry_run)
    return {"status": status, "titulo": titulo, "falhados": falhados}


def rodar_bot(calendar_service, meet_service, gmail_service, config):
    hoje = datetime.date.today()
    data_inicio = hoje - datetime.timedelta(days=config.days_behind)
    data_fim = hoje + datetime.timedelta(days=config.days_ahead)

    incident_store = IncidentStore(getattr(config, "incidents_db_path", "incidents.db"))
    notification_router = _criar_router_notificacoes(
        gmail_service=gmail_service,
        webhook_url=getattr(config, "webhook_url", None),
        discord_webhook_url=getattr(config, "discord_webhook_url", None),
        google_chat_webhook_url=getattr(config, "google_chat_webhook_url", None),
    )

    logger.info("Buscando eventos entre %s e %s", data_inicio, data_fim)
    eventos = listar_eventos_do_periodo(calendar_service, config.calendar_id, data_inicio, data_fim)
    logger.info("Encontrados %d eventos no periodo.", len(eventos))

    cores_id = {
        chave: resolver_color_id_por_nome(calendar_service, nome)
        for chave, nome in STATUS_NOMES.items()
    }

    eventos_manuais: list = []
    eventos_com_falha: list = []
    _lock = Lock()

    # Cores que indicam evento já processado — bot não toca de novo
    # None é excluído: cor ausente na paleta não deve bloquear eventos novos
    cores_ja_processadas = {
        c for c in [
            cores_id["sucesso_com_coorganizador"],
            cores_id["sucesso_sem_coorganizador"],
            cores_id["falha_coorganizador_aviso"],
        ] if c is not None
    }

    # Filtra apenas os eventos que precisam de processamento:
    # - sem cor (recém-criados pela plataforma) OU com cor "pendente" (Graphite)
    # - excluindo os já processados e os marcados para tratamento manual
    pendentes = []
    for evento in eventos:
        color_id_atual = evento.get("colorId")
        if color_id_atual in cores_ja_processadas:
            continue
        ignorar_id = cores_id["ignorar_manual"]
        if ignorar_id is not None and color_id_atual == ignorar_id:
            eventos_manuais.append(evento.get("summary", "Evento sem titulo"))
            continue
        if not evento_tem_meet(evento):
            continue
        pendentes.append(evento)

    dry_run = getattr(config, "dry_run", False)
    if dry_run:
        logger.info("*** MODO DRY RUN — nenhuma reunião será modificada ***")

    logger.info("Eventos pendentes para configurar: %d", len(pendentes))

    def _processar(evento):
        return processar_evento(
            calendar_service, meet_service, config.calendar_id,
            evento, cores_id,
            incident_store=incident_store,
            notification_router=notification_router,
            dry_run=dry_run,
        )

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        futuros = {executor.submit(_processar, ev): ev for ev in pendentes}
        for futuro in as_completed(futuros):
            try:
                resultado = futuro.result()
            except Exception as exc:
                titulo = futuros[futuro].get("summary", "Evento sem titulo")
                logger.error("Erro inesperado ao processar '%s': %s", titulo, exc)
                continue
            if resultado["status"] == "falha_configuracao":
                # Falha na configuração do Meet — problema técnico, não do e-mail do convidado.
                # Não envia e-mail para os convidados pois eles não têm culpa.
                with _lock:
                    eventos_com_falha.append(resultado["titulo"])
            elif resultado["status"] == "falha_parcial":
                with _lock:
                    eventos_com_falha.append(resultado["titulo"])
                if not dry_run:
                    for convidado in resultado["falhados"]:
                        enviar_email_coorganizador(gmail_service, convidado["email"], convidado["nome"])
                else:
                    for convidado in resultado["falhados"]:
                        logger.info("[DRY RUN] Enviaria e-mail de aviso para %s", convidado["email"])

    if (eventos_manuais or eventos_com_falha) and config.report_email_override:
        enviar_relatorio(gmail_service, config.report_email_override, eventos_manuais, eventos_com_falha)

    logger.info(
        "Processamento concluido. Manuais: %d. Falhas: %d.",
        len(eventos_manuais), len(eventos_com_falha)
    )
