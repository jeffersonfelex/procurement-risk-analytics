-- R2 Pedido a fornecedor bloqueado
SELECT 'pedido'                                                AS tipo_objeto,
       p.id_pedido                                             AS id_objeto,
       p.departamento                                          AS departamento,
       p.cnpj                                                  AS cnpj_fornecedor,
       p.valor                                                 AS valor_envolvido,
       1.0                                                     AS pontuacao,
       '[bloqueio vigente] Pedido de ' || p.data || ' com fornecedor bloqueado de ' || b.data_inicio
         || ' a ' || COALESCE(b.data_fim, 'sem prazo') || ' (' || b.motivo || ')'
                                                               AS evidencia
  FROM pedidos p
  JOIN bloqueios b
    ON b.cnpj = p.cnpj
   AND p.data >= b.data_inicio
   AND (b.data_fim IS NULL OR p.data <= b.data_fim)
 WHERE p.data >= :data_inicio
