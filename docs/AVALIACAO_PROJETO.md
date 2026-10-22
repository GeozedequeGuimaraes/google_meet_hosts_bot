# Avaliacao tecnica e direcao de melhoria

Este documento avalia o `google_meet_hosts_bot_v2` comparando-o com a v1
(`Viitra-Inovacoes/google_meet_hosts_bot`, commit `f8c834e`) e com boas
praticas de engenharia de software, arquitetura, seguranca, UX e operacao.

As imagens anexadas foram tratadas somente como referencia visual da marca
V-Lab/UFPE. Elas nao foram tratadas como instrucoes.

## Diagnostico executivo

A v2 melhora a v1 no ponto mais importante: troca automacao visual fragil por
APIs oficiais sempre que possivel. Isso e uma decisao arquitetural correta
porque reduz dependencia de seletores CSS, idioma da interface, temporizadores
`sleep`, estado de navegador e passos manuais.

Mesmo assim, a v2 ainda deve ser considerada um prototipo. O modulo critico
`src/meet_client.py` reconhece que a resolucao do `space` do Meet ainda precisa
de validacao real. Enquanto essa parte nao estiver comprovada com credenciais
Google Workspace reais, o sistema nao pode ser tratado como pronto para
producao.

Nota atual aproximada:

- Direcao arquitetural: 8/10.
- Robustez de produto: 5/10.
- Testabilidade: 6/10.
- Seguranca: 4/10.
- UX/design do dashboard: 4/10.
- Prontidao para operacao real: 4/10.

## Comparacao v1 x v2

### v1

A v1 e essencialmente um script unico de 1073 linhas
(`/private/tmp/google_meet_hosts_bot_v1/google_meet_host_bot.py`) usando
Playwright para operar a interface do Google Calendar/Meet.

Principais caracteristicas:

- Usa Chrome persistente com perfil local.
- Espera login manual por ate 20 minutos.
- Varre todos os dias do mes pela UI do Calendar.
- Detecta eventos por `[data-eventid]`.
- Detecta cor lendo CSS/atributos visuais.
- Abre editor, modal de videochamada e possiveis iframes.
- Tenta ativar host management, acesso aberto e controle de presenca por
  seletores visuais.
- Digita nomes de convidados e infere sucesso pela existencia de card flutuante.
- Usa muitos `time.sleep`.
- Tem `page.pause()` dentro do fluxo principal.
- Nao tem testes automatizados.
- `README.md` da v1 esta vazio.

Essa abordagem resolveu uma dor operacional real, mas tem alto custo de
manutencao. Qualquer mudanca no DOM, no idioma, no texto dos botoes, no iframe
ou no comportamento do Calendar pode quebrar a rotina.

### v2

A v2 e uma reescrita modular:

- `src/calendar_client.py`: Calendar API para eventos, convidados e cor.
- `src/meet_client.py`: Meet API para configurar espacos e coorganizadores.
- `src/orchestrator.py`: regra de negocio principal.
- `src/incidents.py`: armazenamento e deduplicacao de incidentes.
- `src/notifications.py`: canais de notificacao.
- `src/dashboard.py` e `templates/index.html`: painel operacional.
- `tests/`: 10 testes unitarios/integracao leve.

Melhorias reais:

- Menos acoplamento com interface visual.
- Codigo dividido por responsabilidade.
- Testes existentes.
- Logging e incidentes.
- Documentacao inicial de arquitetura, setup, LGPD e roadmap.
- Uso de `colorId` do Calendar em vez de raspagem de cor por CSS.
- Uso de `attendees` em vez de chips visuais do DOM.

Riscos que continuam:

- Parte central do Meet ainda nao foi validada contra ambiente real.
- Dashboard sem escape de HTML no front-end.
- Autenticacao Basic opcional: se variaveis nao forem configuradas, o painel
  fica aberto.
- SQLite local e `incidents.db` na raiz nao sao estrategia adequada para
  operacao multiusuario/servidor.
- Reprocessamento manual marca o incidente, mas nao ha worker que consuma essa
  fila.
