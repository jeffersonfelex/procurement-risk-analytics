import pandas as pd
import pytest

from risco_compras.regras.base import (
    COLUNAS_ALERTA,
    Regra,
    incluir_dados,
    incluir_tabelas_csv,
    padronizar_alertas,
    sem_comentarios,
    tabela_em_sql,
)


def test_tabela_em_sql_com_linhas_e_vazia():
    sql = tabela_em_sql([("a'b", 1, 2.5, None)], ["texto", "inteiro", "real", "nulo"])
    assert "column1 AS texto" in sql and "('a''b', 1, 2.5, NULL)" in sql
    vazia = tabela_em_sql([], ["x", "y"])
    assert vazia == "SELECT NULL AS x, NULL AS y WHERE 1 = 0"


def test_dois_pontos_em_texto_nao_vira_parametro():
    assert ":" not in tabela_em_sql([("hora 10:30",)], ["t"]).split("VALUES")[1]


def test_incluir_tabelas_csv_ignora_linhas_incompletas(tmp_path):
    (tmp_path / "lista.csv").write_text("codigo;nome\n1;Um\n;Sem código\n2;Dois\n", encoding="utf-8")
    sql = incluir_tabelas_csv("SELECT * FROM ({{csv:lista:codigo,nome}}) t", pasta=tmp_path)
    assert "(1, 'Um')" in sql and "(2, 'Dois')" in sql and "Sem código" not in sql


def test_incluir_dados_exige_a_tabela_preparada():
    df = pd.DataFrame({"a": ["x"], "b": [1]})
    assert "('x', 1)" in incluir_dados("SELECT * FROM ({{dados:t:a,b}}) d", {"t": df})
    with pytest.raises(KeyError, match="não gerou"):
        incluir_dados("SELECT * FROM ({{dados:outra:a}}) d", {"t": df})


def test_parametros_vem_da_consulta_sem_comentarios(tmp_path, monkeypatch):
    arquivo = tmp_path / "r.sql"
    arquivo.write_text("-- comentário com :ignorado\nSELECT * FROM t WHERE d >= :data_inicio AND v > :limite",
                       encoding="utf-8")
    monkeypatch.setattr(Regra, "caminho_sql", property(lambda self: arquivo))
    regra = Regra(id="RX", nome="x", sql="r.sql", parametros={"limite": 10})
    assert regra.parametros_da_consulta("2024-01-01") == {"data_inicio": "2024-01-01", "limite": 10}
    regra.parametros = {}
    with pytest.raises(KeyError, match="limite"):
        regra.parametros_da_consulta("2024-01-01")
    assert ":ignorado" not in sem_comentarios(arquivo.read_text(encoding="utf-8"))


def test_padronizar_alertas_normaliza_e_confere_colunas():
    regra = Regra(id="R9", nome="teste", sql="x.sql", versao="2.0")
    bruto = pd.DataFrame([{"TIPO_OBJETO": "pedido", "ID_OBJETO": 10, "DEPARTAMENTO": "TI",
                           "CNPJ_FORNECEDOR": "11.222.333/0001-81", "VALOR_ENVOLVIDO": "1500.456",
                           "PONTUACAO": 3, "EVIDENCIA": "[x] teste"}])
    saida = padronizar_alertas(bruto, regra)
    assert list(saida.columns[:len(COLUNAS_ALERTA)]) == COLUNAS_ALERTA
    linha = saida.iloc[0]
    assert (linha.id_regra, linha.id_objeto, linha.cnpj_fornecedor) == ("R9", "10", "11222333000181")
    assert linha.pontuacao == 1.0 and linha.valor_envolvido == 1500.46 and linha.versao_regra == "2.0"
    with pytest.raises(ValueError, match="evidencia"):
        padronizar_alertas(bruto.drop(columns=["EVIDENCIA"]), regra)
