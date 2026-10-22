"""
Envio de e-mails via Gmail API.

A logica de negocio (quando enviar, para quem, o texto) e a mesma da v1;
a unica mudanca e que o servico Gmail agora compartilha a mesma sessao
OAuth2 usada para Calendar e Meet (ver src/google_auth.py), em vez de ter
um fluxo de autenticacao proprio e separado.
"""

import base64
import logging
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def _montar_mensagem(destinatario: str, assunto: str, corpo: str) -> dict:
    mensagem = MIMEText(corpo, "plain", "utf-8")
    mensagem["to"] = destinatario
    mensagem["subject"] = assunto
    raw = base64.urlsafe_b64encode(mensagem.as_bytes()).decode("utf-8")
    return {"raw": raw}


def _saudacao(nome: str) -> str:
    """Retorna o nome se parece um nome real (tem espaço), senão usa saudação genérica."""
    nome = (nome or "").strip()
    if " " in nome:
        return f"Prezada(o) {nome}"
    return "Prezada(o) professor(a)"


def enviar_email_coorganizador(gmail_service, email_destinatario, nome_destinatario):
    assunto = "Configuração de reunião no Google Meet — AVAMEC Interativo"
    corpo = (
        _saudacao(nome_destinatario) + ",\n\n"
        "Identificamos que não foi possível adicionar o seu e-mail como "
        "coorganizador(a) da reunião no Google Meet.\n\n"
        "Isso ocorre porque o endereço informado não é vinculado a uma conta "
        "Google (Gmail ou Google Workspace). Para que você tenha acesso às "
        "opções de coorganização e gravação, pedimos que informe um e-mail "
        "Gmail ou institucional Google ao responsável pelo seu encontro.\n\n"
        "Atenciosamente,\nEquipe de Assessoria Pedagógica — V-Lab UFPE"
    )
    corpo_mensagem = _montar_mensagem(email_destinatario, assunto, corpo)
    try:
        gmail_service.users().messages().send(userId="me", body=corpo_mensagem).execute()
        logger.info("E-mail de aviso enviado para %s", email_destinatario)
        return True
    except Exception as e:
        logger.error("Falha ao enviar e-mail para %s: %s", email_destinatario, e)
        return False


def enviar_relatorio(gmail_service, email_destinatario, eventos_manuais, eventos_com_falha):
    if not eventos_manuais and not eventos_com_falha:
        return True

    assunto = "Relatorio de Eventos - Bot Meet v2"
    linhas = ["Resumo dos eventos processados:", ""]
    if eventos_manuais:
        linhas.append("Eventos marcados para tratamento manual:")
        linhas.extend([" - " + e for e in eventos_manuais])
        linhas.append("")
    if eventos_com_falha:
        linhas.append("Eventos com falha ao adicionar coorganizador:")
        linhas.extend([" - " + e for e in eventos_com_falha])
        linhas.append("")
    linhas.append("Atenciosamente,\nBot de Configuracao do Google Meet v2")
    corpo = "\n".join(linhas)

    corpo_mensagem = _montar_mensagem(email_destinatario, assunto, corpo)
    try:
        gmail_service.users().messages().send(userId="me", body=corpo_mensagem).execute()
        logger.info("Relatorio enviado para %s", email_destinatario)
        return True
    except Exception as e:
        logger.error("Falha ao enviar relatorio: %s", e)
        return False
