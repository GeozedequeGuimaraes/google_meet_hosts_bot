import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.infrastructure.google.calendar_gateway import extrair_emails_da_descricao


def test_extrai_emails_simples():
    evento = {"description": "Participantes: fulano@example.com e ciclano@example.org"}
    emails = extrair_emails_da_descricao(evento)
    assert "fulano@example.com" in emails
    assert "ciclano@example.org" in emails


def test_sem_email_retorna_lista_vazia():
    evento = {"description": "Reuniao de planejamento, sem contatos aqui."}
    assert extrair_emails_da_descricao(evento) == []


def test_evento_sem_descricao_nao_quebra():
    evento = {}
    assert extrair_emails_da_descricao(evento) == []
