{# Dimension cliente: perfil + comportamiento historico de compra.

   GRANO: 1 fila por `customer_unique_id` (= persona).
   En Olist `customer_id` es una clave por pedido: la misma persona tiene varios
   `customer_id`. Si la dimension se construyera a grano `customer_id`, las
   metricas de vida (lifetime_value) saldrian repetidas y cualquier BI las
   duplicaria al sumarlas, asi que primero se colapsa la persona. #}

with customers as (

    select * from {{ ref('stg_customers') }}

),

persons as (

    select
        customer_unique_id,
        count(distinct customer_id)   as order_identities,
        max(customer_zip_code_prefix) as customer_zip_code_prefix,
        max(customer_city)            as customer_city,
        max(customer_state)           as customer_state
    from customers
    group by customer_unique_id

),

orders as (

    select * from {{ ref('fct_orders') }}
    where customer_unique_id <> 'unknown'

),

agg as (

    select
        customer_unique_id,
        count(*)                                    as lifetime_orders,
        sum(case when is_delivered then 1 else 0 end) as delivered_orders,
        round(sum(order_value), 2)                  as lifetime_value,
        round(avg(order_value), 2)                  as avg_order_value,
        round(avg(cast(delivery_days as double)), 2) as avg_delivery_days,
        round(avg(case when avg_review_score > 0 then avg_review_score end), 2) as avg_review_score,
        min(order_date)                             as first_order_date,
        max(order_date)                             as last_order_date
    from orders
    group by customer_unique_id

)

select
    p.customer_unique_id,
    p.order_identities,
    p.customer_zip_code_prefix,
    p.customer_city,
    p.customer_state,
    coalesce(a.lifetime_orders, 0)     as lifetime_orders,
    coalesce(a.delivered_orders, 0)    as delivered_orders,
    coalesce(a.lifetime_value, 0)      as lifetime_value,
    coalesce(a.avg_order_value, 0)     as avg_order_value,
    a.avg_delivery_days,
    a.avg_review_score,
    a.first_order_date,
    a.last_order_date,
    date_diff('day', a.last_order_date, current_date) as days_since_last_order,
    case
        when a.lifetime_value is null then 'sin compras'
        when a.lifetime_value >= 500 then 'alto valor'
        when a.lifetime_value >= 150 then 'valor medio'
        else 'valor bajo'
    end                                as value_segment
from persons p
left join agg a on p.customer_unique_id = a.customer_unique_id
