{# Ingreso mensual por categoria + ranking y cuota de mercado mensual. #}

with lines as (

    select * from {{ ref('int_order_lines') }}

),

agg as (

    select
        order_month_start,
        product_category_name_english                     as category,
        count(distinct order_id)                          as orders,
        count(*)                                          as units,
        round(sum(line_total), 2)                         as revenue,
        round(sum(freight_value), 2)                      as freight_revenue,
        round(avg(price), 2)                              as avg_price
    from lines
    group by order_month_start, product_category_name_english

)

select
    order_month_start,
    category,
    orders,
    units,
    revenue,
    freight_revenue,
    avg_price,
    rank() over (partition by order_month_start order by revenue desc) as revenue_rank,
    round(revenue * 100.0 / sum(revenue) over (partition by order_month_start), 2) as revenue_share_pct
from agg
