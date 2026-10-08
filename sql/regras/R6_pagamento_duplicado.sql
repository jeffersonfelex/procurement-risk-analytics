-- R6 Pagamento em duplicidade
-- Segundo pagamento ao mesmo fornecedor, com o mesmo valor e a mesma nota fiscal (ou do mesmo pedido),
-- poucos dias depois do primeiro. O alerta aponta o pagamento repetido (o mais recente).
SELECT 'pagamento'                                                      AS tipo_objeto,
       b.id_pagamento                                                   AS id_objeto,
       p.departamento                                                   AS departamento,
       b.cnpj                                                           AS cnpj_fornecedor,
       b.valor                                                          AS valor_envolvido,
       CASE WHEN a.nota_fiscal = b.nota_fiscal THEN 1.0 ELSE 0.7 END    AS pontuacao,
       '[' || CASE WHEN a.nota_fiscal = b.nota_fiscal THEN 'mesma nota fiscal' ELSE 'mesmo pedido' END
         || '] ' || b.id_pagamento || ' em ' || b.data || ' repete ' || a.id_pagamento || ' de ' || a.data
         || ' (R$ ' || printf('%.2f', b.valor) || ', nota ' || b.nota_fiscal || ')'
                                                                        AS evidencia
  FROM pagamentos a
  JOIN pagamentos b
    ON b.cnpj = a.cnpj
   AND b.id_pagamento > a.id_pagamento
   AND ABS(b.valor - a.valor) < 0.01
   AND julianday(b.data) - julianday(a.data) BETWEEN 0 AND :janela_dias
   AND (b.nota_fiscal = a.nota_fiscal OR b.id_pedido = a.id_pedido)
  JOIN pedidos p ON p.id_pedido = b.id_pedido
 WHERE b.data >= :data_inicio
