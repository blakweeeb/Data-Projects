{# Un pedido puede pagarse con varios metodos: se consolidan a nivel de pedido. #}

with payments as (

    select * from {{ ref('stg_order_payments') }}

)

select
    order_id,
    sum(payment_value)                                          as payment_value,
    max(payment_installments)                                   as max_installments,
    count(*)                                                    as payment_methods,
    max(case when payment_type = 'credit_card' then 1 else 0 end) as paid_with_credit_card,
    max(case when payment_type = 'boleto'      then 1 else 0 end) as paid_with_boleto,
    max(case when payment_type = 'voucher'     then 1 else 0 end) as paid_with_voucher
from payments
group by order_id
