import time
import sys
import os
import re
import base64
import datetime
import calendar
from email.mime.text import MIMEText
from playwright.sync_api import sync_playwright

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Escopos necessários para enviar e-mail via Gmail API
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

# Mapeamento dos nomes exatos que o Google usa nos botões
STATUS_CORES = {
    "pendente": "Grafite",              # Bot precisa configurar
    "ignorar_manual": "Pavão",          # Bot ignora (feito pela equipe)
    "sucesso_com_coorganizador": "Banana",
    "sucesso_sem_coorganizador": "Uva",
    "falha_coorganizador_aviso": "Tomate"
}

# Mapeamento de RGB para nomes de cores do Google Agenda
RGB_MAPA_CORES = {
    (124, 124, 124): "Grafite",
    (75, 153, 210): "Pavão",
    (231, 186, 81): "Banana",
    (167, 90, 186): "Uva",
    (218, 82, 52): "Tomate",
}


def obter_nome_cor_por_estilo(style_str):
    if not style_str:
        return None
    # Procura rgb(r, g, b) ou rgb(r,g,b)
    match_rgb = re.search(r'rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', style_str)
    if match_rgb:
        r, g, b = map(int, match_rgb.groups())
        cor_rgb = (r, g, b)
        if cor_rgb in RGB_MAPA_CORES:
            return RGB_MAPA_CORES[cor_rgb]
        # Aproximação de cor por distância euclidiana caso haja pequenas variações
        for rgb_ref, nome in RGB_MAPA_CORES.items():
            if sum((c1 - c2) ** 2 for c1, c2 in zip(cor_rgb, rgb_ref)) < 100:
                return nome
    
    # Procura hexadecimal ex: #616161
    match_hex = re.search(r'#([0-9a-fA-F]{6})', style_str)
    if match_hex:
        hex_val = match_hex.group(1).lower()
        r = int(hex_val[0:2], 16)
        g = int(hex_val[2:4], 16)
        b = int(hex_val[4:6], 16)
        cor_rgb = (r, g, b)
        if cor_rgb in RGB_MAPA_CORES:
            return RGB_MAPA_CORES[cor_rgb]
        for rgb_ref, nome in RGB_MAPA_CORES.items():
            if sum((c1 - c2) ** 2 for c1, c2 in zip(cor_rgb, rgb_ref)) < 100:
                return nome

    return None


