"""Grafo de vínculos entre empresas e pessoas (sócios, telefones, e-mails e endereços)."""

from __future__ import annotations

import re
import unicodedata

import networkx as nx
import pandas as pd


def normalizar_endereco(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", sem_acento.lower()).strip()


def montar_grafo(arestas: pd.DataFrame, origem: str = "origem", destino: str = "destino", tipo: str = "tipo",
                 peso: str = "peso") -> nx.Graph:
    """Cria um grafo não direcionado a partir de uma tabela de arestas (peso padrão 1)."""
    grafo = nx.Graph()
    tem_peso = peso in arestas.columns
    for linha in arestas.itertuples(index=False):
        registro = linha._asdict()
        grafo.add_edge(registro[origem], registro[destino], tipo=registro[tipo],
                       peso=float(registro[peso]) if tem_peso else 1.0)
    return grafo


def _descrever(grafo: nx.Graph, caminho: list[str]) -> tuple[list[str], float]:
    tipos, peso = [], 1.0
    for u, v in zip(caminho, caminho[1:]):
        aresta = grafo.edges[u, v]
        tipos.append(aresta["tipo"])
        peso *= aresta["peso"]
    return tipos, round(peso, 3)


def grupos_vinculados(grafo: nx.Graph, empresas: list[str], max_saltos: int = 2) -> list[dict]:
    """Pares de empresas ligadas por até `max_saltos` arestas, com os tipos e o peso do caminho."""
    presentes = [c for c in dict.fromkeys(empresas) if c in grafo]
    pares = []
    for i, empresa_a in enumerate(presentes):
        alcance = nx.single_source_shortest_path(grafo, empresa_a, cutoff=max_saltos)
        for empresa_b in presentes[i + 1:]:
            if empresa_b in alcance:
                caminho = alcance[empresa_b]
                tipos, peso = _descrever(grafo, caminho)
                pares.append({"empresa_a": empresa_a, "empresa_b": empresa_b, "caminho": caminho,
                              "tipos": tipos, "peso": peso})
    return pares


def empresas_ligadas(grafo: nx.Graph, pessoa: str, max_saltos: int = 3) -> list[dict]:
    """Empresas alcançáveis a partir de uma pessoa em até `max_saltos` arestas."""
    if pessoa not in grafo:
        return []
    alcance = nx.single_source_shortest_path(grafo, pessoa, cutoff=max_saltos)
    ligadas = []
    for no, caminho in alcance.items():
        if str(no).startswith("pj:"):
            tipos, peso = _descrever(grafo, caminho)
            ligadas.append({"empresa": no, "caminho": caminho, "tipos": tipos, "peso": peso})
    return ligadas
