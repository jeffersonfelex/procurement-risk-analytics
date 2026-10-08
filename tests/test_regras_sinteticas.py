"""Ponta a ponta: cada regra precisa encontrar todas as anomalias plantadas na base sintética."""
import pandas as pd
import pytest
from sqlalchemy import text

from risco_compras.config import carregar_parametros
from risco_compras.regras.base import COLUNAS_ALERTA, carregar_regras

REGRAS = carregar_regras(carregar_parametros())


@pytest.fixture(scope="module")
def plantadas(base_sintetica):
    with base_sintetica.connect() as conexao:
        return pd.read_sql(text("SELECT regra, id_objeto FROM anomalias_plantadas"), conexao)


@pytest.mark.parametrize("id_regra", sorted(REGRAS))
def test_regra_encontra_todas_as_anomalias_plantadas(id_regra, base_sintetica, plantadas):
    alertas = REGRAS[id_regra].executar(base_sintetica, "2023-01-01")
    assert list(alertas.columns[:len(COLUNAS_ALERTA)]) == COLUNAS_ALERTA
    assert alertas["pontuacao"].between(0, 1).all()
    esperadas = set(plantadas.loc[plantadas["regra"] == id_regra, "id_objeto"])
    assert esperadas, f"nenhuma anomalia plantada para {id_regra}"
    faltando = esperadas - set(alertas["id_objeto"])
    assert not faltando, f"{id_regra} não encontrou {sorted(faltando)}"


def test_regras_de_alta_precisao_nao_geram_ruido(base_sintetica, plantadas):
    """R2, R5, R6, R7 e R8 só devem apontar o que foi plantado (a base normal não tem esses casos)."""
    for id_regra in ("R2", "R5", "R6", "R7", "R8"):
        alertas = REGRAS[id_regra].executar(base_sintetica, "2023-01-01")
        esperadas = set(plantadas.loc[plantadas["regra"] == id_regra, "id_objeto"])
        assert set(alertas["id_objeto"]) == esperadas, id_regra
