import pytest
from sqlalchemy import create_engine

from risco_compras.dados_sinteticos import gerar


@pytest.fixture(scope="session")
def base_sintetica(tmp_path_factory):
    """Base sintética pequena, gerada uma vez por sessão de testes."""
    caminho = tmp_path_factory.mktemp("dados") / "teste.db"
    gerar(caminho, semente=123, n_fornecedores=400)
    return create_engine(f"sqlite:///{caminho.as_posix()}")
