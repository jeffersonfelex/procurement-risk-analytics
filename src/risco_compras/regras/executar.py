"""Executa as regras e grava os alertas em dados/resultados."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy.engine import Engine

from ..config import RAIZ, carregar_parametros
from ..conexao import descrever_erro, engine
from .base import Regra, carregar_regras


def executar_regras(regras: list[Regra], eng: Engine, data_inicio: str, pasta_saida: Path,
                    detalhes: bool = False) -> dict[str, pd.DataFrame]:
    """Roda cada regra e grava alertas_<ID>_<carimbo>.csv; uma regra com erro não derruba as outras."""
    pasta_saida.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    resultados = {}
    for regra in regras:
        inicio = datetime.now()
        print(f"{inicio:%H:%M:%S} {regra.id} v{regra.versao}: executando — {regra.nome}", flush=True)
        try:
            alertas = regra.executar(eng, data_inicio)
        except Exception as erro:
            if detalhes:
                raise
            segundos = (datetime.now() - inicio).total_seconds()
            print(f"{regra.id}: ERRO em {segundos:.1f} s — {descrever_erro(erro)}", flush=True)
            continue
        segundos = (datetime.now() - inicio).total_seconds()
        alertas.to_csv(pasta_saida / f"alertas_{regra.id}_{carimbo}.csv", index=False, sep=";", encoding="utf-8")
        print(f"{regra.id}: {len(alertas)} alertas em {segundos:.1f} s", flush=True)
        resultados[regra.id] = alertas
    if len(resultados) > 1:
        consolidado = pd.concat(resultados.values(), ignore_index=True)
        consolidado.to_csv(pasta_saida / f"alertas_consolidado_{carimbo}.csv", index=False, sep=";", encoding="utf-8")
    return resultados


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Executa regras de auditoria contínua")
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--regra", help="ID da regra (ex.: R2)")
    grupo.add_argument("--todas", action="store_true", help="Executa todas as regras ativas")
    parser.add_argument("--data-inicio", help="Sobrepõe padrao.data_inicio do YAML")
    parser.add_argument("--mostrar-sql", action="store_true", help="Só imprime a consulta")
    parser.add_argument("--detalhes", action="store_true", help="Em caso de erro, mostra o rastreamento completo")
    args = parser.parse_args(argv)

    parametros = carregar_parametros()
    padrao = parametros.get("padrao", {})
    data_inicio = args.data_inicio or padrao.get("data_inicio")
    regras = carregar_regras(parametros)
    selecionadas = [regras[args.regra]] if args.regra else [r for r in regras.values() if r.ativa]

    if args.mostrar_sql:
        for regra in selecionadas:
            print(f"-- {regra.id}: {regra.nome}\n{regra.consulta()}\n")
        return
    executar_regras(selecionadas, engine(), data_inicio, RAIZ / padrao.get("pasta_saida", "dados/resultados"),
                    detalhes=args.detalhes)


if __name__ == "__main__":
    main()
