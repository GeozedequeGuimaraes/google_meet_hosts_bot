# Configurando o Google Cloud Console

1. Acesse o Google Cloud Console e crie um novo projeto (ou reutilize um existente).
2. Em "APIs e servicos" > "Biblioteca", ative tres APIs: Google Calendar API,
   Google Meet API e Gmail API.
3. Em "APIs e servicos" > "Tela de consentimento OAuth", configure o app como
   "Externo" (ou "Interno", se for Google Workspace) e adicione os escopos:
   calendar, meetings.space.created, meetings.space.readonly e gmail.send.
4. Enquanto o app estiver em modo de teste, adicione o e-mail que vai rodar o
   bot na lista de "usuarios de teste".
5. Em "Credenciais", crie um "ID do cliente OAuth" do tipo "Aplicativo para
   computador" e baixe o JSON gerado. Renomeie para credentials.json e
   coloque na raiz do projeto.
6. Instale as dependencias (veja requirements.txt) e rode: python main.py
   Na primeira execucao, uma aba do navegador vai abrir pedindo para voce
   fazer login e autorizar o aplicativo; isso so acontece uma vez, porque o
   token e salvo em token.json.

Observacao importante: o recurso de coorganizadores (spaces.members, papel
COHOST) da Google Meet API e relativamente novo. Verifique na documentacao
oficial atual se ele ja esta disponivel para a edicao do Google Workspace da
sua organizacao antes de depender dele.
