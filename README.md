# Google Meet Hosts Bot v2 (Protótipo de estudo)

Este projeto é uma reescrita experimental do google_meet_hosts_bot original, criada
para demonstrar, na prática, as melhorias propostas na análise crítica daquele
projeto: substituir a automação de interface (Playwright) por chamadas diretas às
APIs REST oficiais do Google sempre que possível, organizar o código em módulos
testáveis, adicionar logging estruturado e testes, e documentar propostas de
ampliação do produto.

IMPORTANTE: este é um protótipo pedagógico para você revisar antes de levar
qualquer coisa para o repositório da empresa. Ele não foi executado contra
credenciais reais do Google. Trechos que dependem de detalhes exatos da Google
Meet API (ainda recente) estão marcados como TODO no código e devem ser
validados com a documentação oficial atualizada antes de qualquer uso real.

## Principais diferenças em relação à v1

- Sem navegador: nenhuma dependência de Playwright ou Chrome.
- A cor do evento é o campo nativo colorId da Calendar API, e não mais um valor
  de CSS raspado da tela.
- Convidados vêm do campo attendees da Calendar API, não de elementos do DOM.
- Coorganizadores são adicionados via Google Meet API (recurso spaces.members,
  papel COHOST), não clicando em campos de texto e esperando um card aparecer.
- Código modular (src/), com testes unitários (tests/), logging estruturado e camada inicial de incidentes.
- Documentação de arquitetura, setup e propostas de ampliação em docs/.
- Monitoramento operacional em camadas: incidentes, deduplicação e canais de notificação.

## Estrutura de pastas

- main.py: ponto de entrada do programa.
- src/config.py: leitura de configuração (config.yaml).
- src/logging_setup.py: configuração de logs.
- src/google_auth.py: autenticação OAuth2 única para Calendar, Meet e Gmail.
- src/calendar_client.py: leitura e escrita de eventos, convidados e cor.
- src/meet_client.py: gerenciamento de coorganizadores e configurações do Meet.
- src/color_state.py: tradução entre nomes de status e colorId.
- src/email_service.py: envio de e-mails via Gmail API.
- src/orchestrator.py: lógica de negócio principal e integração com incidentes.
- src/incidents.py: armazenamento e deduplicação de incidentes por evento.
- src/notifications.py: adaptadores de notificação para e-mail e webhooks.
- tests/: testes unitários das partes que não dependem de rede.
- docs/ARQUITETURA.md: explicação detalhada das decisões de design.
- docs/SETUP_GOOGLE_CLOUD.md: passo a passo de configuração no Google Cloud Console.
- docs/ROADMAP.md: propostas de ampliação do produto (painel web, relatório de
  presença, notificações, multi-tenant, Workspace Add-on, gatilhos em tempo real).
- docs/POLITICA_DADOS_LGPD.md: pontos de atenção sobre dados pessoais.

## Como rodar (depois de configurar o Google Cloud, veja docs/SETUP_GOOGLE_CLOUD.md)

1. Crie um ambiente virtual e instale as dependências do requirements.txt.
2. Copie config.example.yaml para config.yaml e ajuste os valores.
3. Coloque o arquivo credentials.json (gerado no Google Cloud Console) na raiz.
4. Rode: python main.py
5. Na primeira execução, uma aba do navegador abrirá para você autorizar o
   aplicativo. Isso só acontece uma vez; depois o token fica salvo em token.json.
