"""
Diagnóstico das APIs do Google antes de rodar o bot em produção.

Uso:
    python scripts/verificar_api.py

O que verifica:
  1. Autenticação OAuth (credentials.json + token.json)
  2. Calendar API — lista eventos da próxima semana
  3. Meet API — tenta ler um space existente e confirma se COHOST está disponível
  4. Gmail API — envia e-mail de teste para o próprio endereço autenticado

Nenhuma reunião é modificada. É seguro rodar em produção.
"""

import sys
import os

# Permite rodar da raiz do projeto sem instalar o pacote
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datetime
from src.shared.config import load_config
from src.infrastructure.google.auth import construir_servicos
from src.infrastructure.google.calendar_gateway import listar_eventos_do_periodo, evento_tem_meet
from src.infrastructure.google.meet_gateway import resolver_nome_do_space_com_servico


def ok(msg):   print(f"  ✓  {msg}")
def falha(msg): print(f"  ✗  {msg}")
def info(msg):  print(f"     {msg}")


def verificar_auth(config):
    print("\n[1] Autenticação OAuth")
    try:
        calendar, meet, gmail = construir_servicos(config.credentials_path, config.token_path)
        ok("credentials.json lido e token gerado/renovado com sucesso")
        return calendar, meet, gmail
    except FileNotFoundError as e:
        falha(str(e))
        falha("Coloque o credentials.json na raiz do projeto e rode novamente.")
        sys.exit(1)
    except Exception as e:
        falha(f"Falha na autenticação: {e}")
        sys.exit(1)


def verificar_calendar(calendar_service, config):
    print("\n[2] Calendar API")
    try:
        hoje = datetime.date.today()
        eventos = listar_eventos_do_periodo(
            calendar_service, config.calendar_id, hoje, hoje + datetime.timedelta(days=7)
        )
        ok(f"Conexão OK — {len(eventos)} evento(s) encontrado(s) nos próximos 7 dias")
        com_meet = [e for e in eventos if evento_tem_meet(e)]
        info(f"{len(com_meet)} desse(s) têm link do Meet")
        return com_meet
    except Exception as e:
        falha(f"Erro ao acessar Calendar API: {e}")
        return []


def verificar_meet(meet_service, eventos_com_meet):
    print("\n[3] Meet API — disponibilidade de COHOST")
    if not eventos_com_meet:
        info("Nenhum evento com Meet nos próximos 7 dias para testar — pulando")
        info("Crie um evento de teste com Google Meet e rode novamente")
        return

    evento = eventos_com_meet[0]
    titulo = evento.get("summary", "sem título")
    try:
        space_name = resolver_nome_do_space_com_servico(meet_service, evento)
        ok(f"Space resolvido para '{titulo}': {space_name}")
    except Exception as e:
        falha(f"Não foi possível resolver o space de '{titulo}': {e}")
        info("Possível causa: Meet API não habilitada no projeto Google Cloud")
        info("  → console.cloud.google.com → APIs e Serviços → Habilitar Google Meet API")
        return

    # Testa se o endpoint de membros responde (sem criar nada)
    try:
        meet_service.spaces().members().list(parent=space_name).execute()
        ok("Endpoint spaces.members disponível — COHOST deve funcionar")
    except Exception as e:
        code = getattr(getattr(e, "resp", None), "status", "?")
        if str(code) == "403":
            falha("spaces.members retornou 403 — recurso COHOST não disponível nesta edição do Workspace")
            info("Edições que suportam: Google Workspace Business Standard ou superior")
            info("Edições pessoais (Gmail comum) NÃO suportam co-organizadores via API")
        elif str(code) == "404":
            falha("Space não encontrado (404) — verifique se o evento tem Meet ativo")
        else:
            falha(f"Erro inesperado ao listar membros ({code}): {e}")


def verificar_gmail(gmail_service, destino: str):
    print("\n[4] Gmail API")
    try:
        from src.infrastructure.google.gmail_gateway import _montar_mensagem
        payload = _montar_mensagem(
            destino,
            "[Bot Meet] Teste de diagnóstico",
            "Este é um e-mail automático de verificação do Bot Meet V2.\n\nSe você recebeu isso, o Gmail API está funcionando corretamente.",
        )
        gmail_service.users().messages().send(userId="me", body=payload).execute()
        ok(f"E-mail de teste enviado para {destino}")
    except Exception as e:
        falha(f"Erro ao enviar e-mail: {e}")
        info("Verifique se a Gmail API está habilitada no projeto Google Cloud")


def main():
    print("=" * 55)
    print("  Diagnóstico Bot Meet V2")
    print("=" * 55)

    config = load_config()
    calendar, meet, gmail = verificar_auth(config)
    eventos_com_meet = verificar_calendar(calendar, config)
    verificar_meet(meet, eventos_com_meet)
    destino = config.report_email_override or "geozedeque@gmail.com"
    verificar_gmail(gmail, destino)

    print("\n" + "=" * 55)
    print("  Diagnóstico concluído.")
    print("  Corrija os itens com ✗ antes de rodar em produção.")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    main()
