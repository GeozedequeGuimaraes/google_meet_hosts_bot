"""
Camada única de autenticação OAuth2.

Diferente da v1 (que só autenticava o Gmail e reaproveitava um perfil de
navegador para o Calendar), aqui autenticamos uma única vez com todos os
escopos necessários para falar diretamente com as APIs REST do Google
(Calendar, Meet e Gmail), sem precisar abrir nenhum navegador controlado
por automação.
"""

import base64
import os
import logging
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/meetings.space.created",
    "https://www.googleapis.com/auth/meetings.space.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _preparar_arquivos_de_credenciais(credentials_path: str, token_path: str) -> None:
    """Decodifica credenciais de env vars para arquivos quando rodando no Render/Cloud."""
    creds_b64 = os.getenv("GOOGLE_CREDENTIALS_B64")
    token_b64 = os.getenv("GOOGLE_TOKEN_B64")
    if creds_b64 and not os.path.exists(credentials_path):
        os.makedirs(os.path.dirname(credentials_path) or ".", exist_ok=True)
        with open(credentials_path, "w", encoding="utf-8") as f:
            f.write(base64.b64decode(creds_b64).decode())
        logger.info("credentials.json gravado a partir de variável de ambiente.")
    if token_b64 and not os.path.exists(token_path):
        os.makedirs(os.path.dirname(token_path) or ".", exist_ok=True)
        with open(token_path, "w", encoding="utf-8") as f:
            f.write(base64.b64decode(token_b64).decode())
        logger.info("token.json gravado a partir de variável de ambiente.")


def obter_credenciais(credentials_path: str, token_path: str) -> Credentials:
    _preparar_arquivos_de_credenciais(credentials_path, token_path)
    creds = None
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception as e:
            logger.warning("Não foi possível carregar token salvo: %s", e)
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.warning("Falha ao renovar token, será feito novo login: %s", e)
                creds = None

        if not creds:
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    "Arquivo de credenciais nao encontrado em: " + credentials_path
                )
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0, prompt="consent")
            with open(token_path, "w", encoding="utf-8") as f:
                f.write(creds.to_json())

    return creds


def construir_servicos(credentials_path: str, token_path: str):
    creds = obter_credenciais(credentials_path, token_path)
    calendar_service = build("calendar", "v3", credentials=creds)
    meet_service = build("meet", "v2", credentials=creds)
    gmail_service = build("gmail", "v1", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)
    return calendar_service, meet_service, gmail_service, drive_service
