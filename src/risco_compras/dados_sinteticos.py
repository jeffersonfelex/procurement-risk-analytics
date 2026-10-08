"""Base SQLite fictícia de compras de uma empresa, com anomalias plantadas.

Tudo aqui é inventado: empresas, pessoas, CPFs/CNPJs (gerados aleatoriamente, só com dígitos
verificadores válidos), telefones com DDD 00 e e-mails no domínio .example. Serve para o projeto
rodar de ponta a ponta sem nenhum dado real.

Além do comportamento "normal", o gerador planta casos conhecidos para cada regra e os registra na
tabela anomalias_plantadas (regra, id_objeto) — os testes e a demo medem se as regras os encontram.
Uma parte dos fornecedores tem perfil de risco (compras diretas no limite, concentração em um
departamento e em dezembro) e é bloqueada mais tarde: é o sinal que o modelo de risco precisa achar.

Exemplo:
    python -m risco_compras.dados_sinteticos                 # grava dados/exemplo.db
    python -m risco_compras.dados_sinteticos --semente 7 --fornecedores 800
"""

from __future__ import annotations

import argparse
import random
import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from .config import BANCO_EXEMPLO
from .utils.documentos import gerar_cnpj, gerar_cpf

LIMITE_COMPRA_DIRETA = 20_000.00   # acima disso a política de compras exige cotação (ver config/regras.yaml)
INICIO, FIM = date(2021, 1, 1), date(2025, 12, 31)

DEPARTAMENTOS = ["Operações", "TI", "Marketing", "Facilities", "Logística", "Financeiro", "Jurídico", "RH"]
CATEGORIAS = ["Material de escritório", "Serviços de TI", "Manutenção predial", "Transporte", "Consultoria",
              "Equipamentos", "Eventos", "Limpeza", "Gráfica", "Alimentação"]
_PREFIXOS = ["Alfa", "Beta", "Delta", "Ômega", "Nova", "Prime", "Vértice", "Horizonte", "Atlas", "Pioneira",
             "Central", "Global", "Integra", "Sigma", "Real", "Aurora", "Norte", "Sul", "Leste", "Oeste"]
_RAMOS = ["Serviços", "Comércio", "Soluções", "Distribuidora", "Tecnologia", "Suprimentos", "Engenharia",
          "Logística", "Consultoria", "Indústria"]
_NOMES = ["Ana", "Bruno", "Carla", "Diego", "Elisa", "Fábio", "Gabriela", "Heitor", "Íris", "João", "Karen",
          "Lucas", "Marina", "Nelson", "Olívia", "Paulo", "Renata", "Sérgio", "Tânia", "Vítor"]
_SOBRENOMES = ["Almeida", "Barros", "Campos", "Duarte", "Esteves", "Freitas", "Gomes", "Lima", "Moraes",
               "Nunes", "Pires", "Queiroz", "Rocha", "Silveira", "Teixeira", "Vasconcelos"]
# categorias que a R1 não analisa (config/categorias_recorrentes.csv): não recebem fracionamento plantado
CATEGORIAS_RECORRENTES = ("Alimentação",)
_MOTIVOS_BLOQUEIO = ["inexecução contratual", "fraude documental", "atraso reiterado", "irregularidade fiscal"]

