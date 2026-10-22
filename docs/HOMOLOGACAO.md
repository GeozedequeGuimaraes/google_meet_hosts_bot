# Ambiente de Homologação

Como testar o bot sem afetar o ambiente real do AVAMEC Interativo.

---

## Por que a V2 é melhor pra isso do que a V1

A V1 rodava dentro de um Chrome específico, numa máquina Windows, logada numa conta Google real. Qualquer teste era no ambiente de produção.

A V2 usa as APIs REST do Google diretamente. Isso significa:
- Roda em qualquer sistema operacional (Mac, Linux, Windows)
- Roda em servidor sem interface gráfica
- Pode apontar para uma **conta Google separada** para testes — sem tocar no calendar de produção

---

## O que você precisa

### 1. Conta Google de teste
Crie uma conta Google separada (pode ser Gmail pessoal) para homologação.
Essa conta vai ser o "organizador das reuniões" no ambiente de teste.

### 2. Credenciais OAuth2 (credentials.json)
No Google Cloud Console da conta de teste (ou de um projeto separado de dev):

1. Acesse [console.cloud.google.com](https://console.cloud.google.com)
2. Crie um projeto (ex: `bot-meet-homologacao`)
3. Habilite as três APIs:
   - **Google Calendar API**
   - **Google Meet API**
   - **Gmail API**
4. Vá em APIs e Serviços → Credenciais → Criar credencial → **ID do cliente OAuth 2.0**
5. Tipo: **Aplicativo para computador**
6. Baixe o JSON e salve como `credentials.json` na raiz do projeto

### 3. Calendário de teste
Na conta Google de teste, crie um calendário separado (ex: "Bot Meet - Homologação").
Copie o ID do calendário (Configurações do calendário → ID do calendário) e coloque no `config.yaml`.

### 4. Eventos de teste
No calendário de teste, crie 2 ou 3 eventos com:
- **Google Meet** vinculado (marque a opção ao criar)
- Um **convidado com e-mail Gmail** (que virará co-org com sucesso)
- Um **convidado com e-mail não-Gmail** (ex: Hotmail) para testar o caso de falha

Não precisa criar a cor Graphite — o fix do filtro já processa eventos sem cor.

---

## Configurar o bot para homologação

Edite o `config.yaml`:

```yaml
calendar_id: "cole-o-id-do-calendario-de-teste@group.calendar.google.com"
days_ahead: 3
days_behind: 0
report_email_override: "seu-email-pessoal@gmail.com"
credentials_path: credentials.json
token_path: token_homologacao.json   # nome diferente para não conflitar com produção
log_level: DEBUG                      # mostra tudo durante testes
schedule: []                          # roda só quando você chamar manualmente
discord_webhook_url: ""               # opcional: canal de teste no Discord
```

---

## Passo a passo para testar

```bash
# 1. Instalar dependências (só na primeira vez)
make install

# 2. Verificar se as APIs estão OK e autenticar
#    Vai abrir o browser para autorizar o acesso na primeira vez
python scripts/verificar_api.py

# 3. Rodar o bot uma vez contra o calendário de teste
make bot

# 4. Conferir o dashboard de incidentes
make dev
# Abra http://localhost:8765
```

### O que observar

| O que verificar | Como confirmar |
|---|---|
| Meet configurado (acesso aberto + controle de presença) | Abra a reunião no Google Meet e veja as configurações |
| Co-org adicionado (e-mail Gmail) | Na reunião, veja se a pessoa aparece como co-organizadora |
| Falha registrada (e-mail não-Gmail) | Dashboard → incidente com tipo COHOST_ASSIGNMENT_FAILED |
| E-mail enviado ao afetado | A pessoa com Hotmail deve receber o aviso |
| E-mail de relatório | Seu e-mail deve receber o resumo da execução |
| Cor do evento alterada | No Google Calendar de teste, veja se a cor mudou (Banana = sucesso, Tomato = falha) |

---

## Separar produção de homologação

| | Homologação | Produção |
|---|---|---|
| Conta Google | Gmail pessoal / conta separada | Conta oficial V-Lab |
| `credentials.json` | Do projeto de dev no Cloud Console | Do projeto oficial |
| `token.json` | `token_homologacao.json` | `token.json` |
| `calendar_id` | Calendário de teste | Calendário do AVAMEC |
| `schedule` | `[]` (manual) | `["07:00", "17:30"]` |
| `log_level` | `DEBUG` | `INFO` |

Nunca use as credenciais de produção no ambiente de homologação.
