with source as (

    select * from {{ source('raw', 'products') }}

),

translation as (

    select * from {{ ref('product_category_name_translation') }}

)

select
    cast(p.product_id                 as varchar) as product_id,
    lower(trim(p.product_category_name))          as product_category_name,
    -- Si la categoria no esta en la tabla de traduccion nos quedamos con el
    -- nombre original en portugues; si ademas viene vacia, cae en 'unknown'
    -- (en el dataset real de Olist hay productos sin categoria).
    coalesce(
        lower(trim(t.product_category_name_english)),
        nullif(lower(trim(p.product_category_name)), ''),
        'unknown'
    )                                             as product_category_name_english,
    coalesce(cast(p.product_name_lenght        as integer), 0) as product_name_length,
    coalesce(cast(p.product_description_lenght as integer), 0) as product_description_length,
    coalesce(cast(p.product_photos_qty         as integer), 0) as product_photos_qty,
    cast(p.product_weight_g   as double)          as product_weight_g,
    cast(p.product_length_cm  as double)          as product_length_cm,
    cast(p.product_height_cm  as double)          as product_height_cm,
    cast(p.product_width_cm   as double)          as product_width_cm
from source p
left join translation t
       on lower(trim(p.product_category_name)) = lower(trim(t.product_category_name))
where p.product_id is not null
