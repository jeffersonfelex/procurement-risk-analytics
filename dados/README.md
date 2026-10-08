# dados/

Pasta local, fora do versionamento (ver `.gitignore`).

- `exemplo.db` — base SQLite sintética, gerada por `python -m risco_compras.dados_sinteticos`.
- `resultados/` — alertas de cada regra, lista única (`.xlsx`), tabelas do painel, desfechos registrados
  e relatório do modelo.

Mesmo com dados sintéticos, a convenção do projeto é que nada desta pasta vá para o repositório:
num uso real, ela teria CPF, CNPJ e dados de pessoas.
