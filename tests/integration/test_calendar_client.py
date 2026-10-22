"""Testes do calendar_client — extração e manipulação de dados do Calendar API."""

from unittest.mock import MagicMock

from src.infrastructure.google.calendar_gateway import (
    adicionar_convidados_ao_evento,
    evento_tem_meet,
    extrair_emails_da_descricao,
    listar_eventos_do_periodo,
    obter_convidados,
)


def _evento_com_meet(**kwargs):
    base = {
        "id": "evt-1",
        "summary": "Aula",
        "attendees": [],
        "description": "",
        "conferenceData": {
            "entryPoints": [
                {"entryPointType": "video", "uri": "https://meet.google.com/abc-def-ghi"}
            ]
        },
    }
    base.update(kwargs)
    return base


# ── evento_tem_meet ──────────────────────────────────────────────────────────

def test_evento_com_meet_retorna_true():
    assert evento_tem_meet(_evento_com_meet()) is True


def test_evento_sem_conference_data_retorna_false():
    assert evento_tem_meet({"id": "x", "summary": "s"}) is False


def test_evento_com_entry_point_nao_video_retorna_false():
    evento = {
        "conferenceData": {
            "entryPoints": [{"entryPointType": "phone", "uri": "tel:+55"}]
        }
    }
    assert evento_tem_meet(evento) is False


# ── obter_convidados ──────────────────────────────────────────────────────────

def test_obter_convidados_exclui_organizador():
    evento = _evento_com_meet(attendees=[
        {"email": "org@example.com", "organizer": True},
        {"email": "prof@example.com", "displayName": "Prof Silva"},
    ])
    convidados = obter_convidados(evento)
    assert len(convidados) == 1
    assert convidados[0]["email"] == "prof@example.com"
    assert convidados[0]["nome"] == "Prof Silva"


def test_obter_convidados_usa_email_como_nome_fallback():
    evento = _evento_com_meet(attendees=[
        {"email": "aluno@example.com"},
    ])
    convidados = obter_convidados(evento)
    assert convidados[0]["nome"] == "aluno"


def test_obter_convidados_evento_sem_attendees_retorna_vazio():
    assert obter_convidados({"id": "x"}) == []


# ── extrair_emails_da_descricao ───────────────────────────────────────────────

def test_extrair_emails_simples():
    evento = _evento_com_meet(description="Contato: prof@ufpe.br e monitor@cin.ufpe.br")
    emails = extrair_emails_da_descricao(evento)
    assert "prof@ufpe.br" in emails
    assert "monitor@cin.ufpe.br" in emails


def test_extrair_emails_sem_descricao_retorna_vazio():
    assert extrair_emails_da_descricao({"id": "x"}) == []


def test_extrair_emails_sem_emails_retorna_vazio():
    assert extrair_emails_da_descricao(_evento_com_meet(description="Sem email aqui")) == []


# ── listar_eventos_do_periodo ─────────────────────────────────────────────────

def test_listar_eventos_do_periodo_pagina():
    import datetime
    svc = MagicMock()
    svc.events().list().execute.side_effect = [
        {"items": [{"id": "a"}], "nextPageToken": "tok"},
        {"items": [{"id": "b"}]},
    ]
    eventos = listar_eventos_do_periodo(
        svc, "primary",
        datetime.date(2026, 9, 1),
        datetime.date(2026, 9, 30),
    )
    assert len(eventos) == 2
    assert eventos[0]["id"] == "a"
    assert eventos[1]["id"] == "b"


# ── adicionar_convidados_ao_evento ────────────────────────────────────────────

def test_adicionar_convidados_nao_duplica():
    svc = MagicMock()
    evento = _evento_com_meet(attendees=[{"email": "existente@example.com"}])
    resultado = adicionar_convidados_ao_evento(
        svc, "primary", "evt-1", evento, ["existente@example.com"]
    )
    # Nenhum patch deve ser disparado quando o email já existe
    svc.events().patch.assert_not_called()
    assert resultado is evento


def test_adicionar_convidados_novo_email_chama_patch():
    svc = MagicMock()
    svc.events().patch().execute.return_value = {"id": "evt-1"}
    evento = _evento_com_meet(attendees=[{"email": "existente@example.com"}])
    adicionar_convidados_ao_evento(
        svc, "primary", "evt-1", evento, ["novo@example.com"]
    )
    assert svc.events().patch.call_count >= 1
