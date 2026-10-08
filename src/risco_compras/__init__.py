"""Análise de risco em compras: regras de auditoria contínua, lista única de casos e modelo de risco.

Módulos:
    config            parâmetros (YAML) e variáveis de ambiente (.env)
    conexao           engine SQLAlchemy e mensagens de erro do banco
    dados_sinteticos  base SQLite fictícia de compras, com anomalias plantadas
    utils             CPF/CNPJ (normalização, validação, pseudonimização)
    regras            execução das regras SQL e padronização dos alertas
    grafos            grafo de vínculos (sócios, telefones, endereços)
    resultados        lista única de casos, planilha de análise e registro de desfechos
    modelos           modelo de risco de fornecedor com validação temporal
"""

__version__ = "1.0.0"
