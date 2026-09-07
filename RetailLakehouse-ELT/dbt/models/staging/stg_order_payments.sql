with source as (

    select * from {{ source('raw', 'order_payments') }}

)

select
    cast(order_id            as varchar) as order_id,
    cast(payment_sequential  as integer) as payment_sequential,
    lower(trim(payment_type))            as payment_type,
    coalesce(cast(payment_installments as integer), 0) as payment_installments,
    greatest(coalesce(cast(payment_value as double), 0), 0) as payment_value
from source
where order_id is not null
