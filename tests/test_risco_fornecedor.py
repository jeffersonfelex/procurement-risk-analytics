import pandas as pd

from risco_compras.modelos import risco_fornecedor as rf

CORTE = pd.Timestamp("2024-01-01")


def _dados():
    pedidos = pd.DataFrame([
        ("11111111", "TI", "c1", "2023-06-10", 100.0, "compra_direta"),
        ("11111111", "TI", "c1", "2023-12-20", 300.0, "cotacao"),
        ("11111111", "TI", "c1", "2024-02-01", 9999.0, "compra_direta"),   # depois do corte: não pode entrar
        ("22222222", "RH", "c2", "2021-01-01", 50.0, "compra_direta"),     # fora da janela de 24 meses
        ("33333333", "RH", "c2", "2023-03-01", 80.0, "compra_direta"),
    ], columns=["raiz", "departamento", "categoria", "data", "valor", "modalidade"])
    pedidos["data"] = pd.to_datetime(pedidos["data"])
    fornecedores = pd.DataFrame({"raiz": ["11111111", "22222222", "33333333"], "capital_social": [1e5, 1e4, 1e3],
                                 "data_abertura": pd.to_datetime(["2020-01-01", "2010-01-01", "2022-01-01"])})
    return pedidos, fornecedores


def test_variaveis_usam_so_o_passado_dentro_da_janela():
    pedidos, fornecedores = _dados()
    base = rf.variaveis_no_corte(pedidos, fornecedores, CORTE).set_index("raiz")
    assert set(base.index) == {"11111111", "33333333"}              # 2222 não teve pedido nos 24 meses
    a = base.loc["11111111"]
    assert a["vl_24m"] == 400.0 and a["vl_max_pedido"] == 300.0     # o pedido de 2024 não vazou
    assert a["pct_direta"] == 0.25 and a["pct_dezembro"] == 0.75 and a["hhi_departamentos"] == 1.0
    assert a["log_capital"] == 5.0


def test_rotulo_na_janela_e_exclusao_de_quem_ja_estava_bloqueado():
    pedidos, fornecedores = _dados()
    base = rf.variaveis_no_corte(pedidos, fornecedores, CORTE)
    bloqueios = pd.DataFrame({"raiz": ["11111111", "33333333"],
                              "data_inicio": pd.to_datetime(["2024-06-01", "2023-11-01"])})
    rotulada = rf.rotular(base, bloqueios, CORTE).set_index("raiz")
    assert list(rotulada.index) == ["11111111"]                    # 3333 já estava bloqueada no corte
    assert rotulada.loc["11111111", "y"] == 1
    fora_da_janela = bloqueios.assign(data_inicio=pd.to_datetime(["2025-02-01", "2023-11-01"]))
    assert rf.rotular(base, fora_da_janela, CORTE)["y"].sum() == 0


def test_metricas_de_ranking():
    m = rf.metricas(pd.Series([1, 0, 0, 1, 0]), [0.9, 0.8, 0.1, 0.7, 0.2], ks=(2,))
    assert m["positivos"] == 2 and m["precisao@2"] == 0.5 and m["lift@2"] == 1.25 and m["roc_auc"] == 0.8333


def test_modelo_supera_a_linha_de_base_na_base_sintetica(base_sintetica):
    resultado = rf.experimentar(rf.montar_base(rf.carregar(base_sintetica)))
    modelo, base = resultado["modelo"], resultado["linha_de_base_valor"]
    assert modelo["positivos"] > 0
    assert modelo["roc_auc"] > 0.75
    assert modelo["average_precision"] > base["average_precision"]
    assert "pct_direta" in resultado["coeficientes"]
