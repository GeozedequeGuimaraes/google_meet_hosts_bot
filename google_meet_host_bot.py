import time
import re
from playwright.sync_api import sync_playwright


def rodar_bot_google():
    with sync_playwright() as p:
        print("Iniciando o navegador...")

        # PERFIL PERSISTENTE para manter login entre execuções
        context = p.chromium.launch_persistent_context(
            user_data_dir="./perfil_google_bot",
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                # --- NOVAS FLAGS PARA IGNORAR MODAIS NATIVOS ---
                "--disable-sync",           # Desativa a tela "Fazer login no Chromium?"
                "--no-first-run",           # Pula as telas de configuração inicial do navegador
                "--disable-features=ProtocolHandlerRegistry" # Ignora o pop-up "Abrir links de agenda na web"
            ],
            permissions=["notifications"],  # Concede permissão de notificações automaticamente no browser
        )

        page = context.pages[0]

        # --- PASSO 1: ACESSAR O GOOGLE AGENDA ---
        print("Acessando o Google Agenda...")
        page.goto("https://calendar.google.com")

        print("\n[AVISO] Se for a primeira execução, faça o login manualmente na janela do navegador.")
        print("O bot irá esperar até que você esteja conectado na sua conta Google.")

        # Novo radar de abas: procura a agenda em todas as abas abertas
        agenda_page = None
        tempo_maximo = 120 # Espera até 2 minutos pelo seu login
        
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
        page = agenda_page
        page.bring_to_front() # Puxa a aba certa para a frente da tela
        page.wait_for_load_state("domcontentloaded")

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

                # Verifica se tem link do Meet de múltiplas formas:
                # 1) Link visível no popup
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

            # --- PASSO 3a: COLETAR CONVIDADOS ---
            convidados = []
            try:
                # No editor do evento, os convidados aparecem como chips/itens na seção "Convidados"
                # Tenta localizar os elementos de convidados pelo atributo data-email ou pelo atributo data-hovercard-id
                chips_convidados = page.locator(
                    "[data-email], [data-hovercard-id]"
                ).all()

                for chip in chips_convidados:
                    print(f"Chips in {chip}")
                    try:
                        email = chip.get_attribute("data-email") or chip.get_attribute(
                            "data-hovercard-id"
                        )
                        if email and "@" in email:
                            # Ignora o organizador/agenda do bot se necessário, mas o principal é obter o NOME
                            nome_cru = chip.inner_text().strip()
                            nome = None
                            
                            if nome_cru:
                                # Pega a primeira linha da string (que costuma ser o Nome do contato no chip do Google Agenda)
                                linhas = [l.strip() for l in nome_cru.split("\n") if l.strip()]
                                if linhas:
                                    nome = linhas[0]
                                    
                                    # Se a primeira linha contiver um e-mail entre parênteses, limpa
                                    if "(" in nome:
                                        nome = nome.split("(")[0].strip()
                                        
                                    # Se a primeira linha for igual ao e-mail, ou se contiver @, usamos o próprio usuário do email
                                    if "@" in nome:
                                        nome = nome.split("@")[0].strip()
                                        
                                    # Limpa possíveis sufixos comuns do calendar
                                    sufixos_remover = [
                                        "organizador", "organizer", "proprietário", "owner", 
                                        "aceitou", "accepted", "recusou", "declined", 
                                        "talvez", "tentative", "aguardando", "awaiting"
                                    ]
                                    for sufixo in sufixos_remover:
                                        if nome.lower().endswith(f" - {sufixo}"):
                                            nome = nome[:-len(f" - {sufixo}")].strip()
                                        if nome.lower().strip() == sufixo:
                                            nome = ""
                            
                            # Fallback: se o nome ficou vazio, extrai do e-mail
                            if not nome:
                                nome = email.split("@")[0]

                            if nome and nome not in convidados:
                                convidados.append(nome)
                    except Exception:
                        continue

                print(f"  Convidados coletados (nomes) ({len(convidados)}):")
                for c in convidados:
                    print(f"    - {c}")

            except Exception as e:
                print(f"  [ERRO] Falha ao coletar convidados: {e}")

            if not convidados:
                print("  [AVISO] Nenhum convidado encontrado. Pulando evento.")
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
            try:

                for nome in convidados:
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
                        time.sleep(1.5)

                        # Ao adicionar o nome no campo "coorganizadores" é gerado um card flutuante.
                        # Para conseguir selecionar e confirmar, simulamos as ações de teclado de um humano.
                        # Seta para baixo foca no card de sugestão, Enter confirma a seleção.
                        page.keyboard.press("ArrowDown")
                        time.sleep(0.5)
                        page.keyboard.press("Enter")

                        time.sleep(1.5)
                        convidados_adicionados += 1
                        print(f"    [OK] Adicionado como coorganizador: {nome}")

                    except Exception as e:
                        print(f"    [FALHA] Não foi possível digitar/adicionar {nome}: {e}")
                        page.keyboard.press("Escape")
                        continue

            except Exception as e:
                print(f"  [ERRO] Falha geral ao adicionar coorganizadores: {e}")

            print(
                f"  Resultado: {convidados_adicionados}/{len(convidados)} coorganizadores adicionados."
            )

            # --- PASSO 3e: SALVAR AS CONFIGURAÇÕES ---
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

            # Salva o evento inteiro
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
    rodar_bot_google()