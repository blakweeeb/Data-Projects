with source as (

    select * from {{ source('raw', 'order_items') }}

)

select
    cast(order_id      as varchar)                    as order_id,
    cast(order_item_id as integer)                    as order_item_id,
    cast(product_id    as varchar)                    as product_id,
    cast(seller_id     as varchar)                    as seller_id,
    cast(shipping_limit_date as timestamp)            as shipping_limit_date,
    -- el precio nunca puede ser negativo: si llega sucio lo neutralizamos
    greatest(coalesce(cast(price         as double), 0), 0) as price,
    greatest(coalesce(cast(freight_value as double), 0), 0) as freight_value,
    cast(order_year    as integer)                    as order_year,
    cast(order_month   as integer)                    as order_month
from source
where order_id is not null
  and product_id is not null
