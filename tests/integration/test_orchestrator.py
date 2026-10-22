"""Testes do orchestrator — caminhos críticos com mocks dos serviços Google."""

from unittest.mock import MagicMock, patch

import pytest

from src.application.incident_service import IncidentStore
from src.application.orchestrator import processar_evento, rodar_bot


def _make_evento(event_id="evt-001", color_id="11", has_meet=True, attendees=None):
    evento = {
        "id": event_id,
        "summary": "Aula de IA",
        "colorId": color_id,
        "attendees": attendees or [{"email": "prof@example.com", "organizer": True}],
        "description": "",
    }
    if has_meet:
        evento["conferenceData"] = {
            "entryPoints": [{"entryPointType": "video", "uri": "https://meet.google.com/abc-def"}]
        }
    return evento


@pytest.fixture
def store(tmp_path):
    return IncidentStore(str(tmp_path / "test.db"))


@pytest.fixture
def calendar_svc():
    svc = MagicMock()
    svc.colors().get().execute.return_value = {
        "event": {"11": {"background": "#616161"}}
    }
    svc.events().list().execute.return_value = {"items": []}
    return svc


@pytest.fixture
def meet_svc():
    svc = MagicMock()
    svc.spaces().get().execute.return_value = {"name": "spaces/abc"}
    svc.spaces().patch().execute.return_value = {}
    svc.spaces().members().create().execute.return_value = {}
    return svc


@pytest.fixture
def gmail_svc():
    svc = MagicMock()
    svc.users().getProfile().execute.return_value = {"emailAddress": "bot@example.com"}
    svc.users().messages().send().execute.return_value = {}
    return svc


# ── processar_evento ────────────────────────────────────────────────────────

def test_processar_evento_sem_convidados_retorna_sucesso(store, calendar_svc, meet_svc):
    evento = _make_evento()
    cores_id = {"pendente": "11", "sucesso_sem_coorganizador": "2",
                "sucesso_com_coorganizador": "3", "falha_coorganizador_aviso": "4",
                "ignorar_manual": "5"}
    resultado = processar_evento(calendar_svc, meet_svc, "primary", evento, cores_id, store)
    assert resultado["status"] == "sucesso_sem_coorganizador"


def test_processar_evento_com_convidado_bem_sucedido(store, calendar_svc, meet_svc):
    evento = _make_evento(attendees=[
        {"email": "org@example.com", "organizer": True},
        {"email": "prof@gmail.com", "organizer": False},
    ])
    cores_id = {"pendente": "11", "sucesso_sem_coorganizador": "2",
                "sucesso_com_coorganizador": "3", "falha_coorganizador_aviso": "4",
                "ignorar_manual": "5"}
    resultado = processar_evento(calendar_svc, meet_svc, "primary", evento, cores_id, store)
    assert resultado["status"] == "sucesso_com_coorganizador"
    assert resultado["falhados"] == []


def test_processar_evento_falha_meet_cria_incidente(store, calendar_svc, meet_svc):
    meet_svc.spaces().get().execute.side_effect = Exception("API indisponível")
    evento = _make_evento()
    cores_id = {"pendente": "11", "sucesso_sem_coorganizador": "2",
                "sucesso_com_coorganizador": "3", "falha_coorganizador_aviso": "4",
                "ignorar_manual": "5"}
    resultado = processar_evento(calendar_svc, meet_svc, "primary", evento, cores_id, store)
    assert resultado["status"] == "falha_configuracao"
    incidentes = store.list_incidents(include_resolved=True)
    assert len(incidentes) == 1
    assert incidentes[0]["type"] == "MEET_SPACE_CONFIG_FAILED"


def test_processar_evento_falha_cohost_cria_incidente(store, calendar_svc, meet_svc):
    meet_svc.spaces().members().create().execute.side_effect = Exception("403 Forbidden")
    evento = _make_evento(attendees=[
        {"email": "org@example.com", "organizer": True},
        {"email": "prof@hotmail.com", "organizer": False},
    ])
    cores_id = {"pendente": "11", "sucesso_sem_coorganizador": "2",
                "sucesso_com_coorganizador": "3", "falha_coorganizador_aviso": "4",
                "ignorar_manual": "5"}
    resultado = processar_evento(calendar_svc, meet_svc, "primary", evento, cores_id, store)
    assert resultado["status"] == "falha_parcial"
    assert len(resultado["falhados"]) == 1
    incidentes = store.list_incidents(include_resolved=True)
    assert any(i["type"] == "COHOST_ASSIGNMENT_FAILED" for i in incidentes)


# ── rodar_bot ───────────────────────────────────────────────────────────────

def _make_config(tmp_path):
    from src.shared.config import Config
    # Paleta com todos os colorIds usados pelo bot
    return Config(
        calendar_id="primary", days_ahead=1, days_behind=0,
        report_email_override="", credentials_path="c.json",
        token_path="t.json", log_level="WARNING",
        incidents_db_path=str(tmp_path / "bot.db"),
    )


def _paleta_mock():
    return {
        "event": {
            "11": {"background": "#616161"},   # Graphite = pendente
            "2":  {"background": "#f6c026"},   # Banana
            "3":  {"background": "#9a6ade"},   # Grape
            "4":  {"background": "#d60000"},   # Tomato
            "5":  {"background": "#4a86e8"},   # Peacock
        }
    }


def test_rodar_bot_pula_eventos_sem_meet(calendar_svc, meet_svc, gmail_svc, tmp_path):
    config = _make_config(tmp_path)
    calendar_svc.colors().get().execute.return_value = _paleta_mock()
    calendar_svc.events().list().execute.return_value = {
        "items": [_make_evento(has_meet=False, color_id="11")]
    }
    rodar_bot(calendar_svc, meet_svc, gmail_svc, config)
    assert IncidentStore(config.incidents_db_path).list_incidents(include_resolved=True) == []


def test_rodar_bot_pula_eventos_nao_pendentes(calendar_svc, meet_svc, gmail_svc, tmp_path):
    config = _make_config(tmp_path)
    calendar_svc.colors().get().execute.return_value = _paleta_mock()
    calendar_svc.events().list().execute.return_value = {
        "items": [_make_evento(color_id="3")]  # não é Grafite
    }
    rodar_bot(calendar_svc, meet_svc, gmail_svc, config)
    assert IncidentStore(config.incidents_db_path).list_incidents(include_resolved=True) == []
