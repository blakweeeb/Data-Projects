{# Cohortes de retencion: mes de alta del cliente vs meses posteriores de actividad. #}

with activity as (

    select distinct
        customer_unique_id,
        order_month_start
    from {{ ref('fct_orders') }}
    where customer_unique_id <> 'unknown'

),

cohort as (

    select
        customer_unique_id,
        min(order_month_start) as cohort_month
    from activity
    group by customer_unique_id

),

joined as (

    select
        c.cohort_month,
        a.order_month_start,
        date_diff('month', c.cohort_month, a.order_month_start) as month_index,
        a.customer_unique_id
    from activity a
    join cohort c on a.customer_unique_id = c.customer_unique_id

),

cohort_size as (

    select cohort_month, count(*) as cohort_customers
    from cohort
    group by cohort_month

)

select
    j.cohort_month,
    j.month_index,
    count(distinct j.customer_unique_id)                     as active_customers,
    max(s.cohort_customers)                                  as cohort_customers,
    round(
        count(distinct j.customer_unique_id) * 100.0 / max(s.cohort_customers), 2
    )                                                        as retention_pct
from joined j
join cohort_size s on j.cohort_month = s.cohort_month
group by j.cohort_month, j.month_index
order by j.cohort_month, j.month_index
