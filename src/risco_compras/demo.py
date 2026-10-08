"""Demonstração de ponta a ponta: base sintética → regras → lista única → modelo."""

from __future__ import annotations

import argparse

import pandas as pd
from sqlalchemy import text

from .config import BANCO_EXEMPLO, RAIZ, carregar_parametros, url_banco
from .conexao import engine
from .dados_sinteticos import gerar
from .modelos import risco_fornecedor
from .regras.base import carregar_regras
from .regras.executar import executar_regras
from .resultados import lista_unica


def cobertura_das_anomalias(eng, resultados: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Para cada regra: anomalias plantadas, quantas a regra encontrou e o total de alertas."""
    with eng.connect() as conexao:
        plantadas = pd.read_sql(text("SELECT regra, id_objeto FROM anomalias_plantadas"), conexao)
    linhas = []
    for regra, grupo in plantadas.groupby("regra"):
        achados = set(resultados[regra]["id_objeto"]) if regra in resultados else set()
        linhas.append({"regra": regra, "plantadas": len(grupo), "encontradas": len(set(grupo["id_objeto"]) & achados),
                       "alertas": len(resultados.get(regra, []))})
    return pd.DataFrame(linhas)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Demonstração de ponta a ponta (base sintética)")
    parser.add_argument("--recriar", action="store_true", help="Gera a base sintética de novo")
    parser.add_argument("--semente", type=int, default=42)
    args = parser.parse_args(argv)

    if url_banco().startswith("sqlite") and (args.recriar or not BANCO_EXEMPLO.exists()):
        print("== 1. Gerando a base sintética", flush=True)
        gerar(BANCO_EXEMPLO, semente=args.semente)

    print("\n== 2. Executando as regras", flush=True)
    parametros = carregar_parametros()
    padrao = parametros["padrao"]
    regras = [r for r in carregar_regras(parametros).values() if r.ativa]
    eng = engine()
    resultados = executar_regras(regras, eng, padrao["data_inicio"], RAIZ / padrao["pasta_saida"])
    print("\nAnomalias plantadas encontradas por regra:")
    print(cobertura_das_anomalias(eng, resultados).to_string(index=False))

    print("\n== 3. Montando a lista única de casos", flush=True)
    lista_unica.montar()

    print("\n== 4. Avaliando o modelo de risco de fornecedor", flush=True)
    risco_fornecedor.main([])


if __name__ == "__main__":
    main()
