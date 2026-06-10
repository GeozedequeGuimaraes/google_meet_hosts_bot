import time
import sys
import os
import re
import base64
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


def obter_cor_evento(page):
    """Lê a cor atual do evento no editor do Google Calendar sem precisar abrir menus."""
    try:
        # Localiza o botão principal de cor usando o trecho do aria-label que é padrão
        # O 'i' no final de '*=marcador de cor' garante que ele ignore maiúsculas/minúsculas
        btn_cor = page.locator("div[role='button'][aria-label*='marcador de cor' i]").first
        
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
        # 1. Localiza o botão principal de cor
        btn_cor = page.locator("div[role='button'][aria-label*='marcador de cor' i]").first
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


def rodar_bot_google():
    with sync_playwright() as p:
        print("Iniciando o navegador...")

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

        # Navega para a visualização de 'Dia' via URL (mostra apenas hoje)
        print("Acessando a visualização de 'Dia' (apenas hoje)...")
        page.goto("https://calendar.google.com/calendar/r/day")
        page.wait_for_load_state("domcontentloaded")
        time.sleep(4)

        # Garante que está no dia de hoje clicando no botão "Hoje" / "Today"
        try:
            btn_hoje = page.get_by_role("button", name=re.compile(r"Hoje|Today", re.IGNORECASE)).first
            if btn_hoje.is_visible():
                btn_hoje.click()
                time.sleep(2)
                print("  Garantido: Visualizando o dia de HOJE.")
        except Exception as e:
            print(f"  [AVISO] Não foi possível clicar no botão 'Hoje': {e}")

        # --- PASSO 2: LOCALIZAR EVENTOS COM MEET ---
        # Usa data-eventid como seletor estável do Google Calendar
        eventos = page.locator("[data-eventid]").all()
        event_ids_processados = set()
        eventos_para_processar = []  # Lista de (event_id, titulo)

        print(
            f"Detectados {len(eventos)} elementos de eventos. Filtrando eventos com Meet..."
        )

        for evento in eventos:
            try:
                event_id = evento.get_attribute("data-eventid")
                if not event_id or event_id in event_ids_processados:
                    continue

                event_ids_processados.add(event_id)

                # Tenta pegar o texto do evento para log
                titulo = evento.inner_text().strip().split("\n")[0] or "Sem título"
                print(f"  Verificando evento: {titulo}")

                # Clica no evento para abrir o balão flutuante
                evento.click(force=True)
                time.sleep(2)

                # Link visível do google meet no popup
                tem_meet = False
                try:
                    link_meet = page.locator("span").filter(has_text="Entrar com o Google Meet").first
                    if link_meet.count() > 0:
                        tem_meet = True
                except Exception:
                    pass

                if tem_meet:
                    eventos_para_processar.append((event_id, titulo))
                    print(f"    -> Evento com Meet DETECTADO!")
                else:
                    print(f"    -> Sem Meet, pulando.")

                # Fecha o balão
                page.keyboard.press("Escape")
                time.sleep(0.5)
            except Exception as e:
                print(f"    [ERRO] Exceção ao verificar evento: {e}")
                page.keyboard.press("Escape")
                continue

        print(
            f"\nTotal de eventos com Meet para processar: {len(eventos_para_processar)}"
        )

        # --- PASSO 3: PARA CADA EVENTO, EDITAR E CONFIGURAR COORGANIZADORES ---
        for event_id, titulo in eventos_para_processar:
            print(f"\n{'='*60}")
            print(f"Processando evento: {titulo}")
            print(f"{'='*60}")

            # Clica no evento na agenda para abrir o balão
            evento_elem = page.locator(f"[data-eventid='{event_id}']").first
            try:
                evento_elem.click(force=True)
                time.sleep(1.5)
            except Exception:
                print(f"  [ERRO] Não encontrou o evento '{titulo}' na agenda.")
                continue

            # Clica no botão de Editar (ícone de lápis) para abrir o editor completo
            try:
                btn_editar = page.get_by_role("button", name="Editar evento").first
                btn_editar.click()
                time.sleep(3)
                print("  Editor de evento aberto.")
            except Exception as e:
                print(f"  [ERRO] Não foi possível abrir o editor: {e}")
                page.keyboard.press("Escape")
                continue

            # --- VERIFICAÇÃO DE COR ---
            cor_atual = obter_cor_evento(page)
            pular_evento = False
            if cor_atual:
                print(f"  [COR] Cor atual do evento: {cor_atual}")
                if STATUS_CORES["ignorar_manual"] in cor_atual:
                    print("  [PULAR] Chamada manual (Pavão). O bot não precisa mexer.")
                    pular_evento = True
                elif STATUS_CORES["pendente"] not in cor_atual:
                    print(f"  [PULAR] Evento não é pendente (Grafite). Já foi processado ou é nosso. Pulando...")
                    pular_evento = True
                else:
                    print("  [PROCESSANDO] Chamada pendente (Grafite). Iniciando configuração...")
            else:
                print("  [AVISO] Não foi possível detectar a cor. Prosseguindo por segurança...")

            if pular_evento:
                page.goto("https://calendar.google.com/calendar/r/day")
                page.wait_for_load_state("domcontentloaded")
                time.sleep(3)
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

            if not convidados:
                print("  [AVISO] Nenhum convidado encontrado. Evento SEM organizadores.")
                # Muda a cor para Uva (Roxo) - configurado sem organizadores
                alterar_cor_evento(page, STATUS_CORES["sucesso_sem_coorganizador"])
                # Salva o evento com a nova cor
                try:
                    btn_salvar = page.get_by_role(
                        "button", name=re.compile(r"Salvar|Save", re.IGNORECASE)
                    ).first
                    if btn_salvar.is_visible():
                        btn_salvar.click()
                        time.sleep(2)
                        print("  Evento salvo com cor Roxo (sem organizadores).")
                        try:
                            btn_enviar = page.get_by_role(
                                "button",
                                name=re.compile(r"Enviar|Send|Não enviar|Don't send", re.IGNORECASE),
                            ).first
                            if btn_enviar.is_visible(timeout=3000):
                                btn_enviar.click()
                                time.sleep(1)
                        except Exception:
                            pass
                except Exception as e:
                    print(f"  [ERRO] Falha ao salvar evento sem organizadores: {e}")
                # Volta para a visualização de 'Dia'
                page.goto("https://calendar.google.com/calendar/r/day")
                page.wait_for_load_state("domcontentloaded")
                time.sleep(3)
                continue

            # --- PASSO 3b: ABRIR OPÇÕES DE VIDEOCHAMADA ---
            try:
                btn_opcoes_video = page.get_by_role("button", name="Opções da videochamada").first 
                if btn_opcoes_video.is_visible(timeout=5000):
                    btn_opcoes_video.click()
                    time.sleep(2)
                    print("  Opções de videochamada abertas.")
                else:
                    raise Exception("Nenhum botão de opções de videochamada encontrado.")
            except Exception as e:
                print(f"  [ERRO] Não encontrou 'Opções de videochamada': {e}")
                page.goto("https://calendar.google.com/calendar/r/day")
                page.wait_for_load_state("domcontentloaded")
                time.sleep(3)
                continue

            # --- PASSO 3c: ISOLAR O MODAL E NAVEGAR PARA ABA "CONVIDADOS" E "COORGANIZADORES" ---
            try:
                # Isola o modal de opções de videochamada usando a expressão regular sugerida pelo usuário
                modal = page.get_by_role("dialog", name=re.compile(r"Opções da videochamada|Video conferencing options", re.IGNORECASE)).first
                
                # Aguarda o modal estar visível
                modal.wait_for(state="visible", timeout=10000)
                print("  [OK] Modal de opções de videochamada isolado.")

                # Verifica se há um iframe dentro do modal (comum para extensões de conferência do Meet no Calendar)
                time.sleep(1.5) # Dá um tempo para o iframe carregar
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

            except Exception as e:
                print(f"  [AVISO] Erro ao navegar para abas de convidados/coorganizadores dentro do modal: {e}")
            # --- PASSO 3d: ADICIONAR CONVIDADOS COMO COORGANIZADORES ---
            convidados_adicionados = 0
            convidados_sem_card = []  # Lista de convidados onde o card flutuante não apareceu

            # Inicializa o serviço Gmail uma vez (lazy, só se necessário)
            servico_gmail = None

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
                        # Após digitar o nome, o Google Meet gera um card flutuante de sugestão.
                        # Substituído pela busca direta do atributo aria-label contendo o nome do convidado.
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
            conseguiu_adicionar = (convidados_adicionados > 0) and (not convidados_sem_card)
            precisa_de_organizador = len(convidados) > 0

            if conseguiu_adicionar:
                alterar_cor_evento(page, STATUS_CORES["sucesso_com_coorganizador"])
            elif precisa_de_organizador and not conseguiu_adicionar:
                # Fallback: Virou convidado, mas não coorganizador
                alterar_cor_evento(page, STATUS_CORES["falha_coorganizador_aviso"])
            else:
                alterar_cor_evento(page, STATUS_CORES["sucesso_sem_coorganizador"])

            # --- PASSO 3g: SALVAR O EVENTO INTEIRO ---
            try:
                btn_salvar_evento = page.get_by_role(
                    "button", name=re.compile(r"Salvar|Save", re.IGNORECASE)
                ).first

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
            page.goto("https://calendar.google.com/calendar/r/day")
            page.wait_for_load_state("domcontentloaded")
            time.sleep(3)

        print("\n" + "=" * 60)
        print("[FIM] Todas as reuniões da agenda foram processadas!")
        print("=" * 60)
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
    rodar_bot_google()