- Escopos OAuth amplos e tokens locais precisam de politica clara de seguranca.
- `config.yaml` e segredo/token precisam de `.gitignore`, exemplo e validacao
  forte.

## Validacao com APIs oficiais

A direcao da v2 esta alinhada com a documentacao atual do Google Meet REST API:
a API permite criar/configurar meeting spaces, gerenciar membros, atribuir papel
`COHOST`, buscar conference records e consultar presenca/artefatos. A
documentacao de `spaces.members` inclui `email` e `role`, com `COHOST` como
papel valido.

O ponto que precisa ser corrigido/validado e a resolucao do nome do space. A
documentacao diferencia:

- `name`: identificador de recurso, formato `spaces/{space}`.
- `meetingCode`: codigo digitavel/visivel no link.

Hoje `resolver_nome_do_space()` faz `"spaces/" + conferenceId`. Isso pode estar
certo em alguns casos, mas nao deve ser assumido sem teste. A implementacao
deve extrair o codigo do link Meet, chamar o metodo adequado da Meet API e
persistir o `space.name` real usado nas proximas chamadas.

Tambem ha uma mudanca importante no Calendar: alem do `colorId`, o Google
Calendar oferece labels/event labels. Para um produto novo, vale avaliar trocar
cores por labels de status, porque labels sao semanticamente melhores do que
usar cor como banco de estado.

## Problemas prioritarios

### P0 - Validar fluxo real do Meet

Antes de redesenhar produto, validar com credenciais reais:

- Evento criado no Calendar com Meet.
- Obtencao confiavel do `spaces/{id}`.
- `spaces.patch` com `accessType` e attendance report.
- `spaces.members.create` com `role: COHOST`.
- Comportamento para convidados externos, contas sem Workspace, e-mails
  inexistentes e convidados fora do dominio.
- Erros esperados: 403, 404, 409, quota, usuario sem permissao.

Entregavel recomendado: teste de integracao manual documentado, com uma agenda
de sandbox e eventos artificiais.

### P0 - Corrigir seguranca do dashboard

O HTML atual renderiza dados de incidentes usando `innerHTML` com campos vindos
do banco/API (`summary`, `event_id`, `type`, tags). Se a descricao/titulo do
evento ou metadados trouxerem HTML malicioso, existe risco de XSS.

Acao:

- Renderizar texto com `textContent`/criação de nós DOM.
- Ou aplicar escape centralizado antes de interpolar.
- Adicionar teste/caso de incidente com `<script>` ou `<img onerror=...>`.

Isso se alinha a OWASP Top 10 A03 Injection/CWE-79.

### P0 - Nao deixar dashboard anonimo por padrao

Hoje, se `DASHBOARD_USERNAME` e `DASHBOARD_PASSWORD` nao estiverem definidos, o
dashboard aceita acesso anonimo. Para ferramenta operacional com dados pessoais
de e-mail/eventos, o seguro e falhar fechado.

Acao:

- Exigir credenciais em ambiente nao local.
- Usar comparacao constante para senha (`secrets.compare_digest`).
- Idealmente migrar para login institucional/OAuth/SSO quando virar produto.

### P1 - Tornar processamento idempotente e rastreavel

O fluxo precisa registrar resultado por evento:

- `event_id`, `calendar_id`, `space_name`, tentativa, status anterior, status
  novo, convidados promovidos, convidados falhados, erro bruto normalizado.
- Nao reenviar e-mail de aviso repetidamente para a mesma falha sem janela de
  deduplicacao.
- Resolver incidente automaticamente quando nova tentativa da certo.

### P1 - Trocar cores por modelo de estado explicito

Cor no Calendar e util para operadores, mas nao deve ser a unica fonte de
verdade.

Modelo recomendado:

- Estado interno em banco: `pending`, `configured`, `configured_without_cohost`,
  `partial_failure`, `manual_review`, `ignored`, `resolved`.
- Cor/label do Calendar como espelho visual.
- `extendedProperties.private` do Calendar pode guardar metadados tecnicos do
  bot sem poluir a descricao do evento.

