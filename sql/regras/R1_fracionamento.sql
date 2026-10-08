-- R1 Fracionamento de compra direta
-- Várias compras diretas do mesmo fornecedor, departamento e categoria no mesmo mês, cada uma abaixo
-- do limite que exige cotação, mas que somadas passam dele. Categorias recorrentes por natureza
-- (config/categorias_recorrentes.csv) ficam de fora.
SELECT 'grupo_de_pedidos'                                                    AS tipo_objeto,
       p.cnpj || '|' || p.departamento || '|' || p.categoria || '|' || substr(p.data, 1, 7) AS id_objeto,
       p.departamento                                                        AS departamento,
       p.cnpj                                                                AS cnpj_fornecedor,
       SUM(p.valor)                                                          AS valor_envolvido,
       MIN(1.0, 0.4 + 0.15 * COUNT(*) + 0.2 * (SUM(p.valor) / :limite_compra_direta - 1)) AS pontuacao,
       '[' || COUNT(*) || ' compras diretas] ' || p.categoria || ' em ' || substr(p.data, 1, 7)
         || ' somam R$ ' || printf('%.2f', SUM(p.valor)) || ' (limite R$ '
         || printf('%.2f', :limite_compra_direta) || ', maior pedido R$ ' || printf('%.2f', MAX(p.valor)) || ')'
                                                                             AS evidencia
  FROM pedidos p
 WHERE p.modalidade = 'compra_direta'
   AND p.data >= :data_inicio
   AND p.categoria NOT IN (SELECT categoria FROM ({{csv:categorias_recorrentes:categoria}}) AS recorrentes)
 GROUP BY p.cnpj, p.departamento, p.categoria, substr(p.data, 1, 7)
HAVING COUNT(*) >= :minimo_pedidos
   AND SUM(p.valor) > :limite_compra_direta
   AND MAX(p.valor) <= :limite_compra_direta
