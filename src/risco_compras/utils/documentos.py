"""Normalização, validação e pseudonimização de CPF e CNPJ.

A resolução de entidades (ligar a mesma pessoa ou empresa entre bases) começa aqui:
todas as bases devem gravar CPF com 11 dígitos e CNPJ com 14, sem máscara.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re

_NAO_DIGITO = re.compile(r"\D")


def somente_digitos(valor: object) -> str:
    """Remove máscara e espaços. None vira string vazia."""
    if valor is None:
        return ""
    return _NAO_DIGITO.sub("", str(valor))


def normalizar_cpf(valor: object) -> str:
    """CPF com 11 dígitos (completa zeros à esquerda perdidos em planilhas)."""
    digitos = somente_digitos(valor)
    return digitos.zfill(11) if digitos else ""


def normalizar_cnpj(valor: object) -> str:
    """CNPJ com 14 dígitos (completa zeros à esquerda perdidos em planilhas)."""
    digitos = somente_digitos(valor)
    return digitos.zfill(14) if digitos else ""


def _digito(numeros: str, pesos: list[int]) -> str:
    resto = sum(int(n) * p for n, p in zip(numeros, pesos)) % 11
    return "0" if resto < 2 else str(11 - resto)


def cpf_valido(valor: object) -> bool:
    cpf = normalizar_cpf(valor)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    d1 = _digito(cpf[:9], list(range(10, 1, -1)))
    d2 = _digito(cpf[:9] + d1, list(range(11, 1, -1)))
    return cpf[-2:] == d1 + d2


def cnpj_valido(valor: object) -> bool:
    cnpj = normalizar_cnpj(valor)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    d1 = _digito(cnpj[:12], pesos1)
    d2 = _digito(cnpj[:12] + d1, pesos2)
    return cnpj[-2:] == d1 + d2


def raiz_cnpj(valor: object) -> str:
    """Oito primeiros dígitos: identifica a empresa (matriz e filiais)."""
    return normalizar_cnpj(valor)[:8]


def pseudonimizar(valor: object, segredo: str | None = None) -> str:
    """Código estável e irreversível para CPF/CNPJ (HMAC-SHA256, 16 caracteres).

    Mantém a possibilidade de cruzar bases no ambiente de desenvolvimento
    sem expor o documento. O segredo vem de SEGREDO_PSEUDONIMIZACAO no .env.
    """
    segredo = segredo or os.getenv("SEGREDO_PSEUDONIMIZACAO")
    if not segredo:
        raise RuntimeError("Defina SEGREDO_PSEUDONIMIZACAO no .env")
    documento = somente_digitos(valor)
    return hmac.new(segredo.encode(), documento.encode(), hashlib.sha256).hexdigest()[:16]


def gerar_cpf(rng) -> str:
    """CPF fictício com dígitos verificadores corretos (rng: random.Random). Só para dados sintéticos."""
    base = "".join(str(rng.randint(0, 9)) for _ in range(9))
    d1 = _digito(base, list(range(10, 1, -1)))
    return base + d1 + _digito(base + d1, list(range(11, 1, -1)))


def gerar_cnpj(rng, raiz: str | None = None, filial: int = 1) -> str:
    """CNPJ fictício com dígitos verificadores corretos. Só para dados sintéticos."""
    raiz = raiz or "".join(str(rng.randint(0, 9)) for _ in range(8))
    base = raiz + f"{filial:04d}"
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = _digito(base, pesos1)
    return base + d1 + _digito(base + d1, [6] + pesos1)
