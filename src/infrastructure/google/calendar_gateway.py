"""
Cliente fino sobre a Google Calendar API v3.

Substitui toda a parte da v1 que abria o Google Agenda num Chrome
controlado por automação, clicava em cada card de evento e lia atributos
data-eventid do DOM. Aqui, tudo é obtido com chamadas HTTP estruturadas.
"""

import logging
import re

logger = logging.getLogger(__name__)

REGEX_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def listar_eventos_do_periodo(calendar_service, calendar_id, data_inicio, data_fim):
    """Lista eventos de um intervalo de datas usando events().list().

    Muito mais barato do que a v1, que reabria a visualizacao de cada dia
    do mes no navegador e esperava a pagina renderizar antes de raspar o DOM.
    """
    time_min = data_inicio.isoformat() + "T00:00:00Z"
    time_max = data_fim.isoformat() + "T23:59:59Z"

    eventos = []
    page_token = None
    while True:
        resposta = calendar_service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            pageToken=page_token,
        ).execute()
        eventos.extend(resposta.get("items", []))
        page_token = resposta.get("nextPageToken")
        if not page_token:
            break
    return eventos


def evento_tem_meet(evento: dict) -> bool:
    conference_data = evento.get("conferenceData")
    if not conference_data:
        return False
    for entry_point in conference_data.get("entryPoints", []):
        uri = entry_point.get("uri") or ""
        if entry_point.get("entryPointType") == "video" and "meet.google.com" in uri:
            return True
    return False


def obter_convidados(evento: dict):
    """Extrai a lista de convidados (nome, email) direto do campo attendees.

    Na v1 isso era feito varrendo elementos treeitem no DOM do editor de
    evento. Aqui e so um campo estruturado do JSON devolvido pela API.
    """
    convidados = []
    for attendee in evento.get("attendees", []):
        if attendee.get("organizer"):
            continue
        email = (attendee.get("email") or "").strip()
        nome = attendee.get("displayName") or (email.split("@")[0] if email else "")
        if email:
            convidados.append({"nome": nome, "email": email})
    return convidados


def extrair_emails_da_descricao(evento: dict):
    """Mesma ideia da v1: as vezes o organizador cola e-mails na descricao
    em vez de adicionar convidados formalmente. Continua valendo a pena
    extrair isso com regex, pois e uma heuristica sobre texto livre, e nao
    sobre a interface do Google.
    """
    descricao = evento.get("description", "") or ""
    return sorted(set(REGEX_EMAIL.findall(descricao)))


def atualizar_cor_do_evento(calendar_service, calendar_id, event_id, color_id):
    if color_id is None:
        logger.debug("Cor nao disponivel nesta conta — evento %s nao sera colorido.", event_id)
        return None
    return calendar_service.events().patch(
        calendarId=calendar_id,
        eventId=event_id,
        body={"colorId": color_id},
    ).execute()


def adicionar_convidados_ao_evento(calendar_service, calendar_id, event_id, evento, novos_emails):
    """Adiciona novos convidados (ex: encontrados na descricao) usando
    events().patch(), sem precisar digitar nada em nenhum campo de tela.
    """
    attendees_atuais = evento.get("attendees", [])
    emails_atuais = {(a.get("email") or "").lower() for a in attendees_atuais}
    novos = [{"email": e} for e in novos_emails if e.lower() not in emails_atuais]
    if not novos:
        return evento
    body = {"attendees": attendees_atuais + novos}
    return calendar_service.events().patch(
        calendarId=calendar_id,
        eventId=event_id,
        body=body,
        sendUpdates="none",
    ).execute()
