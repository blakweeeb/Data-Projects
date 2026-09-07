# Data Dictionary - Olist E-commerce Data Lake

## Raw Layer (01_raw/)
Partitioned by year/month where applicable.

### customers
| Column | Type | Description | Quality Rules |
|--------|------|-------------|---------------|
| customer_id | string | Unique customer identifier (PK) | NOT NULL, UNIQUE |
| customer_unique_id | string | Unique customer ID across orders | NOT NULL |
| customer_zip_code_prefix | string | ZIP code prefix (5 digits) | NOT NULL, REGEX ^\d{5}$ |
| customer_city | string | City name | - |
| customer_state | string | State code (2 letters) | IN SET (BR states) |

### geolocation
| Column | Type | Description | Quality Rules |
|--------|------|-------------|---------------|
| geolocation_zip_code_prefix | string | ZIP code prefix (5 digits) | NOT NULL, UNIQUE, REGEX ^\d{5}$ |
| geolocation_lat | float | Latitude | BETWEEN -33.75 AND 5.27 |
| geolocation_lng | float | Longitude | BETWEEN -73.99 AND -34.79 |
| geolocation_city | string | City name | - |
| geolocation_state | string | State code | IN SET (BR states) |

### orders
| Column | Type | Description | Quality Rules |
|--------|------|-------------|---------------|
| order_id | string | Unique order identifier (PK) | NOT NULL, UNIQUE |
| customer_id | string | Customer FK | NOT NULL |
| order_status | string | Order status | IN SET (delivered, shipped, canceled, unavailable, invoiced, processing, created) |
| order_purchase_timestamp | timestamp | Purchase timestamp | BETWEEN 2016-01-01 AND 2018-12-31 |
| order_approved_at | timestamp | Approval timestamp | - |
| order_delivered_carrier_date | timestamp | Carrier delivery date | - |
| order_delivered_customer_date | timestamp | Customer delivery date | - |
| order_estimated_delivery_date | timestamp | Estimated delivery date | - |
| delivery_delay_days | float | Delay vs estimated (days) | BETWEEN -30 AND 60 (mostly) |
| is_late | boolean | Late delivery flag | - |
| delivery_time_days | float | Total delivery time (days) | BETWEEN 0 AND 60 (mostly) |

### order_items
| Column | Type | Description | Quality Rules |
|--------|------|-------------|---------------|
| order_id | string | Order FK | NOT NULL |
| order_item_id | int | Item sequence in order | NOT NULL |
| product_id | string | Product FK | NOT NULL |
| seller_id | string | Seller FK | NOT NULL |
| shipping_limit_date | timestamp | Shipping deadline | BETWEEN 2016-01-01 AND 2019-12-31 |
| price | float | Item price | BETWEEN 0 AND 10000 (mostly) |
| freight_value | float | Shipping cost | BETWEEN 0 AND 2000 (mostly) |
| product_category_name | string | Category (Portuguese) | - |
| product_category_name_english | string | Category (English) | - |

### order_payments
| Column | Type | Description | Quality Rules |
|--------|------|-------------|---------------|
| order_id | string | Order FK | NOT NULL |
| payment_sequential | int | Payment sequence | NOT NULL |
| payment_type | string | Payment method | IN SET (credit_card, boleto, voucher, debit_card, not_defined) |
| payment_installments | int | Number of installments | BETWEEN 1 AND 24 |
| payment_value | float | Payment amount | BETWEEN 0 AND 15000 |

### order_reviews
| Column | Type | Description | Quality Rules |
|--------|------|-------------|---------------|
| review_id | string | Unique review ID (PK) | NOT NULL, UNIQUE |
| order_id | string | Order FK | NOT NULL |
| review_score | int | Score 1-5 | BETWEEN 1 AND 5 |
| review_comment_title | string | Review title | - |
| review_comment_message | string | Review message | - |
| review_creation_date | timestamp | Creation date | BETWEEN 2016-01-01 AND 2019-12-31 |
| review_answer_timestamp | timestamp | Answer timestamp | - |

