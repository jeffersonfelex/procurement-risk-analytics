-- R7 Pedido fora da vigência do contrato
SELECT 'pedido'                                                         AS tipo_objeto,
       p.id_pedido                                                      AS id_objeto,
       p.departamento                                                   AS departamento,
       p.cnpj                                                           AS cnpj_fornecedor,
       p.valor                                                          AS valor_envolvido,
       MIN(1.0, 0.5 + ABS(julianday(p.data) - julianday(
             CASE WHEN p.data > c.data_fim THEN c.data_fim ELSE c.data_inicio END)) / 180.0) AS pontuacao,
       '[' || CASE WHEN p.data > c.data_fim THEN 'após o fim' ELSE 'antes do início' END || '] Pedido de '
         || p.data || ' no contrato ' || c.id_contrato || ' (vigência ' || c.data_inicio || ' a '
         || c.data_fim || ')'                                           AS evidencia
  FROM pedidos p
  JOIN contratos c ON c.id_contrato = p.id_contrato
 WHERE p.data >= :data_inicio
   AND (p.data > c.data_fim OR p.data < c.data_inicio)
