{# Serie temporal de ventas mensuales: KPI principal del negocio. #}

with orders as (

    select * from {{ ref('fct_orders') }}

)

select
    order_month_start,
    count(*)                                              as orders,
    count(distinct customer_unique_id)                    as active_customers,
    sum(item_count)                                       as items_sold,
    round(sum(order_value), 2)                            as revenue,
    round(sum(freight_value), 2)                          as freight_revenue,
    round(avg(order_value), 2)                            as avg_order_value,
    round(sum(case when is_delivered then 1 else 0 end) * 100.0 / count(*), 2) as delivered_pct,
    round(avg(delivery_days), 2)                          as avg_delivery_days,
    round(avg(case when avg_review_score > 0 then avg_review_score end), 2) as avg_review_score,
    sum(case when is_canceled then 1 else 0 end)          as canceled_orders,
    -- variacion mensual del ingreso (MoM)
    round(
        (sum(order_value) - lag(sum(order_value)) over (order by order_month_start))
        / nullif(lag(sum(order_value)) over (order by order_month_start), 0) * 100, 2
    )                                                     as revenue_mom_pct
from orders
group by order_month_start
order by order_month_start
