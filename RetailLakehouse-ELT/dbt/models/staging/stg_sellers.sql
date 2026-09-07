with source as (

    select * from {{ source('raw', 'sellers') }}

)

select
    cast(seller_id              as varchar) as seller_id,
    lpad(cast(seller_zip_code_prefix as varchar), 5, '0') as seller_zip_code_prefix,
    {{ title_case('seller_city') }}         as seller_city,
    upper(trim(seller_state))               as seller_state
from source
where seller_id is not null
