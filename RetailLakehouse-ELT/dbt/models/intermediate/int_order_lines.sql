{# Linea de pedido enriquecida con las dimensiones de negocio.
   Es la tabla de hecho "atomica" sobre la que se construyen todos los marts. #}

with items as (

    select * from {{ ref('stg_order_items') }}

),

orders as (

    select * from {{ ref('stg_orders') }}

),

products as (

    select product_id, product_category_name_english from {{ ref('stg_products') }}

),

sellers as (

    select seller_id, seller_state, seller_city from {{ ref('stg_sellers') }}

),

customers as (

    select customer_id, customer_unique_id, customer_state, customer_city
    from {{ ref('stg_customers') }}

)

select
    i.order_id,
    i.order_item_id,
    i.product_id,
    i.seller_id,
    i.price,
    i.freight_value,
    i.price + i.freight_value                        as line_total,
    i.shipping_limit_date,
    o.order_status,
    o.order_purchase_timestamp,
    o.order_month_start,
    o.order_year,
    o.order_month,
    p.product_category_name_english,
    s.seller_state,
    s.seller_city,
    c.customer_unique_id,
    c.customer_state,
    c.customer_city
from items i
inner join orders o      on i.order_id  = o.order_id
left  join products p    on i.product_id = p.product_id
left  join sellers s     on i.seller_id  = s.seller_id
left  join customers c   on o.customer_id = c.customer_id
