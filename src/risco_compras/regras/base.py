"""Definição de regra, marcadores {{csv:...}} e {{dados:...}} e formato padrão dos alertas."""

from __future__ import annotations

import importlib
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from ..config import RAIZ
from ..utils.documentos import normalizar_cnpj

COLUNAS_ALERTA = [
    "id_regra",
    "tipo_objeto",
    "id_objeto",
    "departamento",
    "cnpj_fornecedor",
    "valor_envolvido",
    "pontuacao",
    "evidencia",
]

_PARAMETRO_SQL = re.compile(r"(?<!:):([A-Za-z_]\w*)")
_TABELA_CSV = re.compile(r"\{\{csv:([\w-]+):([\w,]+)\}\}")
_DADOS = re.compile(r"\{\{dados:(\w+):([\w,]+)\}\}")
_MARCADOR = re.compile(r"\{\{.*?\}\}", re.S)
_COMENTARIO = re.compile(r"--[^\n]*")


def sem_comentarios(sql: str) -> str:
    """Remove comentários de linha (--): um ':nome' num comentário não pode virar parâmetro."""
    return _COMENTARIO.sub("", sql)


def _valor_sql(valor) -> str:
    if valor is None or valor is pd.NA or (isinstance(valor, float) and math.isnan(valor)):
        return "NULL"
    if isinstance(valor, bool):
        return "1" if valor else "0"
    if isinstance(valor, int) or (hasattr(valor, "dtype") and getattr(valor.dtype, "kind", "") in "iu"):
        return str(int(valor))
    if isinstance(valor, float) or (hasattr(valor, "dtype") and getattr(valor.dtype, "kind", "") == "f"):
        return repr(float(valor))
    texto = str(valor).replace(":", " ").replace("'", "''")   # ':' seria lido como parâmetro
    return f"'{texto}'"


def tabela_em_sql(registros: list[tuple], colunas: list[str]) -> str:
    """Linhas Python → tabela derivada SQL (VALUES), compatível com SQLite e PostgreSQL."""
    if not registros:
        return "SELECT " + ", ".join(f"NULL AS {c}" for c in colunas) + " WHERE 1 = 0"
    selecao = ", ".join(f"column{i + 1} AS {c}" for i, c in enumerate(colunas))
    linhas = ",\n        ".join("(" + ", ".join(_valor_sql(v) for v in registro) + ")" for registro in registros)
    return f"SELECT {selecao}\n      FROM (VALUES\n        {linhas}) AS valores"


def tabela_csv_em_sql(nome: str, colunas: list[str], pasta: Path | None = None) -> str:
    """config/<nome>.csv → tabela derivada com as colunas pedidas (linhas com alguma delas vazia ficam de fora)."""
    caminho = (pasta or RAIZ / "config") / f"{nome}.csv"
    tabela = pd.read_csv(caminho, sep=";", dtype=str, encoding="utf-8-sig").fillna("")
    faltando = [c for c in colunas if c not in tabela.columns]
    if faltando:
        raise KeyError(f"{caminho.name}: colunas ausentes {faltando}")
    registros = []
    for _, linha in tabela.iterrows():
        valores = [str(linha[c]).strip() for c in colunas]
        if all(valores):
            registros.append(tuple(float(v) if re.fullmatch(r"-?\d+\.\d+", v) else
                                   int(v) if re.fullmatch(r"-?\d+", v) else v for v in valores))
    return tabela_em_sql(registros, colunas)


def incluir_tabelas_csv(sql: str, pasta: Path | None = None) -> str:
    """Troca {{csv:nome:col1,col2}} pela tabela derivada gerada de config/nome.csv."""
    return _TABELA_CSV.sub(lambda m: tabela_csv_em_sql(m.group(1), m.group(2).split(","), pasta), sql)


