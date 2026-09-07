with source as (

    select * from {{ source('raw', 'order_reviews') }}

)

select
    cast(review_id               as varchar)   as review_id,
    cast(order_id                as varchar)   as order_id,
    cast(review_score            as integer)   as review_score,
    cast(review_comment_title    as varchar)   as review_comment_title,
    cast(review_comment_message  as varchar)   as review_comment_message,
    cast(review_creation_date    as timestamp) as review_creation_date,
    cast(review_answer_timestamp as timestamp) as review_answer_timestamp
from source
where review_id is not null