ESQUEMA = """
CREATE TABLE fornecedores (cnpj TEXT PRIMARY KEY, razao_social TEXT, data_abertura TEXT,
                           capital_social REAL, telefone TEXT, endereco TEXT, email TEXT);
CREATE TABLE socios (cnpj TEXT, cpf TEXT, nome TEXT);
CREATE TABLE funcionarios (cpf TEXT PRIMARY KEY, nome TEXT, departamento TEXT);
CREATE TABLE bloqueios (id_bloqueio INTEGER PRIMARY KEY, cnpj TEXT, data_inicio TEXT, data_publicacao TEXT,
                        data_fim TEXT, motivo TEXT);
CREATE TABLE contratos (id_contrato TEXT PRIMARY KEY, cnpj TEXT, departamento TEXT, objeto TEXT, valor REAL,
                        data_inicio TEXT, data_fim TEXT);
CREATE TABLE cotacoes (id_cotacao TEXT PRIMARY KEY, departamento TEXT, categoria TEXT, data TEXT);
CREATE TABLE propostas (id_cotacao TEXT, cnpj TEXT, valor REAL, vencedora INTEGER);
CREATE TABLE pedidos (id_pedido TEXT PRIMARY KEY, cnpj TEXT, departamento TEXT, categoria TEXT, data TEXT,
                      valor REAL, modalidade TEXT, id_cotacao TEXT, id_contrato TEXT);
CREATE TABLE pagamentos (id_pagamento TEXT PRIMARY KEY, id_pedido TEXT, cnpj TEXT, data TEXT, valor REAL,
                         nota_fiscal TEXT);
CREATE TABLE anomalias_plantadas (regra TEXT, id_objeto TEXT);
CREATE INDEX ix_pedidos_cnpj ON pedidos (cnpj, data);
CREATE INDEX ix_pagamentos_cnpj ON pagamentos (cnpj, data);
"""


@dataclass
class Fornecedor:
    cnpj: str
    departamentos: list[str]
    categorias: list[str]
    risco: bool
    ativo_desde: date
    bloqueio: tuple[date, date] | None = None


@dataclass
class Gerador:
    rng: random.Random
    linhas: dict[str, list[tuple]] = field(default_factory=lambda: {t: [] for t in (
        "fornecedores", "socios", "funcionarios", "bloqueios", "contratos", "cotacoes", "propostas",
        "pedidos", "pagamentos", "anomalias_plantadas")})
    contadores: dict[str, int] = field(default_factory=dict)

    # ------------------------------------------------------------ utilitários
    def proximo(self, prefixo: str) -> str:
        self.contadores[prefixo] = self.contadores.get(prefixo, 0) + 1
        return f"{prefixo}-{self.contadores[prefixo]:06d}"

    def data_entre(self, inicio: date, fim: date) -> date:
        return inicio + timedelta(days=self.rng.randint(0, max((fim - inicio).days, 0)))

    def nome_pessoa(self) -> str:
        return f"{self.rng.choice(_NOMES)} {self.rng.choice(_SOBRENOMES)} {self.rng.choice(_SOBRENOMES)}"

    def plantar(self, regra: str, id_objeto: str) -> None:
        self.linhas["anomalias_plantadas"].append((regra, id_objeto))

    # ------------------------------------------------------------ cadastro
    def novo_fornecedor(self, i: int, risco: bool, abertura: date | None = None,
                        capital: float | None = None) -> Fornecedor:
        cnpj = gerar_cnpj(self.rng)
        nome = f"{self.rng.choice(_PREFIXOS)} {self.rng.choice(_RAMOS)} {i:04d} Ltda"
        abertura = abertura or self.data_entre(date(2005, 1, 1), date(2019, 12, 31))
        capital = capital if capital is not None else round(10 ** self.rng.uniform(4.5, 6.7), -3)
        telefone = f"(00) 9{self.rng.randint(1000, 9999)}-{self.rng.randint(1000, 9999)}"
        endereco = f"Rua Fictícia {self.rng.randint(1, 4000)}, Bairro {self.rng.choice(_PREFIXOS)}"
        self.linhas["fornecedores"].append((cnpj, nome, abertura.isoformat(), capital, telefone, endereco,
                                            f"contato@fornecedor{i:04d}.example"))
        for _ in range(self.rng.choice((1, 1, 2, 3))):
            self.linhas["socios"].append((cnpj, gerar_cpf(self.rng), self.nome_pessoa()))
        departamentos = (self.rng.sample(DEPARTAMENTOS, 1) if risco
                         else self.rng.sample(DEPARTAMENTOS, self.rng.randint(1, 4)))
        return Fornecedor(cnpj, departamentos, self.rng.sample(CATEGORIAS, self.rng.randint(1, 2)), risco,
                          ativo_desde=self.data_entre(INICIO, date(2024, 6, 30)))

    # ------------------------------------------------------------ movimento
    def pedido(self, f: Fornecedor, data: date, valor: float, departamento: str | None = None,
               categoria: str | None = None, modalidade: str | None = None, id_contrato: str | None = None,
               concorrentes: list[str] | None = None, pagar: bool = True) -> str:
        departamento = departamento or self.rng.choice(f.departamentos)
        categoria = categoria or self.rng.choice(f.categorias)
        modalidade = modalidade or ("cotacao" if valor > LIMITE_COMPRA_DIRETA else "compra_direta")
        id_cotacao = None
        if modalidade == "cotacao":
            id_cotacao = self.proximo("COT")
            self.linhas["cotacoes"].append((id_cotacao, departamento, categoria,
                                            (data - timedelta(days=self.rng.randint(10, 40))).isoformat()))
            self.linhas["propostas"].append((id_cotacao, f.cnpj, round(valor, 2), 1))
            for outro in concorrentes or []:
                self.linhas["propostas"].append((id_cotacao, outro, round(valor * self.rng.uniform(1.03, 1.25), 2), 0))
        id_pedido = self.proximo("PED")
        self.linhas["pedidos"].append((id_pedido, f.cnpj, departamento, categoria, data.isoformat(), round(valor, 2),
                                       modalidade, id_cotacao, id_contrato))
        if pagar:
            self.pagamento(id_pedido, f.cnpj, data + timedelta(days=self.rng.randint(15, 45)), valor)
        return id_pedido

    def pagamento(self, id_pedido: str, cnpj: str, data: date, valor: float, nota_fiscal: str | None = None) -> str:
        id_pagamento = self.proximo("PAG")
        self.linhas["pagamentos"].append((id_pagamento, id_pedido, cnpj, data.isoformat(), round(valor, 2),
                                          nota_fiscal or self.proximo("NF")))
        return id_pagamento

    def valor_normal(self) -> float:
        return round(min(10 ** self.rng.gauss(3.7, 0.45), 250_000), 2)   # mediana ~ R$ 5 mil

    def data_do_pedido(self, f: Fornecedor) -> date:
        data = self.data_entre(f.ativo_desde, FIM - timedelta(days=60))
        if f.risco and self.rng.random() < 0.35:   # perfil de risco: concentração em dezembro
            data = date(data.year, 12, self.rng.randint(1, 20))
        return data

    def bloqueado_em(self, f: Fornecedor, data: date) -> bool:
        return bool(f.bloqueio) and f.bloqueio[0] <= data <= f.bloqueio[1]