def obter_servico_gmail():
    """Autentica via OAuth2 e retorna o serviço Gmail API pronto para uso."""
    if getattr(sys, 'frozen', False):
        pasta_atual = os.path.dirname(sys.executable)
    else:
        pasta_atual = os.path.dirname(os.path.abspath(__file__))

    caminho_credenciais = os.path.join(pasta_atual, "credentials.json")
    caminho_token = os.path.join(pasta_atual, "token_gmail.json")

    creds = None
    if os.path.exists(caminho_token):
        creds = Credentials.from_authorized_user_file(caminho_token, GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(caminho_credenciais):
                print(f"[ERRO] Arquivo credentials.json não encontrado em: {caminho_credenciais}")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(caminho_credenciais, GMAIL_SCOPES)
            creds = flow.run_local_server(port=3009)
        with open(caminho_token, "w") as token_file:
            token_file.write(creds.to_json())

    try:
        service = build("gmail", "v1", credentials=creds)
        return service
    except Exception as e:
        print(f"[ERRO] Falha ao criar serviço Gmail: {e}")
        return None


def enviar_email_coorganizador(service, email_destinatario, nome_destinatario):
    """Envia e-mail de notificação para convidado que não pôde ser adicionado como coorganizador."""
    if not service:
        print(f"    [AVISO] Serviço Gmail não disponível. E-mail para {email_destinatario} não enviado.")
        return False

    assunto = "Configuração de Coorganização e Gravação na Reunião Meet - AVAMEC Interativo"

    corpo = (
        f"Prezada(o) {nome_destinatario},\n\n"
        "Não foi possível adicionar o seu e-mail como co-organizadora da reunião. "
        "Para que você possa acessar a opção de gravação, é necessário que informe um e-mail "
        "de outro domínio, preferencialmente do Gmail, por favor, compartilhe-o para que "
        "possamos prosseguir com as devidas configurações. Também pedimos para que o adicione "
        "nas próximas solicitações\n\n"
        "Atenciosamente,\n\n"
        "Equipe AVAMEC Interativo."
    )

    mensagem = MIMEText(corpo, "plain", "utf-8")
    mensagem["to"] = email_destinatario
    mensagem["subject"] = assunto

    raw = base64.urlsafe_b64encode(mensagem.as_bytes()).decode("utf-8")

    try:
        service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()
        print(f"    [EMAIL] E-mail enviado com sucesso para: {email_destinatario}")
        return True
    except Exception as e:
        print(f"    [ERRO] Falha ao enviar e-mail para {email_destinatario}: {e}")
        return False


def enviar_email_relatorio(service, email_destinatario, eventos_pavao, eventos_tomate):
    """Envia um relatório final com eventos manuais e falhas."""
    if not service:
        print("    [AVISO] Serviço Gmail não disponível. Relatório não enviado.")
        return False

    if not eventos_pavao and not eventos_tomate:
        return True  # Não há nada para relatar

    assunto = "Relatório de Eventos - Bot Meet"

    corpo = "Resumo dos eventos processados:\n\n"
    if eventos_pavao:
        corpo += "Eventos que exigem trabalho manual (Pavão):\n"
        for ev in eventos_pavao:
            corpo += f" - {ev}\n"
        corpo += "\n"

    if eventos_tomate:
        corpo += "Eventos com falha ao adicionar coorganizador (Tomate):\n"
        for ev in eventos_tomate:
            corpo += f" - {ev}\n"
        corpo += "\n"

    corpo += "Atenciosamente,\nBot de Configuração do Google Meet"

    mensagem = MIMEText(corpo, "plain", "utf-8")
    mensagem["to"] = email_destinatario
    mensagem["subject"] = assunto

    raw = base64.urlsafe_b64encode(mensagem.as_bytes()).decode("utf-8")

    try:
        service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()
        print(f"    [EMAIL] Relatório enviado com sucesso para: {email_destinatario}")
        return True
    except Exception as e:
        print(f"    [ERRO] Falha ao enviar relatório para {email_destinatario}: {e}")
        return False


def obter_cor_evento(page):
    """Lê a cor atual do evento no editor do Google Calendar sem precisar abrir menus."""
    try:
        # Localiza o botão principal de cor usando o trecho do aria-label que é padrão
        # Suporta o novo botão e o antigo como fallback
        btn_cor = page.locator("button[aria-label*='cor do evento' i], div[role='button'][aria-label*='marcador de cor' i]").first
        
        # Espera o elemento estar visível na tela (timeout de 3 segundos)
        btn_cor.wait_for(state="visible", timeout=3000)
        
        # Extrai o aria-label completo (Ex: "Adicionar um marcador de cor Grafite")
        label_atual = btn_cor.get_attribute("aria-label")
        
        # Extrai também o código hexadecimal caso precise como fallback (Ex: "#616161")
        hex_atual = btn_cor.get_attribute("data-color")
        
        print(f"  [INFO] Cor atual lida com sucesso: '{label_atual}' ({hex_atual})")
        
        print(f"cor do botão: {btn_cor}")

        # Retorna a string completa para você comparar no seu dicionário STATUS_CORES
        return label_atual

    except Exception as e:
        print(f"  [AVISO] Não foi possível ler a cor do evento: {e}")
        return None


def alterar_cor_evento(page, nome_cor):
    """Altera a cor do evento selecionando a cor especificada pelo nome."""
    try:
        print(f"  [COR] Tentando alterar a cor do evento para: '{nome_cor}'...")
        # 1. Localiza o botão principal de cor usando o novo seletor de aria-label
        btn_cor = page.locator("button[aria-label*='cor do evento' i]").first
        btn_cor.wait_for(state="visible", timeout=3000)
        btn_cor.click()
        time.sleep(1.5)

        print(f"cor do botão para alteração: {btn_cor}")

        # 2. Procura a opção da cor pelo seu nome na lista/menu que se abriu
        # Google Calendar usa botões com aria-label contendo o nome da cor em português (ex: "Banana", "Tomate", etc.)
        seletores = [
            f"[role='menuitemradio'][aria-label*='{nome_cor}' i]",
            f"[role='menuitem'][aria-label*='{nome_cor}' i]",
            f"[aria-label*='{nome_cor}' i]",
        ]

        opcao_cor = None
        for sel in seletores:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=1000):
                    opcao_cor = loc
                    print(f"    [COR] Opção de cor encontrada com o seletor: '{sel}'")
                    break
            except Exception:
                continue

        if not opcao_cor:
            try:
                loc = page.get_by_role("menuitemradio", name=re.compile(nome_cor, re.IGNORECASE)).first
                if loc.is_visible(timeout=1000):
                    opcao_cor = loc
                    print(f"    [COR] Opção de cor encontrada via get_by_role('menuitemradio', name='{nome_cor}')")
            except Exception:
                pass

        if opcao_cor:
            opcao_cor.click()
            time.sleep(1.5)
            print(f"  [COR] Cor do evento alterada para '{nome_cor}' com sucesso.")
            return True
        else:
            print(f"  [ERRO] Não foi possível encontrar a opção da cor '{nome_cor}' no menu.")
            # Fecha o menu apertando Escape para não deixar travado
            page.keyboard.press("Escape")
            time.sleep(0.5)
            return False

    except Exception as e:
        print(f"  [ERRO] Falha ao alterar a cor do evento para '{nome_cor}': {e}")
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        return False


