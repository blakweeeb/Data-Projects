{# Satisfaccion: puntuacion media y reseñas por pedido. #}

with reviews as (

    select * from {{ ref('stg_order_reviews') }}

)

select
    order_id,
    avg(cast(review_score as double))  as avg_review_score,
    min(cast(review_score as double))  as min_review_score,
    count(*)                           as review_count
from reviews
group by order_id
