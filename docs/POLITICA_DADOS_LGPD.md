# Nota sobre dados pessoais e LGPD

Este projeto manipula dados pessoais (nomes e e-mails de convidados, e
potencialmente dados de presenca) em contexto educacional. Este documento
nao e um parecer juridico, apenas um ponto de partida para uma politica
real a ser revisada por quem responde legalmente pela instituicao.

Pontos a decidir antes de qualquer uso em producao:

- por quanto tempo o arquivo token.json e os logs (bot.log) devem ser
  retidos, e onde ficam armazenados;
- quem tem acesso as credenciais (credentials.json) e ao e-mail de servico
  usado para autenticacao;
- se os relatorios de presenca gerados (ver ROADMAP.md, item 2) precisam de
  uma base legal especifica de tratamento de dados de estudantes/participantes,
  considerando que muitos podem ser menores de idade;
- um processo de exclusao de dados quando solicitado por um titular.

Recomendacao minima: nunca versionar (git) os arquivos credentials.json,
token.json e bot.log. O .gitignore deste projeto ja os exclui por padrao.
