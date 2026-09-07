with source as (

    select * from {{ source('raw', 'customers') }}

)

select
    cast(customer_id              as varchar) as customer_id,
    cast(customer_unique_id       as varchar) as customer_unique_id,
    lpad(cast(customer_zip_code_prefix as varchar), 5, '0') as customer_zip_code_prefix,
    {{ title_case('customer_city') }}         as customer_city,
    upper(trim(customer_state))               as customer_state
from source
where customer_id is not null
