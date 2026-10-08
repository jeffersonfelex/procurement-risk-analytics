"""Engine SQLAlchemy e mensagens curtas para erros de banco."""

from __future__ import annotations

import re
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from .config import url_banco


@lru_cache(maxsize=None)
def engine(url: str | None = None) -> Engine:
    return create_engine(url or url_banco(), pool_pre_ping=True)


def causa_do_erro(erro: BaseException) -> BaseException:
    """Desce pela cadeia pandas → SQLAlchemy → driver e devolve o erro original do banco."""
    atual, vistos = erro, set()
    while id(atual) not in vistos:
        vistos.add(id(atual))
        proximo = getattr(atual, "orig", None) or atual.__cause__
        if not isinstance(proximo, BaseException):
            break
        atual = proximo
    return atual


_CODIGO_ERRO = re.compile(r"\b(ORA-\d{5}|DPY-\d{4}|SQLSTATE\[\w+\])")


def descrever_erro(erro: BaseException, limite: int = 400) -> str:
    """Texto curto do erro do banco, começando pelo código do erro quando houver."""
    causa = causa_do_erro(erro)
    texto = " ".join(str(causa).split())
    achado = _CODIGO_ERRO.search(texto)
    if achado:
        texto = texto[achado.start():]
    elif texto.startswith("Execution failed on sql"):
        texto = texto.rsplit("': ", 1)[-1]
    return f"{type(causa).__name__}: {texto[:limite]}"
