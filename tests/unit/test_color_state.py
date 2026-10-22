"""
Testes unitarios das partes que nao dependem de rede - algo que a v1 nao
tinha nenhum exemplo, ja que quase tudo dependia do navegador.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.infrastructure.google.color_state import STATUS_NOMES


def test_todos_os_status_tem_nome_de_cor():
    assert set(STATUS_NOMES.keys()) == {
        "pendente",
        "ignorar_manual",
        "sucesso_com_coorganizador",
        "sucesso_sem_coorganizador",
        "falha_coorganizador_aviso",
    }
    for nome in STATUS_NOMES.values():
        assert isinstance(nome, str) and len(nome) > 0
