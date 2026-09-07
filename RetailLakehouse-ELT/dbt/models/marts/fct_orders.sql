{# Tabla de hecho de pedidos. Grano: 1 fila por pedido.
   Materializada como tabla Parquet gestionada en s3a://lake/lakehouse/fct_orders #}

with orders as (

    select * from {{ ref('stg_orders') }}

),

lines as (

    select
        order_id,
        count(*)                  as item_count,
        sum(price)                as items_value,
        sum(freight_value)        as freight_value,
        sum(line_total)           as order_value,
        max(customer_unique_id)   as customer_unique_id,
        max(customer_state)       as customer_state,
        max(product_category_name_english) as top_category
    from {{ ref('int_order_lines') }}
    group by order_id

),

payments as (

    select * from {{ ref('int_order_payments_agg') }}

),

reviews as (

    select * from {{ ref('int_order_reviews_agg') }}

)

select
    o.order_id,
    o.customer_id,
    coalesce(l.customer_unique_id, 'unknown')        as customer_unique_id,
    o.order_status,
    o.order_purchase_timestamp,
    o.order_date,
    o.order_month_start,
    o.order_year,
    o.order_month,
    o.is_delivered_on_time,
    o.delivery_days,
    coalesce(l.item_count, 0)                        as item_count,
    round(coalesce(l.items_value, 0), 2)             as items_value,
    round(coalesce(l.freight_value, 0), 2)           as freight_value,
    round(coalesce(l.order_value, 0), 2)             as order_value,
    round(coalesce(p.payment_value, 0), 2)           as payment_value,
    coalesce(p.max_installments, 0)                  as max_installments,
    coalesce(p.payment_methods, 0)                   as payment_methods,
    l.top_category,
    l.customer_state,
    round(coalesce(r.avg_review_score, 0), 2)        as avg_review_score,
    coalesce(r.review_count, 0)                      as review_count,
    case when o.order_status = 'delivered' then true else false end as is_delivered,
    case when o.order_status = 'canceled'  then true else false end as is_canceled
from orders o
left join lines l    on o.order_id = l.order_id
left join payments p on o.order_id = p.order_id
left join reviews r  on o.order_id = r.order_id
