-- R3 Concorrentes vinculados na mesma cotação
WITH pares AS ({{dados:pares_vinculados:cnpj_a,cnpj_b,tipos,peso}})
SELECT 'cotacao'                                                        AS tipo_objeto,
       c.id_cotacao                                                     AS id_objeto,
       c.departamento                                                   AS departamento,
       pa.cnpj                                                          AS cnpj_fornecedor,
       MAX(pa.valor, pb.valor)                                          AS valor_envolvido,
       pares.peso                                                       AS pontuacao,
       '[' || pares.tipos || '] Vínculo com ' || pb.cnpj || ' na cotação ' || c.id_cotacao
         || CASE WHEN pa.vencedora = 1 OR pb.vencedora = 1 THEN ', vencida por uma das duas' ELSE '' END
                                                                        AS evidencia
  FROM pares
  JOIN propostas pa ON pa.cnpj = pares.cnpj_a
  JOIN propostas pb ON pb.cnpj = pares.cnpj_b AND pb.id_cotacao = pa.id_cotacao
  JOIN cotacoes c   ON c.id_cotacao = pa.id_cotacao
 WHERE c.data >= :data_inicio
