import pandas as pd

from risco_compras.grafos.vinculos import empresas_ligadas, grupos_vinculados, montar_grafo, normalizar_endereco

ARESTAS = pd.DataFrame([
    ("pj:A", "pf:1", "socio", 1.0),
    ("pj:B", "pf:1", "socio", 1.0),        # A e B: sócio em comum
    ("pj:B", "tel:99", "telefone", 0.7),
    ("pj:C", "tel:99", "telefone", 0.7),   # B e C: telefone em comum
    ("pj:D", "pf:2", "socio", 1.0),        # D isolada
], columns=["origem", "destino", "tipo", "peso"])


def test_pares_vinculados_ate_dois_saltos_com_peso():
    grafo = montar_grafo(ARESTAS)
    pares = {(p["empresa_a"], p["empresa_b"]): p for p in grupos_vinculados(grafo, ["pj:A", "pj:B", "pj:C", "pj:D"])}
    assert set(pares) == {("pj:A", "pj:B"), ("pj:B", "pj:C")}   # A–C precisa de 4 saltos
    assert pares[("pj:A", "pj:B")]["tipos"] == ["socio", "socio"] and pares[("pj:A", "pj:B")]["peso"] == 1.0
    assert pares[("pj:B", "pj:C")]["peso"] == 0.49


def test_empresas_ligadas_a_uma_pessoa():
    grafo = montar_grafo(ARESTAS)
    ligadas = {item["empresa"]: item for item in empresas_ligadas(grafo, "pf:1", max_saltos=3)}
    assert set(ligadas) == {"pj:A", "pj:B", "pj:C"}
    assert ligadas["pj:A"]["tipos"] == ["socio"]
    assert ligadas["pj:C"]["peso"] == 0.49
    assert empresas_ligadas(grafo, "pf:nao-existe") == []


def test_normalizar_endereco():
    assert normalizar_endereco("Rua Fictícia, 12 - Bairro Ômega") == "rua ficticia 12 bairro omega"
