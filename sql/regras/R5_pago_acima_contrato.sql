-- R5 Pago acima do valor do contrato
SELECT 'contrato'                                                       AS tipo_objeto,
       c.id_contrato                                                    AS id_objeto,
       c.departamento                                                   AS departamento,
       c.cnpj                                                           AS cnpj_fornecedor,
       SUM(pg.valor)                                                    AS valor_envolvido,
       MIN(1.0, 0.5 + 2 * (SUM(pg.valor) / c.valor - 1 - :tolerancia))  AS pontuacao,
       '[' || printf('%.0f', 100 * (SUM(pg.valor) / c.valor - 1)) || '% acima] Pago R$ '
         || printf('%.2f', SUM(pg.valor)) || ' contra R$ ' || printf('%.2f', c.valor)
         || ' contratados (vigência ' || c.data_inicio || ' a ' || c.data_fim || ')'
                                                                        AS evidencia
  FROM contratos c
  JOIN pedidos p     ON p.id_contrato = c.id_contrato
  JOIN pagamentos pg ON pg.id_pedido = p.id_pedido
 WHERE c.data_fim >= :data_inicio
 GROUP BY c.id_contrato, c.departamento, c.cnpj, c.valor, c.data_inicio, c.data_fim
HAVING SUM(pg.valor) > c.valor * (1 + :tolerancia)
