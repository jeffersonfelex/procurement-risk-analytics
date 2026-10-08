"""Modelo de risco de fornecedor: chance de bloqueio nos 12 meses seguintes a cada data de corte.

As variáveis usam só pedidos anteriores ao corte, quem já estava bloqueado sai da base e a
validação é temporal (treina nos cortes antigos e testa no último).
"""

from __future__ import annotations

import argparse
import json
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text

from ..config import RAIZ
from ..conexao import engine

MESES_HISTORICO = 24
MESES_HORIZONTE = 12
CORTES_PADRAO = ("2023-01-01", "2024-01-01", "2025-01-01")

VARIAVEIS = {
    "vl_24m": "Valor comprado nos 24 meses antes do corte (R$)",
    "vl_12m": "Valor comprado nos 12 meses antes do corte (R$)",
    "crescimento": "vl_12m ÷ valor dos 12 meses anteriores (+1)",
    "qt_pedidos_24m": "Pedidos nos 24 meses",
    "vl_medio_pedido": "Valor médio por pedido (R$)",
    "vl_max_pedido": "Maior pedido (R$)",
    "qt_departamentos": "Departamentos compradores distintos",
    "hhi_departamentos": "Concentração do valor por departamento (Herfindahl, 0 a 1)",
    "pct_direta": "Fração do valor em compra direta (sem cotação)",
    "pct_dezembro": "Fração do valor comprado em dezembro",
    "qt_categorias": "Categorias distintas",
    "meses_ativos_24m": "Meses com pedido nos 24 meses",
    "meses_desde_primeiro": "Meses desde o primeiro pedido",
    "meses_desde_ultimo": "Meses desde o último pedido",
    "idade_empresa_meses": "Idade da empresa no corte (meses)",
    "log_capital": "log10 do capital social",
}


def carregar(eng=None) -> dict[str, pd.DataFrame]:
    eng = eng or engine()
    with eng.connect() as conexao:
        pedidos = pd.read_sql(text("SELECT cnpj, departamento, categoria, data, valor, modalidade FROM pedidos"),
                              conexao)
        fornecedores = pd.read_sql(text("SELECT cnpj, data_abertura, capital_social FROM fornecedores"), conexao)
        bloqueios = pd.read_sql(text("SELECT cnpj, data_inicio FROM bloqueios"), conexao)
    for tabela in (pedidos, fornecedores, bloqueios):
        tabela["raiz"] = tabela["cnpj"].astype(str).str.zfill(14).str[:8]
    pedidos["data"] = pd.to_datetime(pedidos["data"])
    fornecedores["data_abertura"] = pd.to_datetime(fornecedores["data_abertura"])
    bloqueios["data_inicio"] = pd.to_datetime(bloqueios["data_inicio"])
    return {"pedidos": pedidos, "fornecedores": fornecedores, "bloqueios": bloqueios}


def _meses(delta: pd.Series) -> pd.Series:
    return (delta.dt.days / 30.44).round(1)