def gerar(caminho: str | Path = BANCO_EXEMPLO, semente: int = 42, n_fornecedores: int = 600,
          n_funcionarios: int = 300) -> dict[str, int]:
    """Grava a base em `caminho` (sobrescreve) e devolve o número de linhas por tabela."""
    g = Gerador(random.Random(semente))
    rng = g.rng

    funcionarios = [(gerar_cpf(rng), g.nome_pessoa(), rng.choice(DEPARTAMENTOS)) for _ in range(n_funcionarios)]
    g.linhas["funcionarios"] = funcionarios

    fornecedores = [g.novo_fornecedor(i, risco=rng.random() < 0.12) for i in range(1, n_fornecedores + 1)]
    cnpjs = [f.cnpj for f in fornecedores]

    # bloqueios: a maioria dos fornecedores de risco é bloqueada em algum momento; alguns normais também
    for f in fornecedores:
        if rng.random() < (0.75 if f.risco else 0.02):
            inicio = g.data_entre(date(2022, 3, 1), date(2025, 10, 31))
            fim = inicio + timedelta(days=rng.choice((365, 540, 730)))
            f.bloqueio = (inicio, fim)
            publicacao = inicio + timedelta(days=rng.randint(0, 30))
            g.linhas["bloqueios"].append((len(g.linhas["bloqueios"]) + 1, f.cnpj, inicio.isoformat(),
                                          publicacao.isoformat(), fim.isoformat(), rng.choice(_MOTIVOS_BLOQUEIO)))

    # contratos de parte dos fornecedores normais, com pedidos dentro da vigência e do valor
    contratos = []
    for f in rng.sample([f for f in fornecedores if not f.risco and not f.bloqueio], 120):
        inicio = g.data_entre(date(2021, 6, 1), date(2024, 6, 30))
        fim = inicio + timedelta(days=rng.choice((365, 730)))
        valor = round(rng.uniform(80_000, 600_000), -2)
        id_contrato = g.proximo("CTR")
        departamento = rng.choice(f.departamentos)
        g.linhas["contratos"].append((id_contrato, f.cnpj, departamento, rng.choice(f.categorias), valor,
                                      inicio.isoformat(), fim.isoformat()))
        contratos.append((id_contrato, f, departamento, valor, inicio, fim))
        n = rng.randint(3, 8)
        for _ in range(n):
            g.pedido(f, g.data_entre(inicio, fim - timedelta(days=30)), valor / n * rng.uniform(0.6, 0.95),
                     departamento=departamento, modalidade="contrato", id_contrato=id_contrato)

    # pedidos avulsos (compra direta ou cotação), fora dos períodos de bloqueio
    for f in fornecedores:
        for _ in range(max(1, int(rng.gauss(18 if f.risco else 14, 5)))):
            data = g.data_do_pedido(f)
            if g.bloqueado_em(f, data):
                continue
            if f.risco and rng.random() < 0.6:   # perfil de risco: compra direta logo abaixo do limite
                valor = LIMITE_COMPRA_DIRETA * rng.uniform(0.70, 0.98)
            else:
                valor = g.valor_normal()
            concorrentes = rng.sample(cnpjs, 2) if valor > LIMITE_COMPRA_DIRETA else None
            g.pedido(f, data, valor, concorrentes=[c for c in concorrentes or [] if c != f.cnpj])

    normais = [f for f in fornecedores if not f.risco and not f.bloqueio]
    _plantar_anomalias(g, fornecedores, normais, contratos, funcionarios, n_fornecedores)

    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if caminho.exists():
        caminho.unlink()
    with sqlite3.connect(caminho) as conexao:
        conexao.executescript(ESQUEMA)
        for tabela, linhas in g.linhas.items():
            if linhas:
                marcadores = ", ".join("?" * len(linhas[0]))
                conexao.executemany(f"INSERT INTO {tabela} VALUES ({marcadores})", linhas)
    return {tabela: len(linhas) for tabela, linhas in g.linhas.items()}


