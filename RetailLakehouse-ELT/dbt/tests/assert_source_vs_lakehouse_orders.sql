{# Cuadratura origen <-> lakehouse.
   Trino expone la base relacional original con el catalogo `postgresql`, asi que
   podemos comparar en la misma consulta las filas de PostgreSQL y del lakehouse.
   Un test singular falla si devuelve filas. #}

with source_counts as (
    select count(*) as source_rows
    from postgresql.public.orders
),

lakehouse_counts as (
    select count(*) as lakehouse_rows
    from {{ ref('fct_orders') }}
)

select
    source_rows,
    lakehouse_rows,
    source_rows - lakehouse_rows as diff
from source_counts, lakehouse_counts
where source_rows <> lakehouse_rows