def variaveis_no_corte(pedidos: pd.DataFrame, fornecedores: pd.DataFrame, corte: pd.Timestamp) -> pd.DataFrame:
    """Variáveis de cada CNPJ raiz com pedido nos 24 meses antes do corte (só dados anteriores ao corte)."""
    passado = pedidos[pedidos["data"] < corte]
    janela = passado[passado["data"] >= corte - pd.DateOffset(months=MESES_HISTORICO)]
    if janela.empty:
        return pd.DataFrame(columns=["raiz", "corte", *VARIAVEIS])
    ultimos_12 = janela["data"] >= corte - pd.DateOffset(months=12)
    janela = janela.assign(
        vl_12=janela["valor"].where(ultimos_12, 0.0),
        vl_12_anterior=janela["valor"].where(~ultimos_12, 0.0),
        vl_direta=janela["valor"].where(janela["modalidade"] == "compra_direta", 0.0),
        vl_dezembro=janela["valor"].where(janela["data"].dt.month == 12, 0.0),
        mes=janela["data"].dt.to_period("M"),
    )
    g = janela.groupby("raiz")
    base = pd.DataFrame({
        "vl_24m": g["valor"].sum(),
        "vl_12m": g["vl_12"].sum(),
        "vl_12_anterior": g["vl_12_anterior"].sum(),
        "qt_pedidos_24m": g.size(),
        "vl_max_pedido": g["valor"].max(),
        "qt_departamentos": g["departamento"].nunique(),
        "vl_direta": g["vl_direta"].sum(),
        "vl_dezembro": g["vl_dezembro"].sum(),
        "qt_categorias": g["categoria"].nunique(),
        "meses_ativos_24m": g["mes"].nunique(),
        "ultimo": g["data"].max(),
    })
    por_departamento = janela.groupby(["raiz", "departamento"])["valor"].sum()
    participacao = por_departamento / por_departamento.groupby(level="raiz").transform("sum")
    base["hhi_departamentos"] = (participacao ** 2).groupby(level="raiz").sum()
    base["crescimento"] = base["vl_12m"] / (base["vl_12_anterior"] + 1.0)
    base["vl_medio_pedido"] = base["vl_24m"] / base["qt_pedidos_24m"]
    base["pct_direta"] = base["vl_direta"] / base["vl_24m"]
    base["pct_dezembro"] = base["vl_dezembro"] / base["vl_24m"]
    base["meses_desde_primeiro"] = _meses(corte - passado.groupby("raiz")["data"].min()).reindex(base.index)
    base["meses_desde_ultimo"] = _meses(corte - base["ultimo"])
    cadastro = fornecedores.groupby("raiz").agg(abertura=("data_abertura", "min"), capital=("capital_social", "max"))
    base["idade_empresa_meses"] = _meses(corte - cadastro["abertura"].reindex(base.index))
    base["log_capital"] = np.log10(cadastro["capital"].reindex(base.index).clip(lower=1))
    base = base.reset_index()
    base.insert(1, "corte", corte)
    return base[["raiz", "corte", *VARIAVEIS]]


def rotular(base: pd.DataFrame, bloqueios: pd.DataFrame, corte: pd.Timestamp) -> pd.DataFrame:
    """y = bloqueio com início em [corte, corte + 12 meses); quem já tinha bloqueio antes do corte sai da base."""
    fim = corte + pd.DateOffset(months=MESES_HORIZONTE)
    antes = set(bloqueios.loc[bloqueios["data_inicio"] < corte, "raiz"])
    na_janela = set(bloqueios.loc[(bloqueios["data_inicio"] >= corte) & (bloqueios["data_inicio"] < fim), "raiz"])
    base = base[~base["raiz"].isin(antes)].copy()
    base["y"] = base["raiz"].isin(na_janela).astype(int)
    return base


def montar_base(dados: dict[str, pd.DataFrame], cortes=CORTES_PADRAO) -> pd.DataFrame:
    partes = []
    for corte in map(pd.Timestamp, cortes):
        base = variaveis_no_corte(dados["pedidos"], dados["fornecedores"], corte)
        partes.append(rotular(base, dados["bloqueios"], corte))
    return pd.concat(partes, ignore_index=True)


def ajustar(treino: pd.DataFrame) -> Pipeline:
    modelo = Pipeline([
        ("imputar", SimpleImputer(strategy="median")),
        ("padronizar", StandardScaler()),
        ("logistica", LogisticRegression(class_weight="balanced", max_iter=2000, C=0.5)),
    ])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        modelo.fit(treino[list(VARIAVEIS)], treino["y"])
    return modelo


def metricas(y: pd.Series, score: np.ndarray, ks=(10, 25)) -> dict:
    y = np.asarray(y)
    ordem = np.argsort(-np.asarray(score), kind="stable")
    prevalencia = float(y.mean())
    saida = {"n": int(len(y)), "positivos": int(y.sum()), "prevalencia": round(prevalencia, 4),
             "average_precision": round(float(average_precision_score(y, score)), 4) if y.any() else None,
             "roc_auc": round(float(roc_auc_score(y, score)), 4) if 0 < y.sum() < len(y) else None}
    for k in ks:
        precisao = float(y[ordem[:k]].mean()) if len(y) else 0.0
        saida[f"precisao@{k}"] = round(precisao, 3)
        saida[f"lift@{k}"] = round(precisao / prevalencia, 2) if prevalencia else None
    return saida


