-- =====================================================================================
-- Consultas analiticas de ejemplo sobre el lakehouse (Trino)
-- Ejecutar con:  make trino-cli       y pegar las consultas
--          o:    docker compose exec -T trino trino --server localhost:8080 -f /ruta.sql
-- =====================================================================================

-- 0. Que hay en el catalogo ---------------------------------------------------------
SHOW SCHEMAS IN hive;
SHOW TABLES IN hive.lakehouse;
DESCRIBE hive.lakehouse.fct_orders;

-- 1. Cuadratura origen (PostgreSQL) vs lakehouse -------------------------------------
--    Trino consulta AMBOS orígenes en la misma query gracias al conector postgresql.
SELECT
    (SELECT count(*) FROM postgresql.public.orders)  AS filas_postgres,
    (SELECT count(*) FROM hive.lakehouse.fct_orders) AS filas_lakehouse;

-- 2. Ventas mensuales (KPI principal) -------------------------------------------------
SELECT
    date_format(order_month_start, '%Y-%m') AS mes,
    orders                                  AS pedidos,
    active_customers                        AS clientes_activos,
    revenue                                 AS ingreso,
    avg_order_value                         AS ticket_medio,
    delivered_pct                           AS pct_entregados,
    revenue_mom_pct                         AS var_mensual_pct
FROM hive.lakehouse.agg_sales_monthly
ORDER BY order_month_start;

-- 3. Top 10 categorias por ingreso historico ------------------------------------------
SELECT
    category,
    sum(revenue)          AS ingreso_total,
    sum(units)            AS unidades,
    round(avg(avg_price), 2) AS precio_medio
FROM hive.lakehouse.agg_category_monthly
GROUP BY category
ORDER BY ingreso_total DESC
LIMIT 10;

-- 4. Categoria lider por mes (window function) ----------------------------------------
SELECT mes, category, revenue
FROM (
    SELECT
        date_format(order_month_start, '%Y-%m') AS mes,
        category,
        revenue,
        row_number() OVER (PARTITION BY order_month_start ORDER BY revenue DESC) AS rn
    FROM hive.lakehouse.agg_category_monthly
) t
WHERE rn = 1
ORDER BY mes;

-- 5. Retencion por cohortes ------------------------------------------------------------
SELECT
    date_format(cohort_month, '%Y-%m') AS cohorte,
    month_index                        AS mes_n,
    active_customers,
    cohort_customers,
    retention_pct
FROM hive.lakehouse.customer_retention_cohorts
WHERE month_index <= 6
ORDER BY cohort_month, month_index;

-- 6. Ticket medio y satisfaccion por estado del cliente --------------------------------
SELECT
    customer_state,
    count(*)                                             AS pedidos,
    round(avg(order_value), 2)                           AS ticket_medio,
    round(avg(case when avg_review_score > 0 then avg_review_score end), 2) AS score_medio,
    round(avg(delivery_days), 1)                         AS dias_entrega
FROM hive.lakehouse.fct_orders
GROUP BY customer_state
ORDER BY pedidos DESC
LIMIT 10;

-- 7. Impacto del retraso en la entrega sobre la satisfaccion ---------------------------
SELECT
    is_delivered_on_time                                          AS entrego_a_tiempo,
    count(*)                                                      AS pedidos,
    round(avg(case when avg_review_score > 0 then avg_review_score end), 2) AS score_medio
FROM hive.lakehouse.fct_orders
WHERE is_delivered
GROUP BY 1
ORDER BY 1;

-- 8. Segmentacion de clientes por valor -------------------------------------------------
SELECT
    value_segment,
    count(*)                     AS clientes,
    round(avg(lifetime_value), 2) AS valor_medio,
    round(avg(lifetime_orders), 2) AS pedidos_medios
FROM hive.lakehouse.dim_customers
GROUP BY value_segment
ORDER BY valor_medio DESC;

-- 9. Particiones fisicas registradas en el metastore -------------------------------------
SELECT table_name, count(*) AS particiones
FROM hive.information_schema.partitions
WHERE table_schema = 'raw'
GROUP BY table_name
ORDER BY table_name;

-- 10. Tamaño real de los ficheros Parquet escritos por dbt --------------------------------
SELECT
    regexp_extract("$path", '.*/([^/]+)/[^/]+$', 1) AS modelo,
    count(*)                                        AS ficheros,
    round(sum("$file_size") / 1024.0 / 1024, 2)     AS mb
FROM hive.lakehouse.fct_orders
GROUP BY 1;

-- 11. Consulta directa a la zona raw (Parquet particionado) -------------------------------
SELECT order_year, order_month, count(*) AS pedidos
FROM hive.raw.orders
GROUP BY order_year, order_month
ORDER BY order_year, order_month;