def incluir_dados(sql: str, dados: dict[str, pd.DataFrame]) -> str:
    """Troca {{dados:nome:col1,col2}} pela tabela `dados[nome]` (gerada pela preparação da regra)."""
    def troca(m: re.Match) -> str:
        nome, colunas = m.group(1), m.group(2).split(",")
        if nome not in dados:
            raise KeyError(f"consulta pede {{{{dados:{nome}}}}}, mas a preparação da regra não gerou essa tabela")
        tabela = dados[nome]
        faltando = [c for c in colunas if c not in tabela.columns]
        if faltando:
            raise KeyError(f"tabela de dados '{nome}' sem as colunas {faltando}")
        return tabela_em_sql(list(tabela[colunas].itertuples(index=False, name=None)), colunas)
    return _DADOS.sub(troca, sql)


@dataclass
class Regra:
    id: str
    nome: str
    sql: str
    parametros: dict = field(default_factory=dict)
    ativa: bool = True
    versao: str = "1.0"
    preparar: str | None = None

    @property
    def caminho_sql(self) -> Path:
        return RAIZ / self.sql

    def consulta(self) -> str:
        return incluir_tabelas_csv(self.caminho_sql.read_text(encoding="utf-8"))

    def parametros_da_consulta(self, data_inicio: str) -> dict:
        """Só os parâmetros que aparecem na consulta (:nome)."""
        disponiveis = {"data_inicio": data_inicio, **self.parametros}
        usados = set(_PARAMETRO_SQL.findall(_MARCADOR.sub("", sem_comentarios(self.consulta()))))
        faltando = usados - disponiveis.keys()
        if faltando:
            raise KeyError(f"Regra {self.id}: parâmetros sem valor {sorted(faltando)}")
        return {nome: disponiveis[nome] for nome in usados}

    def dados_preparados(self, engine: Engine, data_inicio: str) -> dict[str, pd.DataFrame]:
        """Roda a etapa Python da regra (config: preparar), se houver."""
        if not self.preparar:
            return {}
        modulo, funcao = self.preparar.split(":")
        return getattr(importlib.import_module(modulo), funcao)(engine, data_inicio, self.parametros)

    def consulta_para(self, engine: Engine, data_inicio: str) -> str:
        return incluir_dados(sem_comentarios(self.consulta()), self.dados_preparados(engine, data_inicio))

    def executar(self, engine: Engine, data_inicio: str) -> pd.DataFrame:
        consulta = self.consulta_para(engine, data_inicio)
        with engine.connect() as conexao:
            resultado = pd.read_sql(text(consulta), conexao, params=self.parametros_da_consulta(data_inicio))
        return padronizar_alertas(resultado, self)


def padronizar_alertas(df: pd.DataFrame, regra: Regra) -> pd.DataFrame:
    """Confere as colunas obrigatórias e acrescenta metadados de execução."""
    df = df.rename(columns=str.lower)
    df["id_regra"] = regra.id
    faltando = [c for c in COLUNAS_ALERTA if c not in df.columns]
    if faltando:
        raise ValueError(f"Regra {regra.id}: consulta sem as colunas {faltando}")

    saida = df[COLUNAS_ALERTA].copy()
    saida["id_objeto"] = saida["id_objeto"].astype(str)
    saida["cnpj_fornecedor"] = saida["cnpj_fornecedor"].map(normalizar_cnpj)
    saida["pontuacao"] = pd.to_numeric(saida["pontuacao"], errors="coerce").fillna(1.0).clip(0, 1)
    saida["valor_envolvido"] = pd.to_numeric(saida["valor_envolvido"], errors="coerce").fillna(0.0).round(2)
    saida["versao_regra"] = regra.versao
    saida["data_execucao"] = datetime.now().isoformat(timespec="seconds")
    saida["status_tratamento"] = "pendente"
    return saida


def carregar_regras(parametros: dict) -> dict[str, Regra]:
    """Monta os objetos Regra a partir de config/regras.yaml."""
    return {
        id_regra: Regra(
            id=id_regra,
            nome=conf["nome"],
            sql=conf["sql"],
            parametros=conf.get("parametros") or {},
            ativa=bool(conf.get("ativa", True)),
            versao=str(conf.get("versao", "1.0")),
            preparar=conf.get("preparar"),
        )
        for id_regra, conf in parametros.get("regras", {}).items()
    }