def experimentar(base: pd.DataFrame) -> dict:
    """Treina nos cortes anteriores ao último e avalia no último (validação fora do tempo)."""
    cortes = sorted(base["corte"].unique())
    if len(cortes) < 2:
        raise ValueError("São necessários ao menos 2 cortes (treino e teste)")
    treino, teste = base[base["corte"] < cortes[-1]], base[base["corte"] == cortes[-1]]
    if treino["y"].nunique() < 2:
        raise ValueError("O treino precisa de exemplos positivos e negativos")
    modelo = ajustar(treino)
    score = modelo.predict_proba(teste[list(VARIAVEIS)])[:, 1]
    coeficientes = pd.Series(modelo.named_steps["logistica"].coef_[0], index=list(VARIAVEIS))
    return {
        "cortes_treino": [str(pd.Timestamp(c).date()) for c in cortes[:-1]],
        "corte_teste": str(pd.Timestamp(cortes[-1]).date()),
        "treino": {"n": int(len(treino)), "positivos": int(treino["y"].sum())},
        "modelo": metricas(teste["y"], score),
        "linha_de_base_valor": metricas(teste["y"], teste["vl_24m"].to_numpy()),
        "coeficientes": {k: round(float(v), 3) for k, v in coeficientes.sort_values(key=abs, ascending=False).items()},
    }


def relatorio(resultado: dict) -> str:
    def linha(nome: str, m: dict) -> str:
        return (f"| {nome} | {m['average_precision']} | {m['roc_auc']} | {m['precisao@10']} | {m['lift@10']} "
                f"| {m['precisao@25']} | {m['lift@25']} |")

    teste = resultado["modelo"]
    partes = [
        "# Modelo de risco de fornecedor — avaliação fora do tempo",
        "",
        f"Treino: cortes {', '.join(resultado['cortes_treino'])} ({resultado['treino']['n']} empresas-corte, "
        f"{resultado['treino']['positivos']} bloqueadas nos 12 meses seguintes).",
        f"Teste: corte {resultado['corte_teste']} ({teste['n']} empresas, {teste['positivos']} bloqueadas; "
        f"prevalência {teste['prevalencia']:.1%}).",
        "",
        "| Ranking | Average precision | ROC-AUC | Precisão@10 | Lift@10 | Precisão@25 | Lift@25 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        linha("Regressão logística", teste),
        linha("Linha de base: maior valor comprado", resultado["linha_de_base_valor"]),
        "",
        "Lift@k = precisão nos k primeiros ÷ prevalência: quantas vezes melhor que escolher ao acaso.",
        "",
        "## Coeficientes (variáveis padronizadas)",
        "",
        "| Variável | Coeficiente | Descrição |",
        "| --- | --- | --- |",
        *[f"| {nome} | {coef:+.3f} | {VARIAVEIS[nome]} |" for nome, coef in resultado["coeficientes"].items()],
        "",
        "Relatório agregado: não contém CNPJ nem ranking nominal de empresas.",
    ]
    return "\n".join(partes) + "\n"


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description="Monta a base e avalia o modelo de risco de fornecedor")
    parser.add_argument("--cortes", nargs="+", default=list(CORTES_PADRAO))
    parser.add_argument("--pasta", default=str(RAIZ / "dados" / "resultados"))
    args = parser.parse_args(argv)
    base = montar_base(carregar(), args.cortes)
    resultado = experimentar(base)
    pasta = Path(args.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    (pasta / f"modelo_risco_{carimbo}.json").write_text(json.dumps(resultado, indent=2, ensure_ascii=False),
                                                        encoding="utf-8")
    texto = relatorio(resultado)
    (pasta / f"modelo_risco_{carimbo}.md").write_text(texto, encoding="utf-8")
    print(texto)
    return resultado


if __name__ == "__main__":
    main()
