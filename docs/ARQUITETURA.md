# Arquitetura da v2

## Por que este redesenho existe

A versao 1 deste bot resolvia um problema real (configurar reunioes do Google
Meet em lote) automatizando a interface visual do Google Calendar com
Playwright. Isso funcionava, mas era fragil: dependia de texto exato em
portugues, de classes CSS instaveis, de um Chrome persistente numa maquina
ligada, e nao tinha nenhum teste automatizado.

Esta v2 substitui, sempre que possivel, a automacao de interface por
chamadas diretas as APIs REST oficiais do Google: Calendar API v3 para
ler/escrever eventos, convidados e a cor (campo colorId); e Google Meet
API v2 para gerenciar membros do espaco de reuniao (papel COHOST) e
configuracoes como tipo de acesso e controle de presenca.

## Camadas do projeto

- src/google_auth.py: autenticacao OAuth2 unica, com todos os escopos necessarios.
- src/calendar_client.py: leitura e escrita de eventos, convidados e cor.
- src/meet_client.py: gerenciamento de membros e configuracoes do espaco do Meet.
- src/color_state.py: traducao entre os nomes de status internos e o colorId oficial.
- src/email_service.py: envio de e-mails via Gmail API.
- src/orchestrator.py: a logica de negocio, equivalente a funcao rodar_bot_google
  da v1, mas sem nenhuma dependencia de navegador.
- main.py: ponto de entrada.
- tests/: testes unitarios das partes que nao dependem de chamadas de rede reais.

## O que NAO foi implementado neste prototipo (propositalmente)

Este e um esqueleto de estudo, nao um sistema testado em producao. Os pontos
abaixo precisam de validacao com credenciais reais antes de qualquer uso real,
e estao marcados como TODO no codigo:

- a forma exata de obter o nome de recurso do espaco do Meet a partir de um
  evento do Calendar;
- os nomes exatos dos campos de configuracao do espaco (accessType, controle
  de presenca) na versao da API disponivel para a sua conta;
- a disponibilidade do recurso spaces.members (papel COHOST) na edicao
  especifica do Google Workspace usada, ja que esse recurso e recente e pode
  depender de liberacao por edicao/plano.
