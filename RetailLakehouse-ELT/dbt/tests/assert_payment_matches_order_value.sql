{# Control financiero: el total pagado no deberia desviarse mas de 1% del valor
   del pedido (productos + flete). Detecta errores en la agregacion de pagos. #}

select
    order_id,
    order_value,
    payment_value,
    abs(payment_value - order_value)          as abs_diff,
    abs(payment_value - order_value) / nullif(order_value, 0) * 100 as diff_pct
from {{ ref('fct_orders') }}
where order_value > 0
  and abs(payment_value - order_value) / order_value > 0.01
