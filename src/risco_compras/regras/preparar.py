"""Etapas Python das regras que dependem do grafo de vínculos (config: preparar).

Cada função recebe (engine, data_inicio, parametros) e devolve {nome: DataFrame}; a consulta da regra
usa a tabela com {{dados:nome:colunas}}.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from ..config import RAIZ
from ..grafos.vinculos import empresas_ligadas, grupos_vinculados, montar_grafo, normalizar_endereco


def pesos_vinculos(caminho=None) -> dict[str, float]:
    """Peso de cada tipo de vínculo (config/pesos_vinculos.csv); peso 0 desliga o vínculo."""
    tabela = pd.read_csv(caminho or RAIZ / "config" / "pesos_vinculos.csv", sep=";", encoding="utf-8-sig")
    return {str(t): float(p) for t, p in zip(tabela["tipo"], tabela["peso"])}


def arestas_do_cadastro(engine: Engine, pesos: dict[str, float]) -> pd.DataFrame:
    """Arestas empresa–pessoa e empresa–contato a partir do cadastro de fornecedores e sócios."""
    with engine.connect() as conexao:
        socios = pd.read_sql(text("SELECT cnpj, cpf FROM socios"), conexao)
        cadastro = pd.read_sql(text("SELECT cnpj, telefone, email, endereco FROM fornecedores"), conexao)
    partes = [pd.DataFrame({"origem": "pj:" + socios["cnpj"], "destino": "pf:" + socios["cpf"], "tipo": "socio"})]
    for coluna, prefixo in (("telefone", "tel:"), ("email", "email:"), ("endereco", "end:")):
        valores = cadastro[coluna].fillna("").astype(str)
        if coluna == "endereco":
            valores = valores.map(normalizar_endereco)
        validos = valores.str.strip() != ""
        partes.append(pd.DataFrame({"origem": "pj:" + cadastro.loc[validos, "cnpj"],
                                    "destino": prefixo + valores[validos], "tipo": coluna}))
    arestas = pd.concat(partes, ignore_index=True)
    arestas["peso"] = arestas["tipo"].map(pesos).fillna(0.0)
    return arestas[arestas["peso"] > 0]


def concorrentes_vinculados(engine: Engine, data_inicio: str, parametros: dict) -> dict[str, pd.DataFrame]:
    """R3: pares de empresas que participaram de cotações desde data_inicio e estão ligadas no grafo."""
    grafo = montar_grafo(arestas_do_cadastro(engine, pesos_vinculos()))
    consulta = text("SELECT DISTINCT p.cnpj FROM propostas p JOIN cotacoes c ON c.id_cotacao = p.id_cotacao "
                    "WHERE c.data >= :inicio")
    with engine.connect() as conexao:
        participantes = ["pj:" + c for c in pd.read_sql(consulta, conexao, params={"inicio": data_inicio})["cnpj"]]
    pares = grupos_vinculados(grafo, participantes, max_saltos=int(parametros.get("max_saltos", 2)))
    linhas = []
    for par in pares:
        a, b = sorted((par["empresa_a"][3:], par["empresa_b"][3:]))
        linhas.append({"cnpj_a": a, "cnpj_b": b, "tipos": "+".join(dict.fromkeys(par["tipos"])), "peso": par["peso"]})
    colunas = ["cnpj_a", "cnpj_b", "tipos", "peso"]
    return {"pares_vinculados": pd.DataFrame(linhas, columns=colunas).drop_duplicates(["cnpj_a", "cnpj_b"])}


def funcionarios_ligados(engine: Engine, data_inicio: str, parametros: dict) -> dict[str, pd.DataFrame]:
    """R4: funcionários ligados (como sócios, direta ou indiretamente) a empresas do cadastro."""
    grafo = montar_grafo(arestas_do_cadastro(engine, pesos_vinculos()))
    with engine.connect() as conexao:
        funcionarios = pd.read_sql(text("SELECT cpf, nome, departamento FROM funcionarios"), conexao)
    linhas = []
    for f in funcionarios.itertuples(index=False):
        for ligada in empresas_ligadas(grafo, "pf:" + f.cpf, max_saltos=int(parametros.get("max_saltos", 3))):
            linhas.append({"cnpj": ligada["empresa"][3:], "cpf": f.cpf, "nome_funcionario": f.nome,
                           "departamento_funcionario": f.departamento,
                           "vinculo": "+".join(ligada["tipos"]), "peso": ligada["peso"]})
    colunas = ["cnpj", "cpf", "nome_funcionario", "departamento_funcionario", "vinculo", "peso"]
    return {"funcionarios_ligados": pd.DataFrame(linhas, columns=colunas)}