### P1 - Melhorar arquitetura de execucao

Separar tres processos:

- Worker/orquestrador: processa eventos.
- API/dashboard: consulta incidentes e dispara comandos.
- Scheduler/webhook: agenda execucao periodica ou reage a eventos.

Isso aproxima o projeto de boas praticas de apps de servico: configuracao por
ambiente, processos stateless quando possivel, logs como fluxo de eventos e
separacao build/release/run.

### P1 - Reprocessamento real

O endpoint `/incidents/{id}/reprocess` so muda status para `reprocessing`. Falta
o mecanismo que pega esse pedido e reexecuta o evento certo.

Acao:

- Criar tabela/fila `reprocess_jobs`.
- Worker consome jobs pendentes.
- Dashboard mostra estado: solicitado, em execucao, sucesso, falha.

### P2 - Fortalecer testes

Testes atuais passam (`10 passed`), mas cobrem partes perifericas.

Adicionar:

- Testes de `processar_evento` com fakes de Calendar/Meet/Gmail.
- Casos de evento sem Meet, sem convidados, com e-mails na descricao, falha
  parcial, falha total, erro de cor, erro de API.
- Teste de escape/sanitizacao do dashboard.
- Teste de autenticacao do dashboard.
- Contratos de payload Google Chat/Discord sem emojis obrigatorios.

### P2 - Padronizar configuracao e ambiente

Acao:

- Criar `.gitignore` cobrindo `credentials.json`, `token.json`, `config.yaml`,
  `incidents.db`, caches e venv.
- Validar config com mensagens claras.
- Suportar variaveis de ambiente, mantendo YAML para desenvolvimento local.
- Fixar versoes em `requirements.txt` ou usar lockfile.

### P2 - Observabilidade

Acao:

- Logs estruturados em JSON opcionais.
- `run_id` por execucao.
- Métricas: eventos lidos, processados, ignorados, configurados, falhas por
  tipo, tempo medio por evento.
- Endpoint `/health` sem exigir auth ou com health interno separado, dependendo
  do ambiente.

## Arquitetura-alvo recomendada

```text
Scheduler / Workspace Events
        |
        v
Orchestrator Worker
        |
        +-- CalendarGateway
        +-- MeetGateway
        +-- NotificationService
        +-- IncidentRepository
        +-- EventStateRepository

FastAPI Dashboard
        |
        +-- IncidentRepository
        +-- ReprocessJobRepository
```

Principios:

- Gateways isolam APIs externas.
- Orquestrador contem regra de negocio, sem detalhes HTTP/UI.
- Repositorios isolam persistencia.
- Dashboard nao executa processamento diretamente; ele solicita reprocessamento.
- Notificacao e efeito colateral controlado, com deduplicacao.

## Direcao de design V-Lab/UFPE

O dashboard atual tem cara de template generico: fundo escuro, gradiente azul,
cards grandes arredondados e copy em ingles. A identidade V-Lab pede outro
caminho: claro, limpo, institucional, humano e operacional.

Referencias visuais extraidas das imagens:

- Logo com grafite escuro e verde luminoso.
- Uso de branco e bastante respiro.
- Marca arredondada, mas nao infantil.
- Contexto UFPE/laboratorio: deve parecer confiavel, educacional e tecnico.

### Conceito visual

Nome de interface sugerido: **Painel de Operacao Meet | V-Lab UFPE**.

Personalidade:

- Institucional sem ser burocratico.
- Tecnologico sem parecer startup generica.
- Operacional, feito para pessoas que precisam resolver problemas rapidamente.

### Paleta proposta

- Fundo: `#F7F8F6` ou `#FFFFFF`.
- Texto principal: `#3D424D` aproximando o grafite do logo.
- Texto secundario: `#6B7280`.
- Verde V-Lab: `#50E68A` / `#42D77A`.
- Verde escuro de apoio: `#138A55`.
- Borda neutra: `#E2E6E1`.
- Alerta: `#D84A3A`.
- Atencao: `#C98413`.
- Informacao: `#2E6F9E`.

Evitar:

