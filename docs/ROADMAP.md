# Roadmap de ampliacao do produto

Este documento reune, como desenho de solucao (nao como codigo pronto), as
propostas de ampliacao discutidas na analise critica do projeto original.

## 1. Painel web de status

Hoje o "estado" de cada evento so existe como uma cor dentro do proprio
Google Agenda, visivel apenas para quem sabe o que cada cor significa. A
proposta e um painel web simples (por exemplo, um pequeno backend
Flask/FastAPI consultando a mesma Calendar API) que mostre, para toda a
equipe pedagogica, a lista de eventos do mes com seu status, motivo de falha
quando houver, e um botao para forcar o reprocessamento manual de um evento
especifico.

## 2. Relatorio de presenca de ponta a ponta

O bot ja ativa o controle de presenca na reuniao, mas hoje ninguem consome
esse dado depois. A proposta e, apos o fim de cada conferencia, buscar o
relatorio de presenca atraves do recurso conferenceRecords da Meet API e
gravar automaticamente os dados numa planilha do Google Sheets (via Sheets
API), organizada por turma/curso, fechando o ciclo entre "configurar a
reuniao" e "ter o dado de frequencia utilizavel".

## 3. Notificacoes em tempo real

Em vez de so um e-mail de relatorio no final do processamento, integrar com
a Google Chat API para enviar um aviso imediato a um espaco de chat da
equipe sempre que um evento cair no estado de falha, permitindo reacao
humana muito mais rapida do que esperar o relatorio consolidado.

## 4. Suporte a multiplas organizacoes (multi-tenant)

A v1 e este prototipo assumem uma unica conta/organizacao fixa. Para virar
um produto reutilizavel por outras assessorias pedagogicas ou instituicoes,
seria necessario desacoplar as credenciais e a configuracao por "tenant"
(uma tabela de organizacoes, cada uma com seu proprio token OAuth2 e
calendario), rodando o mesmo motor de orquestracao para todas.

## 5. Google Workspace Add-on de Calendar

A forma mais nativa de entregar essa funcionalidade seria como um Add-on de
Calendar construido em Google Apps Script, que aparece como uma barra
lateral no momento em que o evento e criado, permitindo configurar tudo
instantaneamente (sem esperar nenhum processamento em lote) e hospedado
inteiramente na infraestrutura do Google, sem precisar de nenhum servidor ou
maquina propria rodando continuamente.

## 6. Gatilho orientado a eventos em vez de varredura periodica

Trocar o modelo de "reprocessar tudo todo santo dia" por uma reacao em tempo
real, usando o gatilho onEventUpdated do Google Apps Script ou uma
assinatura da Google Workspace Events API via Pub/Sub, processando cada
evento no exato momento em que ele e criado ou alterado.