### products
| Column | Type | Description | Quality Rules |
|--------|------|-------------|---------------|
| product_id | string | Unique product ID (PK) | NOT NULL, UNIQUE |
| product_category_name | string | Category (Portuguese) | NOT NULL |
| product_weight_g | float | Weight in grams | BETWEEN 0 AND 50000 (mostly) |
| product_length_cm | float | Length in cm | BETWEEN 0 AND 200 (mostly) |
| product_height_cm | float | Height in cm | BETWEEN 0 AND 200 (mostly) |
| product_width_cm | float | Width in cm | BETWEEN 0 AND 200 (mostly) |
| product_category_name_english | string | Category (English) | - |

### sellers
| Column | Type | Description | Quality Rules |
|--------|------|-------------|---------------|
| seller_id | string | Unique seller ID (PK) | NOT NULL, UNIQUE |
| seller_zip_code_prefix | string | ZIP code prefix (5 digits) | REGEX ^\d{5}$ |
| seller_city | string | City name | - |
| seller_state | string | State code | IN SET (BR states) |

## Curated Layer (02_curated/)
Same schema as raw but cleaned, typed, and enriched.

## Serving Layer (03_serving/) - Star Schema

### fact_orders
| Column | Type | Description |
|--------|------|-------------|
| order_id | string | PK |
| customer_id | string | FK → dim_customers |
| order_status | string | Status |
| order_purchase_timestamp | timestamp | Purchase time |
| order_approved_at | timestamp | Approval time |
| order_delivered_carrier_date | timestamp | Carrier delivery |
| order_delivered_customer_date | timestamp | Customer delivery |
| order_estimated_delivery_date | timestamp | Estimated delivery |
| order_date_key | int | FK → dim_date (YYYYMMDD) |
| delivery_date_key | int | FK → dim_date (YYYYMMDD) |
| item_count | int | Number of items |
| total_price | float | Sum of item prices |
| total_freight | float | Sum of freight |
| unique_sellers | int | Distinct sellers |
| payment_count | int | Number of payments |
| total_payment_value | float | Total paid |
| payment_types | string | Comma-separated payment types |
| review_count | int | Number of reviews |
| avg_review_score | float | Average score |
| max_review_score | int | Max score |
| delivery_delay_days | float | Delay vs estimate |
| is_late | boolean | Late flag |
| delivery_time_days | float | Total delivery time |

### fact_order_items
| Column | Type | Description |
|--------|------|-------------|
| order_id | string | FK → fact_orders |
| order_item_id | int | Item sequence |
| product_id | string | FK → dim_products |
| seller_id | string | FK → dim_sellers |
| shipping_limit_date | timestamp | Shipping deadline |
| price | float | Item price |
| freight_value | float | Shipping cost |
| product_category_name | string | Category (PT) |
| product_category_name_english | string | Category (EN) |
| order_date_key | int | FK → dim_date |

### dim_customers
| Column | Type | Description |
|--------|------|-------------|
| customer_id | string | PK |
| customer_unique_id | string | Unique customer |
| customer_zip_code_prefix | string | ZIP prefix |
| customer_city | string | City |
| customer_state | string | State |

### dim_sellers
| Column | Type | Description |
|--------|------|-------------|
| seller_id | string | PK |
| seller_zip_code_prefix | string | ZIP prefix |
| seller_city | string | City |
| seller_state | string | State |

### dim_products
| Column | Type | Description |
|--------|------|-------------|
| product_id | string | PK |
| product_category_name | string | Category (PT) |
| product_category_name_english | string | Category (EN) |
| product_weight_g | float | Weight |
| product_length_cm | float | Length |
| product_height_cm | float | Height |
| product_width_cm | float | Width |

### dim_geolocation
| Column | Type | Description |
|--------|------|-------------|
| geolocation_zip_code_prefix | string | PK |
| geolocation_lat | float | Latitude |
| geolocation_lng | float | Longitude |
| geolocation_city | string | City |
| geolocation_state | string | State |

### dim_date
| Column | Type | Description |
|--------|------|-------------|
| date | date | PK |
| year | int | Year |
| month | int | Month |
| day | int | Day |
| day_of_week | int | 0-6 |
| day_name | string | Day name |
| month_name | string | Month name |
| quarter | int | Quarter |
| is_weekend | boolean | Weekend flag |