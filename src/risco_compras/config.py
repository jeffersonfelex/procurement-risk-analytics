"""Leitura de parâmetros e variáveis de ambiente."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[2]
load_dotenv(RAIZ / ".env")

BANCO_EXEMPLO = RAIZ / "dados" / "exemplo.db"


def carregar_parametros(caminho: str | Path | None = None) -> dict:
    """Carrega config/regras.yaml (ou outro arquivo informado)."""
    caminho = Path(caminho) if caminho else RAIZ / "config" / "regras.yaml"
    with open(caminho, encoding="utf-8") as arquivo:
        return yaml.safe_load(arquivo)


def url_banco() -> str:
    """URL SQLAlchemy do banco analisado: DB_URL no .env ou a base sintética de exemplo."""
    return os.getenv("DB_URL") or f"sqlite:///{BANCO_EXEMPLO.as_posix()}"
