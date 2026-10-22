"""
Estado do fluxo de trabalho representado pela cor do evento.

Na v1, a cor era lida raspando o CSS do card do evento na tela e mapeada
manualmente para nomes através de tabelas RGB/hexadecimal escritas à mão.
Aqui, a cor é apenas o campo "colorId" nativo da Google Calendar API, e a
tradução de ID para nome vem diretamente do endpoint oficial colors().get(),
então não existe mais nenhuma tentativa de adivinhar cor por distância de
pixel.
"""

import logging

logger = logging.getLogger(__name__)

STATUS_NOMES = {
    "pendente": "Graphite",
    "ignorar_manual": "Peacock",
    "sucesso_com_coorganizador": "Banana",
    "sucesso_sem_coorganizador": "Grape",
    "falha_coorganizador_aviso": "Tomato",
}

# Valores de referência da paleta padrão do Calendar. CONFIRME com
# colors().get() antes de usar em produção, pois podem variar.
HEX_CONHECIDOS = {
    "Graphite": "#616161",
    "Peacock": "#4a86e8",
    "Banana": "#f6c026",
    "Grape": "#9a6ade",
    "Tomato": "#d60000",
}


def resolver_color_id_por_nome(calendar_service, nome_desejado: str) -> str | None:
    """Descobre qual colorId corresponde a um nome de status, comparando o
    hexadecimal de referência com o que colors().get() devolve na conta
    atual. Retorna None se a cor não existir na paleta (ex: contas sem Workspace).
    """
    hex_alvo = HEX_CONHECIDOS.get(nome_desejado)
    if not hex_alvo:
        logger.warning("Nome de cor desconhecido: %s", nome_desejado)
        return None

    paleta = calendar_service.colors().get().execute()
    for color_id, dados in paleta.get("event", {}).items():
        if dados.get("background", "").lower() == hex_alvo.lower():
            return color_id

    logger.warning("Cor '%s' (%s) nao encontrada na paleta da conta — colorId ignorado.", nome_desejado, hex_alvo)
    return None
