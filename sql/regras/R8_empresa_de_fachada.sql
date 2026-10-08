-- R8 Fornecedor recém-aberto ou com capital incompatível
-- Sinais de empresa sem capacidade operacional: primeiro pedido poucos meses depois da abertura e/ou
-- capital social muito pequeno perto do que vendeu no primeiro ano. Cada sinal soma 0,5 na nota.
WITH primeiro AS (
    SELECT p.cnpj, MIN(p.data) AS primeiro_pedido
      FROM pedidos p
     GROUP BY p.cnpj
), primeiro_ano AS (
    SELECT pr.cnpj, pr.primeiro_pedido, MIN(p.departamento) AS departamento, SUM(p.valor) AS valor_12m
      FROM primeiro pr
      JOIN pedidos p ON p.cnpj = pr.cnpj AND julianday(p.data) < julianday(pr.primeiro_pedido) + 365
     GROUP BY pr.cnpj, pr.primeiro_pedido
), sinais AS (
    SELECT a.*, f.data_abertura, f.capital_social,
           CASE WHEN (julianday(a.primeiro_pedido) - julianday(f.data_abertura)) / 30.44 < :meses_minimos
                THEN 1 ELSE 0 END                                                        AS recem_aberta,
           CASE WHEN f.capital_social < :fracao_capital * a.valor_12m THEN 1 ELSE 0 END  AS capital_baixo
      FROM primeiro_ano a
      JOIN fornecedores f ON f.cnpj = a.cnpj
)
SELECT 'fornecedor'                                                     AS tipo_objeto,
       s.cnpj                                                           AS id_objeto,
       s.departamento                                                   AS departamento,
       s.cnpj                                                           AS cnpj_fornecedor,
       s.valor_12m                                                      AS valor_envolvido,
       0.5 * s.recem_aberta + 0.5 * s.capital_baixo                     AS pontuacao,
       '[' || TRIM(CASE WHEN s.recem_aberta = 1 THEN 'recém-aberta ' ELSE '' END
                || CASE WHEN s.capital_baixo = 1 THEN 'capital baixo' ELSE '' END) || '] Aberta em '
         || s.data_abertura || ', primeiro pedido em ' || s.primeiro_pedido || '; capital R$ '
         || printf('%.2f', s.capital_social) || ' para R$ ' || printf('%.2f', s.valor_12m) || ' no primeiro ano'
                                                                        AS evidencia
  FROM sinais s
 WHERE (s.recem_aberta = 1 OR s.capital_baixo = 1)
   AND s.primeiro_pedido >= :data_inicio