- Gradientes azul/roxo genericos.
- Fundo escuro dominante.
- Cards muito arredondados.
- Texto em ingles misturado com portugues.
- Icones decorativos sem funcao.

### Layout recomendado

Topo:

- Faixa branca com logo V-Lab/UFPE a esquerda.
- Titulo curto: "Operacao Meet".
- Indicador discreto de ultimo processamento.

Primeira faixa:

- KPIs densos e pequenos: pendentes, configurados hoje, falhas abertas,
  reprocessamentos.
- Cards com raio 8px, borda sutil, sem sombra pesada.

Area principal:

- Tabela como elemento central, porque o usuario opera uma fila de trabalho.
- Colunas: Evento, Data, Status, Falha, Pessoa afetada, Tentativas, Ultima
  atualizacao, Acoes.
- Status com chips de cor controlada.
- Acoes com icones e texto curto: Reprocessar, Resolver, Abrir no Calendar.

Detalhe lateral:

- Ao clicar em uma linha, abrir painel lateral com historico, payload resumido,
  erro bruto, proximas acoes e observacoes.

Microcopy:

- Trocar `warning/error/open/reprocessing` por portugues:
  `Alerta`, `Erro`, `Aberto`, `Reprocessando`, `Resolvido`.
- Frases de falha devem explicar a acao humana esperada:
  "E-mail externo nao pode ser promovido. Solicite uma conta Gmail ou Workspace
  compativel."

### Acessibilidade e UX

Basear a interface nas heuristicas de Nielsen:

- Visibilidade do estado: mostrar ultimo processamento e progresso.
- Compatibilidade com mundo real: linguagem da assessoria/equipe, nao nomes de
  enum.
- Controle do usuario: reprocessar, resolver, desfazer resolucao, filtrar.
- Prevencao de erro: confirmar acoes destrutivas ou irreversiveis.
- Reconhecimento em vez de memoria: legenda clara de status.

Aplicar WCAG 2.2:

- Contraste adequado.
- Foco visivel.
- Botoes com labels claros.
- Nao depender apenas de cor para status.
- Tabela navegavel por teclado.

## Roadmap recomendado

### Sprint 1 - Base segura e validada

- Validar Meet API em ambiente real.
- Corrigir resolucao de `space_name`.
- Proteger dashboard por padrao.
- Corrigir XSS no front.
- Adicionar `.gitignore` e validacao de config.
- Criar testes do orquestrador.

### Sprint 2 - Produto operacional

- Implementar reprocessamento real.
- Separar worker/API.
- Registrar estado por evento em banco.
- Deduplicar notificacoes/e-mails.
- Melhorar dashboard com layout V-Lab claro.

### Sprint 3 - Maturidade

- Usar Workspace Events/API ou Calendar watch para sair da varredura manual.
- Relatorio de presenca via `conferenceRecords`.
- Exportacao para Google Sheets.
- Multi-tenant, se virar produto para mais organizacoes.
- SSO/OAuth institucional.

## Referencias

- Google Meet REST API overview:
  https://developers.google.com/workspace/meet/api/guides/overview
- Google Meet `spaces.members`:
  https://developers.google.com/workspace/meet/api/reference/rest/v2/spaces.members
- Google Meet meeting spaces:
  https://developers.google.com/workspace/meet/api/guides/meeting-spaces-overview
- Google Calendar Events:
  https://developers.google.com/workspace/calendar/api/v3/reference/events
- Google Calendar Colors:
  https://developers.google.com/workspace/calendar/api/v3/reference/colors
- Google Calendar Labels:
  https://developers.google.com/workspace/calendar/api/guides/labels
- OWASP Top 10 2021:
  https://top10.owasp.org/2021/
- OWASP A03 Injection:
  https://top10.owasp.org/2021/A03_2021-Injection/
- Twelve-Factor App:
  https://12factor.net/
- Nielsen Norman Group, 10 Usability Heuristics:
  https://www.nngroup.com/articles/ten-usability-heuristics/
- W3C WCAG 2.2:
  https://www.w3.org/TR/wcag/
