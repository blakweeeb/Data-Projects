-- =====================================================================================
-- Registro del lakehouse en el Hive Metastore (ejecutado por el servicio `trino-init`)
--   hive.raw      -> tablas EXTERNAS sobre el Parquet escrito por Spark en MinIO
--   hive.staging  -> vistas de limpieza/tipado (dbt)
--   hive.lakehouse-> modelos analiticos (dbt, tablas gestionadas en formato Parquet)
-- =====================================================================================

-- --------------------------------------------------------------------------- ZONA RAW
CREATE SCHEMA IF NOT EXISTS hive.raw WITH (location = 's3://lake/raw/');

CREATE TABLE IF NOT EXISTS hive.raw.orders (
    order_id                       varchar,
    customer_id                    varchar,
    order_status                   varchar,
    order_purchase_timestamp       timestamp(3),
    order_approved_at              timestamp(3),
    order_delivered_carrier_date   timestamp(3),
    order_delivered_customer_date  timestamp(3),
    order_estimated_delivery_date  timestamp(3),
    order_year                     integer,
    order_month                    integer
) WITH (
    external_location = 's3://lake/raw/orders/',
    format = 'PARQUET',
    partitioned_by = ARRAY['order_year', 'order_month']
);

CREATE TABLE IF NOT EXISTS hive.raw.order_items (
    order_id            varchar,
    order_item_id       integer,
    product_id          varchar,
    seller_id           varchar,
    shipping_limit_date timestamp(3),
    price               double,
    freight_value       double,
    order_year          integer,
    order_month         integer
) WITH (
    external_location = 's3://lake/raw/order_items/',
    format = 'PARQUET',
    partitioned_by = ARRAY['order_year', 'order_month']
);

CREATE TABLE IF NOT EXISTS hive.raw.order_payments (
    order_id            varchar,
    payment_sequential  integer,
    payment_type        varchar,
    payment_installments integer,
    payment_value       double
) WITH (
    external_location = 's3://lake/raw/order_payments/',
    format = 'PARQUET'
);

CREATE TABLE IF NOT EXISTS hive.raw.order_reviews (
    review_id               varchar,
    order_id                varchar,
    review_score            integer,
    review_comment_title    varchar,
    review_comment_message  varchar,
    review_creation_date    timestamp(3),
    review_answer_timestamp timestamp(3)
) WITH (
    external_location = 's3://lake/raw/order_reviews/',
    format = 'PARQUET'
);

CREATE TABLE IF NOT EXISTS hive.raw.customers (
    customer_id              varchar,
    customer_unique_id       varchar,
    customer_zip_code_prefix varchar,
    customer_city            varchar,
    customer_state           varchar
) WITH (
    external_location = 's3://lake/raw/customers/',
    format = 'PARQUET'
);

CREATE TABLE IF NOT EXISTS hive.raw.products (
    product_id                  varchar,
    product_category_name       varchar,
    product_name_lenght         integer,
    product_description_lenght  integer,
    product_photos_qty          integer,
    product_weight_g            double,
    product_length_cm           double,
    product_height_cm           double,
    product_width_cm            double
) WITH (
    external_location = 's3://lake/raw/products/',
    format = 'PARQUET'
);

CREATE TABLE IF NOT EXISTS hive.raw.sellers (
    seller_id              varchar,
    seller_zip_code_prefix varchar,
    seller_city            varchar,
    seller_state           varchar
) WITH (
    external_location = 's3://lake/raw/sellers/',
    format = 'PARQUET'
);

CREATE TABLE IF NOT EXISTS hive.raw.geolocation (
    geolocation_zip_code_prefix varchar,
    geolocation_lat             double,
    geolocation_lng             double,
    geolocation_city            varchar,
    geolocation_state           varchar
) WITH (
    external_location = 's3://lake/raw/geolocation/',
    format = 'PARQUET'
);

-- ---------------------------------------------------------------------- ZONA STAGING
CREATE SCHEMA IF NOT EXISTS hive.staging WITH (location = 's3://lake/staging/');

-- ------------------------------------------------------------------------ ZONA MARTS
CREATE SCHEMA IF NOT EXISTS hive.lakehouse WITH (location = 's3://lake/lakehouse/');
