-- R4 Conflito de interesse
WITH ligados AS ({{dados:funcionarios_ligados:cnpj,cpf,nome_funcionario,departamento_funcionario,vinculo,peso}})
SELECT 'fornecedor'                                                     AS tipo_objeto,
       l.cpf || '|' || p.cnpj || '|' || p.departamento                  AS id_objeto,
       p.departamento                                                   AS departamento,
       p.cnpj                                                           AS cnpj_fornecedor,
       SUM(p.valor)                                                     AS valor_envolvido,
       CASE WHEN p.departamento = l.departamento_funcionario THEN l.peso
            ELSE l.peso * :peso_outro_departamento END                  AS pontuacao,
       '[' || CASE WHEN p.departamento = l.departamento_funcionario THEN 'mesmo departamento'
                   ELSE 'outro departamento' END || '] ' || l.nome_funcionario || ' ('
         || l.departamento_funcionario || ') ligado por ' || l.vinculo || '; ' || COUNT(*)
         || ' pedido(s) de ' || p.departamento                          AS evidencia
  FROM ligados l
  JOIN pedidos p ON p.cnpj = l.cnpj
 WHERE p.data >= :data_inicio
 GROUP BY l.cpf, l.nome_funcionario, l.departamento_funcionario, l.vinculo, l.peso, p.cnpj, p.departamento
