with source as (

    select * from {{ source('raw', 'geolocation') }}

),

deduped as (

    -- El origen trae varias filas por codigo postal; nos quedamos con el centroide.
    select
        lpad(cast(geolocation_zip_code_prefix as varchar), 5, '0') as geolocation_zip_code_prefix,
        cast(geolocation_lat as double)  as geolocation_lat,
        cast(geolocation_lng as double)  as geolocation_lng,
        {{ title_case('geolocation_city') }}  as geolocation_city,
        upper(trim(geolocation_state))   as geolocation_state,
        row_number() over (
            partition by cast(geolocation_zip_code_prefix as varchar)
            order by geolocation_lat
        ) as rn
    from source

)

select
    geolocation_zip_code_prefix,
    geolocation_lat,
    geolocation_lng,
    geolocation_city,
    geolocation_state
from deduped
where rn = 1
