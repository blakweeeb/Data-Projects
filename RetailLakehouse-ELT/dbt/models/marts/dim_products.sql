{# Dimension producto: atributos + rendimiento comercial. #}

with products as (

    select * from {{ ref('stg_products') }}

),

lines as (

    select * from {{ ref('int_order_lines') }}

),

agg as (

    select
        product_id,
        count(*)                                     as units_sold,
        count(distinct order_id)                     as orders_count,
        round(sum(line_total), 2)                    as total_revenue,
        round(avg(price), 2)                         as avg_price,
        round(avg(freight_value), 2)                 as avg_freight,
        round(avg(cast(date_diff('day', order_purchase_timestamp, shipping_limit_date) as double)), 2)
                                                     as avg_shipping_window_days
    from lines
    group by product_id

)

select
    p.product_id,
    p.product_category_name,
    p.product_category_name_english,
    p.product_name_length,
    p.product_description_length,
    p.product_photos_qty,
    p.product_weight_g,
    p.product_length_cm,
    p.product_height_cm,
    p.product_width_cm,
    coalesce(a.units_sold, 0)   as units_sold,
    coalesce(a.orders_count, 0) as orders_count,
    coalesce(a.total_revenue, 0) as total_revenue,
    a.avg_price,
    a.avg_freight,
    a.avg_shipping_window_days,
    case when coalesce(a.units_sold, 0) = 0 then 'sin ventas'
         when a.total_revenue >= 10000 then 'top'
         when a.total_revenue >= 2000  then 'medio'
         else 'cola larga'
    end                         as product_performance_segment
from products p
left join agg a on p.product_id = a.product_id
