import random

from risco_compras.utils.documentos import (
    cnpj_valido,
    cpf_valido,
    gerar_cnpj,
    gerar_cpf,
    normalizar_cnpj,
    normalizar_cpf,
    pseudonimizar,
    raiz_cnpj,
)


def test_normaliza_mascaras_e_zeros():
    assert normalizar_cpf("529.982.247-25") == "52998224725"
    assert normalizar_cpf(1234567890) == "01234567890"
    assert normalizar_cnpj("11.222.333/0001-81") == "11222333000181"
    assert normalizar_cnpj(None) == ""


def test_valida_digitos_verificadores():
    assert cpf_valido("529.982.247-25")
    assert not cpf_valido("529.982.247-24")
    assert not cpf_valido("111.111.111-11")
    assert cnpj_valido("11.222.333/0001-81")
    assert not cnpj_valido("11.222.333/0001-80")


def test_raiz_cnpj():
    assert raiz_cnpj("11.222.333/0001-81") == "11222333"


def test_geradores_produzem_documentos_validos_e_reprodutiveis():
    rng = random.Random(1)
    cpfs = [gerar_cpf(rng) for _ in range(200)]
    cnpjs = [gerar_cnpj(rng) for _ in range(200)]
    assert all(cpf_valido(c) for c in cpfs if c != c[0] * 11)
    assert all(cnpj_valido(c) for c in cnpjs if c != c[0] * 14)
    assert gerar_cnpj(random.Random(7)) == gerar_cnpj(random.Random(7))
    assert gerar_cnpj(rng, raiz="11222333", filial=1) == "11222333000181"


def test_pseudonimizacao_estavel_e_sem_mascara():
    a = pseudonimizar("529.982.247-25", segredo="teste")
    b = pseudonimizar("52998224725", segredo="teste")
    assert a == b and len(a) == 16
    assert pseudonimizar("52998224725", segredo="outro") != a
