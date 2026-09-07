with source as (

    select * from {{ source('raw', 'orders') }}

),

typed as (

    select
        cast(order_id                      as varchar)   as order_id,
        cast(customer_id                   as varchar)   as customer_id,
        lower(trim(order_status))                        as order_status,
        cast(order_purchase_timestamp      as timestamp) as order_purchase_timestamp,
        cast(order_approved_at             as timestamp) as order_approved_at,
        cast(order_delivered_carrier_date  as timestamp) as order_delivered_carrier_date,
        cast(order_delivered_customer_date as timestamp) as order_delivered_customer_date,
        cast(order_estimated_delivery_date as timestamp) as order_estimated_delivery_date,
        cast(order_year                    as integer)   as order_year,
        cast(order_month                   as integer)   as order_month
    from source
    where order_id is not null

)

select
    order_id,
    customer_id,
    order_status,
    order_purchase_timestamp,
    order_approved_at,
    order_delivered_carrier_date,
    order_delivered_customer_date,
    order_estimated_delivery_date,
    order_year,
    order_month,
    cast(order_purchase_timestamp as date)        as order_date,
    date_trunc('month', order_purchase_timestamp) as order_month_start,
    -- ¿se entrego dentro de la fecha prometida?
    case
        when order_delivered_customer_date is null then null
        when order_delivered_customer_date <= order_estimated_delivery_date then true
        else false
    end                                            as is_delivered_on_time,
    date_diff(
        'day', order_purchase_timestamp, order_delivered_customer_date
    )                                              as delivery_days
from typed