def _plantar_anomalias(g: Gerador, fornecedores, normais, contratos, funcionarios, n_fornecedores) -> None:
    rng = g.rng
    escolhidos = iter(rng.sample(normais, 40))

    # R1 fracionamento: 3-4 compras diretas no mesmo mês, departamento e categoria, cada uma abaixo do
    # limite e somadas acima dele
    for _ in range(8):
        f = next(escolhidos)
        departamento = f.departamentos[0]
        categoria = next((c for c in f.categorias if c not in CATEGORIAS_RECORRENTES), "Consultoria")
        mes = g.data_entre(date(2023, 1, 1), date(2025, 9, 30)).replace(day=1)
        for _ in range(rng.randint(3, 4)):
            g.pedido(f, mes + timedelta(days=rng.randint(0, 25)), LIMITE_COMPRA_DIRETA * rng.uniform(0.45, 0.8),
                     departamento=departamento, categoria=categoria, modalidade="compra_direta")
        g.plantar("R1", f"{f.cnpj}|{departamento}|{categoria}|{mes:%Y-%m}")

    # R2 pedido com fornecedor bloqueado
    bloqueados = [f for f in fornecedores if f.bloqueio and f.bloqueio[0] >= date(2023, 1, 1)]
    for f in rng.sample(bloqueados, min(6, len(bloqueados))):
        data = g.data_entre(f.bloqueio[0], min(f.bloqueio[1], FIM - timedelta(days=60)))
        g.plantar("R2", g.pedido(f, data, g.valor_normal(), modalidade="compra_direta"))

    # R3 concorrentes vinculados: duas empresas da mesma cotação com sócio, telefone ou e-mail em comum
    socios_por_cnpj = {}
    for cnpj, cpf, nome in g.linhas["socios"]:
        socios_por_cnpj.setdefault(cnpj, []).append((cpf, nome))
    cadastro = {linha[0]: list(linha) for linha in g.linhas["fornecedores"]}
    for vinculo in ("socio", "socio", "telefone", "telefone", "email", "socio"):
        a, b = next(escolhidos), next(escolhidos)
        if vinculo == "socio":
            cpf, nome = socios_por_cnpj[a.cnpj][0]
            g.linhas["socios"].append((b.cnpj, cpf, nome))
        else:
            coluna = 4 if vinculo == "telefone" else 6
            cadastro[b.cnpj][coluna] = cadastro[a.cnpj][coluna]
        data = g.data_entre(date(2023, 3, 1), date(2025, 9, 30))
        g.pedido(a, data, rng.uniform(30_000, 150_000), concorrentes=[b.cnpj, rng.choice(normais).cnpj])
        g.plantar("R3", g.linhas["cotacoes"][-1][0])
    g.linhas["fornecedores"] = [tuple(v) for v in cadastro.values()]

    # R4 conflito de interesse: funcionário é sócio de fornecedor que vende para o seu departamento
    for cpf, nome, departamento in rng.sample(funcionarios, 5):
        f = next(escolhidos)
        g.linhas["socios"].append((f.cnpj, cpf, nome))
        g.pedido(f, g.data_entre(date(2023, 2, 1), date(2025, 9, 30)), g.valor_normal(),
                 departamento=departamento, modalidade="compra_direta")
        g.plantar("R4", f"{cpf}|{f.cnpj}|{departamento}")

    # R5 pago acima do contratado e R7 pedido fora da vigência do contrato
    vigentes = [c for c in contratos if date(2023, 6, 1) <= c[5] <= date(2025, 6, 30)]
    amostra = rng.sample(vigentes, min(10, len(vigentes)))
    for id_contrato, f, departamento, valor, inicio, fim in amostra[:5]:
        g.pedido(f, g.data_entre(inicio, fim), valor * rng.uniform(0.6, 0.8), departamento=departamento,
                 modalidade="contrato", id_contrato=id_contrato)
        g.plantar("R5", id_contrato)
    for id_contrato, f, departamento, valor, inicio, fim in amostra[5:]:
        data = fim + timedelta(days=rng.randint(10, 90))
        g.plantar("R7", g.pedido(f, data, valor * 0.05, departamento=departamento,
                                 modalidade="contrato", id_contrato=id_contrato))

    # R6 pagamento em duplicidade: mesma nota fiscal e valor pagos de novo dias depois (fora de contratos,
    # para a duplicidade não se misturar com a R5)
    avulsos = {p[0] for p in g.linhas["pedidos"] if p[6] != "contrato"}
    candidatos = [p for p in g.linhas["pagamentos"] if p[3] >= "2023-01-01" and p[1] in avulsos]
    for id_pagamento, id_pedido, cnpj, data, valor, nota in rng.sample(candidatos, 6):
        repetido = date.fromisoformat(data) + timedelta(days=rng.randint(2, 10))
        g.plantar("R6", g.pagamento(id_pedido, cnpj, repetido, valor, nota_fiscal=nota))

    # R8 empresa recém-aberta e com capital incompatível com o volume vendido
    for i in range(5):
        primeiro = g.data_entre(date(2023, 3, 1), date(2025, 6, 30))
        f = g.novo_fornecedor(n_fornecedores + 1 + i, risco=False, capital=rng.choice((1_000.0, 2_000.0, 5_000.0)),
                              abertura=primeiro - timedelta(days=rng.randint(20, 75)))
        for k in range(3):
            g.pedido(f, primeiro + timedelta(days=20 * k), rng.uniform(60_000, 90_000),
                     concorrentes=rng.sample([n.cnpj for n in normais], 2))
        g.plantar("R8", f.cnpj)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Gera a base sintética de compras (SQLite)")
    parser.add_argument("--caminho", default=str(BANCO_EXEMPLO))
    parser.add_argument("--semente", type=int, default=42)
    parser.add_argument("--fornecedores", type=int, default=600)
    args = parser.parse_args(argv)
    contagem = gerar(args.caminho, args.semente, args.fornecedores)
    print(f"Base sintética gravada em {args.caminho}")
    for tabela, n in contagem.items():
        print(f"  {tabela:<20} {n:>7} linhas")


if __name__ == "__main__":
    main()
