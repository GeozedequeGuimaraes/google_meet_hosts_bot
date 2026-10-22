"""
Cliente fino sobre a Google Meet REST API (v2).

Este e o modulo que substitui a parte mais fragil da v1: abrir o modal
"Opcoes da videochamada", entrar num iframe, clicar em switches e digitar
nomes num campo esperando um "card flutuante" aparecer. Tudo isso agora e
feito atraves do recurso spaces.members da Meet API.

IMPORTANTE (leia antes de usar com credenciais reais):
O recurso spaces.members (incluindo o papel COHOST) tornou-se disponivel
de forma geral muito recentemente. Antes de usar em producao, confirme na
documentacao oficial atual (developers.google.com/workspace/meet/api)
tres coisas que podem exigir ajuste neste codigo:

  1) se a sua edicao do Google Workspace ja tem esse recurso liberado;
  2) qual e exatamente o campo do evento do Calendar que referencia o
     "space" do Meet (ex: conferenceData.conferenceId, ou um entryPoint
     especifico) na versao da API que voce estiver usando;
  3) os nomes exatos dos campos de configuracao do espaco (accessType,
     campo de controle de presenca), que tambem podem ter mudado.

Este arquivo foi escrito como um prototipo pedagogico, nao como codigo
testado contra a API real.
"""

import logging
import re

logger = logging.getLogger(__name__)

MEET_CODE_RE = re.compile(r"meet\.google\.com/([a-z0-9-]+)", re.IGNORECASE)


def extrair_codigos_meet(evento: dict) -> list[str]:
    conference_data = evento.get("conferenceData", {}) or {}
    codes = []

    conference_id = conference_data.get("conferenceId")
    if conference_id:
        codes.append(conference_id)

    for entry_point in conference_data.get("entryPoints", []):
        uri = entry_point.get("uri") or ""
        match = MEET_CODE_RE.search(uri)
        if match:
            codes.append(match.group(1))

    unique_codes = []
    seen = set()
    for code in codes:
        normalized = str(code).strip()
        if normalized and normalized.lower() not in seen:
            seen.add(normalized.lower())
            unique_codes.append(normalized)
    return unique_codes


def resolver_nome_do_space(evento: dict) -> str:
    """Tenta descobrir o nome do espaco do Meet (ex: "spaces/abc123") a
    partir dos dados de conferencia do evento do Calendar.

    TODO: validar contra a API atual. Em algumas contas, o identificador
    de conferencia do Calendar (conferenceId) pode nao ser diretamente o
    nome de recurso esperado pela Meet API; pode ser necessario resolver
    o "space" chamando spaces.get usando o codigo da reuniao (a parte
    final da URL do tipo meet.google.com/abc-defg-hij) como referencia.
    """
    return resolver_nome_do_space_com_servico(None, evento)


def resolver_nome_do_space_com_servico(meet_service, evento: dict) -> str:
    """Resolve o nome real do space.

    A Meet API identifica o espaco por `spaces/{id}`. O Calendar costuma expor
    o codigo da reuniao (`abc-defg-hij`), que pode ou nao ser aceito como alias
    pelo endpoint. Por isso tentamos candidatos e, quando ha servico disponivel,
    usamos `spaces().get()` para obter o `name` canonico retornado pela API.
    """
    codes = extrair_codigos_meet(evento)
    if not codes:
        raise ValueError("Evento sem codigo de conferencia do Meet.")

    candidates = [code if code.startswith("spaces/") else "spaces/" + code for code in codes]

    if meet_service is None:
        return candidates[0]

    errors = []
    for candidate in candidates:
        try:
            response = meet_service.spaces().get(name=candidate).execute()
            return response.get("name") or candidate
        except Exception as exc:
            errors.append(f"{candidate}: {exc}")

    raise ValueError(
        "Nao foi possivel resolver o space do Meet. Candidatos testados: "
        + "; ".join(errors)
    )


def configurar_space(meet_service, space_name: str):
    """Configura o space do Meet com as três configurações necessárias:
    - Acesso aberto: qualquer um com o link entra sem bater na porta
    - Controle de presença: gera relatório automático de participantes
    - Gravação automática: inicia gravação assim que a reunião começa
    """
    body = {
        "config": {
            "accessType": "OPEN",
            "attendanceReportGenerationType": "GENERATE_REPORT",
            "artifactConfig": {
                "recordingConfig": {
                    "autoRecordingGeneration": "ON"
                }
            }
        }
    }
    return meet_service.spaces().patch(
        name=space_name,
        updateMask=(
            "config.accessType,"
            "config.attendanceReportGenerationType,"
            "config.artifactConfig.recordingConfig.autoRecordingGeneration"
        ),
        body=body,
    ).execute()


def listar_membros(meet_service, space_name: str):
    resposta = meet_service.spaces().members().list(parent=space_name).execute()
    return resposta.get("members", [])


def adicionar_coorganizador(meet_service, space_name: str, email: str):
    """Adiciona um convidado como membro do espaco ja com o papel COHOST.

    Retorna (sucesso, motivo). Em vez de inferir sucesso pela presenca de
    um "card flutuante" na tela (como na v1), aqui o proprio retorno HTTP
    da API diz claramente se funcionou ou nao, o que e muito melhor para
    logs e para decidir quando disparar o e-mail de aviso.
    """
    try:
        meet_service.spaces().members().create(
            parent=space_name,
            body={"email": email, "role": "COHOST"},
        ).execute()
        return True, "ok"
    except Exception as e:
        logger.warning("Falha ao adicionar %s como coorganizador: %s", email, e)
        return False, str(e)


def promover_convidados(meet_service, space_name: str, convidados):
    """Tenta promover uma lista de convidados a coorganizador.

    Retorna (adicionados, falhados), onde falhados e a lista de dicts de
    convidado que nao puderam ser promovidos.
    """
    adicionados = []
    falhados = []
    for convidado in convidados:
        sucesso, motivo = adicionar_coorganizador(meet_service, space_name, convidado["email"])
        if sucesso:
            adicionados.append(convidado)
        else:
            falhados.append({**convidado, "motivo": motivo})
    return adicionados, falhados