def rodar_bot_google(servico_global=None):
    with sync_playwright() as p:
        print("Iniciando o navegador...")

        eventos_pavao = []
        eventos_tomate = []

        # PERFIL PERSISTENTE para manter login entre execuções
        if getattr(sys, 'frozen', False):
            pasta_atual = os.path.dirname(sys.executable)
        else:
            pasta_atual = os.path.dirname(os.path.abspath(__file__))

        caminho_perfil = os.path.join(pasta_atual, "perfil_real")

        # 1. Abre o perfil portátil
        context = p.chromium.launch_persistent_context(
            user_data_dir=caminho_perfil,
            channel="chrome",
            headless=False,
            ignore_default_args=["--enable-automation"],
            args = [
                "--disable-notifications",        
            ]
        )

        page = context.pages[0]

        # --- PASSO 1: ACESSAR O GOOGLE AGENDA ---
        print("Acessando o Google Agenda...")
        page.goto("https://calendar.google.com")
        page.wait_for_load_state("domcontentloaded")

        # Se já estiver logado, não precisa procurar o botão de login
        if "calendar.google.com/calendar" not in page.url:
            # Se redirecionar para a página de apresentação, clica no botão "Faça login"
            try:
                btn_login = page.get_by_role("link", name="Faça login para usar o Google").nth(1)
                btn_login.wait_for(state="visible", timeout=5000)
                print("Botão de login detectado. Clicando para prosseguir...")
                btn_login.click()
                time.sleep(2)
            except Exception as e:
                print(f"Não foi necessário clicar no botão de login inicial ou ele não foi encontrado: {e}")

        print("\n[AVISO] Se for a primeira execução, faça o login manualmente na janela do navegador.")
        print("O bot irá esperar até que você esteja conectado na sua conta Google.")

        # Novo radar de abas: procura a agenda em todas as abas abertas
        agenda_page = None
        tempo_maximo = 1200 # Espera até 20 minutos pelo seu login
        
        for i in range(tempo_maximo):
            # Passa por todas as abas que o navegador tem abertas no momento
            for p in context.pages:
                if "calendar.google.com/calendar" in p.url:
                    agenda_page = p
                    break
            
            if agenda_page:
                break # Achou a aba! Sai do radar.
                
            time.sleep(1) # Espera 1 segundo e checa as abas de novo

        if not agenda_page:
            print("Erro ou tempo limite esgotado ao aguardar o login.")
            context.close()
            return

        print("Conexão com a conta Google detectada na aba correta!")
        
        # Atualiza o bot para usar a aba onde a agenda realmente abriu
        old_page = page
        page = agenda_page
        page.bring_to_front() # Puxa a aba certa para a frente da tela
        page.wait_for_load_state("domcontentloaded")

        # Se abriu em outra aba, fecha a aba inicial de apresentação
        if old_page != page:
            try:
                old_page.close()
            except Exception:
                pass

        # Obtém ano, mês e quantidade de dias do mês atual
        hoje = datetime.date.today()
        ano = hoje.year
        mes = hoje.month
        num_dias = calendar.monthrange(ano, mes)[1]

        for dia in range(1, num_dias + 1):
            print(f"\n{'='*60}")
            print(f"PROCESSANDO DIA: {dia:02d}/{mes:02d}/{ano}")
            print(f"{'='*60}")

            # Navega para a visualização do dia específico
            url_dia = f"https://calendar.google.com/calendar/r/day/{ano}/{mes}/{dia}"
            page.goto(url_dia)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(4)

            # --- PASSO 2 e 3: PARA CADA EVENTO, VERIFICAR COR E MEET NO CARD ---
            # Usa data-eventid como seletor estável do Google Calendar
            # Deduplica por event_id (o DOM tem dois elementos por evento)
            elementos_eventos_raw = page.locator("[data-eventid]").all()
            ids_vistos = set()
            elementos_eventos = []
            for elem in elementos_eventos_raw:
                try:
                    eid = elem.get_attribute("data-eventid")
                    if not eid or eid in ids_vistos:
                        continue
                    ids_vistos.add(eid)
                    elementos_eventos.append(elem)
                except Exception:
                    continue

            print(f"Detectados {len(elementos_eventos)} eventos únicos para processar.")

            for elem in elementos_eventos:
                try:
                    event_id = elem.get_attribute("data-eventid")
                    if not event_id:
                        continue
                except Exception:
                    continue

                # Extrai título para log
                try:
                    aria = elem.get_attribute("aria-label")
                    if aria:
                        titulo = aria.split(",")[0].strip()
                    else:
                        txt = elem.text_content() or ""
                        linhas = [l.strip() for l in txt.split("\n") if l.strip()]
                        titulo = linhas[0] if linhas else "Evento Sem Título"
                except Exception:
                    titulo = "Evento Sem Título"

                print(f"\n  --- Evento: {titulo} ---")

                # Clica no evento para abrir o card de detalhes
                try:
                    elem.click(force=True)
                    time.sleep(1.5)
                except Exception:
                    print(f"  [ERRO] Não conseguiu clicar no evento '{titulo}'.")
                    continue

                # --- VERIFICAÇÃO NO CARD (COR E GOOGLE MEET) ---
                pular_evento = False
                motivo_pular = ""
                try:
                    # 1. Espera o card de detalhes abrir
                    card_dialog = page.locator("#xDetDlg, div[role='dialog']").first
                    card_dialog.wait_for(state="visible", timeout=5000)

                    # 2. Localiza o elemento de cor no card
                    color_elem = None
                    for selector in [
                        "div.xnWuge",
                        "xpath=//*[@id='xDetDlg']/div/div[3]/div[1]/div[1]",
                        "#xDetDlg div.xnWuge",
                        "div[role='dialog'] div.xnWuge"
                    ]:
                        try:
                            loc = page.locator(selector).first
                            if loc.is_visible(timeout=500):
                                color_elem = loc
                                break
                        except Exception:
                            continue

                    # 3. Detecta a cor
                    cor_detectada = None
                    if color_elem:
                        style_str = color_elem.get_attribute("style") or ""
                        cor_detectada = obter_nome_cor_por_estilo(style_str)
                        print(f"  [CARD] Cor detectada: {cor_detectada} ({style_str})")
                    else:
                        print("  [CARD] Elemento de cor não localizado no card.")

                    # Verifica se a cor é Grafite
                    if cor_detectada != STATUS_CORES["pendente"]:
                        pular_evento = True
                        motivo_pular = f"Cor ({cor_detectada}) não é Grafite"
                        if cor_detectada == STATUS_CORES["ignorar_manual"]:
                            eventos_pavao.append(f"{dia:02d}/{mes:02d}/{ano} - {titulo}")

                    # 4. Verifica a presença do Google Meet
                    if not pular_evento:
                        meet_detectado = False
                        try:
                            if page.locator("a[href*='meet.google.com']").count() > 0:
                                meet_detectado = True
                        except Exception:
                            pass

                        if not meet_detectado:
                            try:
                                content_text = card_dialog.text_content() or ""
                                if "Google Meet" in content_text or "meet.google.com" in content_text:
                                    meet_detectado = True
                            except Exception:
                                pass

                        if not meet_detectado:
                            pular_evento = True
                            motivo_pular = "Não possui Google Meet"

                except Exception as e:
                    print(f"  [AVISO] Erro ao analisar o card: {e}. Pulando evento.")
                    pular_evento = True
                    motivo_pular = "Falha ao abrir/analisar o card"

                # Se decidiu pular, fecha o card e vai para o próximo
                if pular_evento:
                    print(f"  [PULAR] {motivo_pular}. Pulando...")
                    try:
                        page.keyboard.press("Escape")
                        time.sleep(1)
                    except Exception:
                        pass
                    continue

                print("  [PROCESSANDO] Grafite + Google Meet. Abrindo editor...")

                # Clica no botão de Editar (ícone de lápis) para abrir o editor completo
                try:
                    btn_editar = page.get_by_role("button", name=re.compile(r"Editar evento|Edit event|Editar|Edit", re.IGNORECASE)).first
                    btn_editar.click()
                    time.sleep(3)
                    print("  Editor de evento aberto.")
                except Exception as e:
                    print(f"  [ERRO] Não foi possível abrir o editor: {e}")
                    try:
                        page.keyboard.press("Escape")
                    except Exception:
                        pass
                    continue

                # --- PASSO 3a: COLETAR CONVIDADOS (nome + email) ---
                convidados = []  # Lista de dicts: [{"nome": "...", "email": "..."}]
                try:
                    # No editor do evento, os convidados aparecem como chips/itens na seção "Convidados"
                    # Tenta localizar apenas os elementos principais de convidados (evitando botões internos)
                    chips_convidados = page.locator(
                        "div[role='treeitem'][data-email], div[role='treeitem'][data-hovercard-id]"
                    ).all()

                    for chip in chips_convidados:
                        try:
                            # Extrai o email do atributo data-email ou data-hovercard-id
                            email = chip.get_attribute("data-email") or chip.get_attribute("data-hovercard-id") or ""
                            email = email.strip()

                            aria_label = chip.get_attribute("aria-label")
                            nome = ""
                            if aria_label:
                                nome = aria_label.split(",")[0].strip()

                            if not nome and email:
                                nome = email.split("@")[0]

                            if nome and email:
                                # Evita duplicatas pelo email
                                if not any(c["email"] == email for c in convidados):
                                    convidados.append({"nome": nome, "email": email})
                        except Exception:
                            continue
                    # Ignora o primeiro convidado (geralmente o organizador/criador do evento)
                    if len(convidados) > 0:
                        organizador = convidados[0]
                        convidados = convidados[1:]
                        print(f"  [INFO] Ignorando o organizador do evento (primeiro da lista): {organizador['nome']} <{organizador['email']}>")

                    print(f"  Convidados que serão coorganizadores ({len(convidados)}):")
                    for c in convidados:
                        print(f"    - {c['nome']} <{c['email']}>")

                except Exception as e:
                    print(f"  [ERRO] Falha ao coletar convidados: {e}")

                # --- PASSO 3b: ABRIR OPÇÕES DE VIDEOCHAMADA (SEMPRE, com ou sem convidados) ---
                opcoes_video_ok = False
                try:
                    btn_opcoes_video = page.get_by_role("button", name="Opções da videochamada").first 
                    if btn_opcoes_video.is_visible(timeout=5000):
                        btn_opcoes_video.click()
                        time.sleep(2)
                        print("  Opções de videochamada abertas.")
                        opcoes_video_ok = True
                    else:
                        raise Exception("Nenhum botão de opções de videochamada encontrado.")
                except Exception as e:
                    print(f"  [ERRO] Não encontrou 'Opções de videochamada': {e}")

                # --- PASSO 3c: CONFIGURAR MODAL DE VIDEOCHAMADA (SEMPRE) ---
                target_container = None
                if opcoes_video_ok:
                    try:
                        # Isola o modal de opções de videochamada
                        modal = page.get_by_role("dialog", name=re.compile(r"Opções da videochamada|Video conferencing options", re.IGNORECASE)).first
                        
                        # Aguarda o modal estar visível
                        modal.wait_for(state="visible", timeout=10000)
                        print("  [OK] Modal de opções de videochamada isolado.")

                        # Verifica se há um iframe dentro do modal
                        time.sleep(1.5)
                        has_iframe = False
                        try:
                            if modal.locator("iframe").count() > 0:
                                has_iframe = True
                        except Exception:
                            pass

                        if has_iframe:
                            print("  [INFO] Usando frame_locator para acessar conteúdo dentro do iframe do modal.")
                            target_container = modal.frame_locator("iframe").first
                        else:
                            print("  [INFO] Usando o modal diretamente no DOM principal.")
                            target_container = modal

                        # --- ASSEGURAR CONFIGURAÇÕES DAS OPÇÕES DE VIDEOCHAMADA ---
                        print("  Assegurando opções de videochamada...")

                        # 1. Gerenciamento de organizadores
                        try:
                            switch_gerenciamento = None
                            for name_pattern in [r"Gerenciamento de organizadores", r"Host management"]:
                                try:
                                    loc = target_container.get_by_role("switch", name=re.compile(name_pattern, re.IGNORECASE)).first
                                    if loc.is_visible(timeout=1500):
                                        switch_gerenciamento = loc
                                        break
                                except Exception:
                                    continue

                            if not switch_gerenciamento:
                                for selector in [
                                    "button[aria-label*='organizadores']",
                                    "button[aria-label*='Host management']",
                                    "button[aria-label*='host management']",
                                    "div.Hu42Nb button",
                                    "div.Hu42Nb [role='switch']",
                                    ".AZRO6b button",
                                    ".Hu42Nb button",
                                    "xpath=.//button[contains(@aria-label, 'organizadores') or contains(@aria-label, 'Host') or contains(@aria-label, 'host')]"
                                ]:
                                    try:
                                        loc = target_container.locator(selector).first
                                        if loc.is_visible(timeout=1000):
                                            switch_gerenciamento = loc
                                            break
                                    except Exception:
                                        continue

                            if switch_gerenciamento:
                                switch_gerenciamento.wait_for(state="visible", timeout=5000)
                                aria_checked = switch_gerenciamento.get_attribute("aria-checked")
                                if aria_checked != "true":
                                    print("    Ativando 'Gerenciamento de organizadores'...")
                                    switch_gerenciamento.click()
                                    time.sleep(1.5)
                                else:
                                    print("    'Gerenciamento de organizadores' já está ativado.")
                            else:
                                print("    [AVISO] Botão de 'Gerenciamento de organizadores' não localizado.")
                        except Exception as e:
                            print(f"    [ERRO] Falha ao configurar 'Gerenciamento de organizadores': {e}")

                        # 2. Tipo de acesso "Abrir" / "Open"
                        try:
                            radio_abrir = None
                            for name_pattern in [r"^Abrir$", r"^Open$"]:
                                try:
                                    loc = target_container.get_by_role("radio", name=re.compile(name_pattern, re.IGNORECASE)).first
                                    if loc.is_visible(timeout=1500):
                                        radio_abrir = loc
                                        break
                                except Exception:
                                    continue

                            if not radio_abrir:
                                for label_text in ["Abrir", "Open"]:
                                    try:
                                        loc = target_container.get_by_label(re.compile(f"^{label_text}$", re.IGNORECASE)).first
                                        if loc.is_visible(timeout=1500):
                                            radio_abrir = loc
                                            break
                                    except Exception:
                                        continue

                            if not radio_abrir:
                                for selector in [
                                    "input[name='accessType'][value='1']",
                                    "input[value='1']",
                                    "xpath=.//input[@value='1']",
                                    "xpath=.//input[@name='accessType' and @value='1']",
                                    "xpath=.//label[text()='Abrir']/preceding-sibling::input",
                                    "xpath=.//label[contains(text(),'Abrir') or contains(text(),'Open')]",
                                    "xpath=.//*[@id='yDmH0d']/c-wiz/div/div/div/div/div[1]/div/div[2]/div/div[1]/div/div[7]/div[3]//input",
                                    "xpath=.//div[contains(@class, 'YRLNPd')]//input",
                                    "label:has-text('Abrir')",
                                    "label:has-text('Open')"
                                ]:
                                    try:
                                        loc = target_container.locator(selector).first
                                        if loc.is_visible(timeout=1000):
                                            radio_abrir = loc
                                            break
                                    except Exception:
                                        continue

                            if radio_abrir:
                                radio_abrir.wait_for(state="visible", timeout=5000)
                                is_checked = False
                                try:
                                    is_checked = radio_abrir.is_checked()
                                except Exception:
                                    pass

                                if not is_checked:
                                    print("    Selecionando acesso 'Abrir'...")
                                    radio_abrir.click()
                                    time.sleep(1.5)
                                else:
                                    print("    Acesso 'Abrir' já selecionado.")
                            else:
                                print("    [AVISO] Opção 'Abrir'/'Open' não localizada.")
                        except Exception as e:
                            print(f"    [ERRO] Falha ao configurar acesso 'Abrir': {e}")

                        # --- PASSO 3d: SE HÁ CONVIDADOS, ADICIONAR COMO COORGANIZADORES ---
                        if convidados:
                            # Dentro do container do modal, primeiro tenta localizar e clicar na aba "Convidados" / "Guests"
                            aba_convidados = None
                            

                            if not aba_convidados:
                                try:
                                    loc = target_container.get_by_role("tab", name="Convidados").first
                                    loc.wait_for(state="visible", timeout=3000)
                                    aba_convidados = loc
                                except Exception as e:
                                    print(f"  [DEBUG] falhou: {e}")


                            if aba_convidados:
                                aba_convidados.click()
                                print("  Aba 'Convidados' selecionada com sucesso no modal.")
                                time.sleep(1.5)
                            else:
                                print("  [AVISO] Não foi possível selecionar a aba 'Convidados' automaticamente.")

                            # Agora tenta localizar e clicar na aba "Coorganizadores" / "Co-hosts"
                            
                            aba_coorganizadores = None
                            
                            try:
                                loc = target_container.get_by_role("region", name="Adicionar coorganizador").locator("label").first
                                loc.wait_for(state="visible", timeout=4000)
                                aba_coorganizadores = loc
                            except Exception as e:
                                print(f"  [DEBUG] falhou: {e}")

                            aba_coorganizadores.click()
                            time.sleep(1.5)
                            print("  Aba 'Coorganizadores' selecionada no modal.")
                        else:
                            print("  [INFO] Sem convidados. Pulando adição de coorganizadores.")

                    except Exception as e:
                        print(f"  [AVISO] Erro ao navegar para abas de convidados/coorganizadores dentro do modal: {e}")

                # --- PASSO 3d: ADICIONAR CONVIDADOS COMO COORGANIZADORES ---
                convidados_adicionados = 0
                convidados_sem_card = []  # Lista de convidados onde o card flutuante não apareceu

                # Inicializa o serviço Gmail uma vez (lazy, só se necessário)
                servico_gmail = servico_global

                if convidados and target_container:
                    try:
                        for convidado in convidados:
                            nome = convidado["nome"]
                            email = convidado["email"]
                            try:
                                # O próprio aba_coorganizadores (localizado no passo anterior) é o campo de entrada para digitar
                                campo_adicionar = None

                                # Tenta usar a variável aba_coorganizadores do escopo da função
                                if 'aba_coorganizadores' in locals() and aba_coorganizadores is not None:
                                    campo_adicionar = aba_coorganizadores

                                campo_adicionar.click()
                                time.sleep(0.5)

                                # Digita o nome do convidado
                                campo_adicionar.fill(nome)
                                time.sleep(2)

                                # --- VERIFICAÇÃO DO CARD FLUTUANTE ---
                                card_encontrado = False
                                try:
                                    # Escapa caracteres especiais para evitar quebra no seletor CSS
                                    nome_escapado = nome.replace('\\', '\\\\').replace('"', '\\"')
                                    card_option = target_container.locator(f'[aria-label*="{nome_escapado}" i]').first
                                    if card_option.is_visible(timeout=3000):
                                        card_encontrado = True
                                        print(f"    [CARD] Card flutuante encontrado via aria-label (nome completo) para: {nome}")
                                except Exception:
                                    pass

                                # Fallback usando o primeiro nome se a busca por nome completo não encontrar
                                if not card_encontrado:
                                    try:
                                        primeiro_nome = nome.split()[0]
                                        primeiro_nome_escapado = primeiro_nome.replace('\\', '\\\\').replace('"', '\\"')
                                        card_option = target_container.locator(f'[aria-label*="{primeiro_nome_escapado}" i]').first
                                        if card_option.is_visible(timeout=2000):
                                            card_encontrado = True
                                            print(f"    [CARD] Card flutuante encontrado via aria-label (primeiro nome) para: {nome}")
                                    except Exception:
                                        pass

                                if card_encontrado:
                                    # Card flutuante encontrado! Clica diretamente nele (está dentro do iframe).
                                    try:
                                        card_option.click()
                                    except Exception:
                                        # Fallback: tenta via teclado
                                        page.keyboard.press("ArrowDown")
                                        time.sleep(0.5)
                                        page.keyboard.press("Enter")
                                    time.sleep(1.5)
                                    convidados_adicionados += 1
                                    print(f"    [OK] Adicionado como coorganizador: {nome} <{email}>")
                                else:
                                    # Card NÃO apareceu - o usuário não foi encontrado
                                    print(f"    [CARD NÃO ENCONTRADO] Nenhum card flutuante gerado para: {nome} <{email}>")
                                    convidados_sem_card.append(convidado)

                                    # Limpa o campo para o próximo convidado
                                    campo_adicionar.fill("")
                                    time.sleep(0.5)

                            except Exception as e:
                                print(f"    [FALHA] Não foi possível digitar/adicionar {nome}: {e}")
                                page.keyboard.press("Escape")
                                continue

                    except Exception as e:
                        print(f"  [ERRO] Falha geral ao adicionar coorganizadores: {e}")

                    print(
                        f"  Resultado: {convidados_adicionados}/{len(convidados)} coorganizadores adicionados."
                    )

                    # --- PASSO 3d.1: ENVIAR E-MAILS PARA CONVIDADOS SEM CARD ---
                    if convidados_sem_card:
                        print(f"\n  Enviando e-mails para {len(convidados_sem_card)} convidado(s) não encontrado(s)...")
                        if servico_gmail is None:
                            servico_gmail = obter_servico_gmail()

                        for convidado in convidados_sem_card:
                            enviar_email_coorganizador(
                                servico_gmail,
                                convidado["email"],
                                convidado["nome"]
                            )

                # --- PASSO 3e: SALVAR AS CONFIGURAÇÕES DO MODAL ---
                if opcoes_video_ok:
                    try:
                        # Reobtém referência ao modal e ao container
                        modal = page.get_by_role("dialog", name=re.compile(r"Opções da videochamada|Video conferencing options", re.IGNORECASE)).first
                        
                        has_iframe = False
                        try:
                            if modal.locator("iframe").count() > 0:
                                has_iframe = True
                        except Exception:
                            pass

                        if has_iframe:
                            target_container = modal.frame_locator("iframe").first
                        else:
                            target_container = modal

                        btn_salvar_opcoes = target_container.get_by_role(
                            "button", name=re.compile(r"Salvar|Save", re.IGNORECASE)
                        ).first

                        if btn_salvar_opcoes.is_visible():
                            btn_salvar_opcoes.click()
                            time.sleep(2)
                            print("  Configurações de videochamada salvas no modal.")

                    except Exception as e:
                        print(f"  [AVISO] Erro ao salvar opções de videochamada no modal: {e}")

                # --- PASSO 3f: ALTERAR COR DO EVENTO COM BASE NO RESULTADO ---
                if not convidados:
                    # Sem convidados → Uva (configurado sem coorganizadores)
                    alterar_cor_evento(page, STATUS_CORES["sucesso_sem_coorganizador"])
                elif convidados_adicionados > 0 and not convidados_sem_card:
                    # Todos os convidados adicionados com sucesso → Banana
                    alterar_cor_evento(page, STATUS_CORES["sucesso_com_coorganizador"])
                else:
                    # Falha ao adicionar algum convidado → Tomate
                    alterar_cor_evento(page, STATUS_CORES["falha_coorganizador_aviso"])
                    eventos_tomate.append(f"{dia:02d}/{mes:02d}/{ano} - {titulo}")

                # --- PASSO 3g: SALVAR O EVENTO INTEIRO ---
                try:
                    btn_salvar_evento = page.get_by_role(
                        "button", name=re.compile(r"Salvar|Save", re.IGNORECASE)
                    ).first
                    print("Salvando evento")

                    if btn_salvar_evento.is_visible():
                        btn_salvar_evento.click()
                        time.sleep(2)
                        print("  Evento salvo com sucesso!")

                        # Se aparecer diálogo "Enviar e-mail de atualização?", clica em "Enviar" ou "Não enviar"
                        try:
                            btn_enviar = page.get_by_role(
                                "button",
                                name=re.compile(
                                    r"Enviar|Send|Não enviar|Don't send", re.IGNORECASE
                                ),
                            ).first
                            if btn_enviar.is_visible(timeout=3000):
                                btn_enviar.click()
                                time.sleep(1)
                        except Exception:
                            pass

                except Exception as e:
                    print(f"  [ERRO] Falha ao salvar o evento: {e}")

                # Volta para a visualização de 'Dia' para processar o próximo evento
                # page.goto(url_dia)
                # page.wait_for_load_state("domcontentloaded")
                # time.sleep(3)

        print("\n" + "=" * 60)
        print("[FIM] Todas as reuniões da agenda foram processadas!")
        print("=" * 60)
        
        # Envia email de relatório no final
        if servico_global and (eventos_pavao or eventos_tomate):
            try:
                perfil = servico_global.users().getProfile(userId='me').execute()
                email_logado = perfil.get('emailAddress')
                if email_logado:
                    print(f"\nEnviando relatório para {email_logado}...")
                    enviar_email_relatorio(servico_global, email_logado, eventos_pavao, eventos_tomate)
                else:
                    print("\n[ERRO] Não foi possível obter o email do perfil logado.")
            except Exception as e:
                print(f"\n[ERRO] Falha ao obter perfil ou enviar relatório: {e}")
        
        input("Pressione Enter no terminal para encerrar o navegador...")
        context.close()


if __name__ == "__main__":
    print("=" * 60)
    print("FASE 1: Autenticação da API do Gmail")
    print("=" * 60)
    print("Verificando conexão com o Gmail...")
    # Tenta autenticar o Gmail logo no início para evitar travamentos durante o bot
    servico = obter_servico_gmail()
    if servico:
        print("[OK] Gmail autenticado com sucesso!")
    else:
        print("[AVISO] Não foi possível autenticar o Gmail. O envio de e-mails falhará.")
    print("=" * 60)
    print("\nFASE 2: Inicialização do Navegador e Playwright")
    print("=" * 60)
    rodar_bot_google(servico)