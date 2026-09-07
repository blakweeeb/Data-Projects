#!/usr/bin/env python
"""Carga inicial del OLTP: crea el esquema de ventas en PostgreSQL y pobla las
tablas desde los CSV de data/raw/ (dataset Olist real o sintetico).

    python scripts/seed_postgres.py --data-dir data/raw
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import psycopg2

DDL = """
DROP TABLE IF EXISTS order_items, order_payments, order_reviews, orders,
                     customers, products, sellers, geolocation CASCADE;

CREATE TABLE geolocation (
    geolocation_zip_code_prefix VARCHAR(10),
    geolocation_lat             DOUBLE PRECISION,
    geolocation_lng             DOUBLE PRECISION,
    geolocation_city            VARCHAR(120),
    geolocation_state           VARCHAR(5)
);

CREATE TABLE customers (
    customer_id              VARCHAR(40) PRIMARY KEY,
    customer_unique_id       VARCHAR(40),
    customer_zip_code_prefix VARCHAR(10),
    customer_city            VARCHAR(120),
    customer_state           VARCHAR(5)
);

CREATE TABLE sellers (
    seller_id              VARCHAR(40) PRIMARY KEY,
    seller_zip_code_prefix VARCHAR(10),
    seller_city            VARCHAR(120),
    seller_state           VARCHAR(5)
);

CREATE TABLE products (
    product_id                 VARCHAR(40) PRIMARY KEY,
    product_category_name      VARCHAR(80),
    product_name_lenght        INTEGER,
    product_description_lenght INTEGER,
    product_photos_qty         INTEGER,
    product_weight_g           DOUBLE PRECISION,
    product_length_cm          DOUBLE PRECISION,
    product_height_cm          DOUBLE PRECISION,
    product_width_cm           DOUBLE PRECISION
);

CREATE TABLE orders (
    order_id                      VARCHAR(40) PRIMARY KEY,
    customer_id                   VARCHAR(40) REFERENCES customers(customer_id),
    order_status                  VARCHAR(20),
    order_purchase_timestamp      TIMESTAMP,
    order_approved_at             TIMESTAMP,
    order_delivered_carrier_date  TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP
);

CREATE TABLE order_items (
    order_id           VARCHAR(40) REFERENCES orders(order_id),
    order_item_id      INTEGER,
    product_id         VARCHAR(40) REFERENCES products(product_id),
    seller_id          VARCHAR(40) REFERENCES sellers(seller_id),
    shipping_limit_date TIMESTAMP,
    price              NUMERIC(12,2),
    freight_value      NUMERIC(12,2),
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE order_payments (
    order_id            VARCHAR(40) REFERENCES orders(order_id),
    payment_sequential  INTEGER,
    payment_type        VARCHAR(30),
    payment_installments INTEGER,
    payment_value       NUMERIC(12,2),
    PRIMARY KEY (order_id, payment_sequential)
);

CREATE TABLE order_reviews (
    review_id               VARCHAR(40) PRIMARY KEY,
    order_id                VARCHAR(40) REFERENCES orders(order_id),
    review_score            INTEGER,
    review_comment_title    VARCHAR(120),
    review_comment_message  TEXT,
    review_creation_date    TIMESTAMP,
    review_answer_timestamp TIMESTAMP
);

CREATE INDEX idx_orders_purchase_ts ON orders (order_purchase_timestamp);
CREATE INDEX idx_order_items_order  ON order_items (order_id);
"""

# Orden de carga respetando las FK
LOAD_ORDER = [
    ("geolocation", "geolocation.csv"),
    ("customers", "customers.csv"),
    ("sellers", "sellers.csv"),
    ("products", "products.csv"),
    ("orders", "orders.csv"),
    ("order_items", "order_items.csv"),
    ("order_payments", "order_payments.csv"),
    ("order_reviews", "order_reviews.csv"),
]


def connect():
    return psycopg2.connect(
        host=os.getenv("PG_HOST", "postgres-source"),
        port=os.getenv("PG_PORT", "5432"),
        dbname=os.getenv("PG_DATABASE", "olist"),
        user=os.getenv("PG_USER", "olist"),
        password=os.getenv("PG_PASSWORD", "olist"),
    )


def load_csv(cur, table: str, csv_path: Path) -> int:
    with csv_path.open("r", encoding="utf-8") as fh:
        cur.copy_expert(
            f"COPY {table} FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')", fh
        )
    cur.execute(f"SELECT count(*) FROM {table}")
    return cur.fetchone()[0]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Carga los CSV en PostgreSQL")
    parser.add_argument("--data-dir", default="data/raw")
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    missing = [f for _, f in LOAD_ORDER if not (data_dir / f).exists()]
    if missing:
        print(f"Faltan CSV en {data_dir}: {', '.join(missing)}")
        print("Ejecuta primero: python scripts/generate_sample_data.py")
        return 2

    # PostgreSQL puede tardar unos segundos en aceptar conexiones
    for attempt in range(30):
        try:
            conn = connect()
            break
        except Exception as exc:  # noqa: BLE001
            print(f"[{attempt + 1}/30] Esperando a PostgreSQL: {exc}")
            time.sleep(2)
    else:
        print("No se pudo conectar a PostgreSQL")
        return 1

    with conn:
        with conn.cursor() as cur:
            print("Creando esquema de ventas...")
            cur.execute(DDL)
            for table, filename in LOAD_ORDER:
                rows = load_csv(cur, table, data_dir / filename)
                print(f"  {table:<15} {rows:>8,} filas cargadas")

    conn.close()
    print("\nPostgreSQL listo con los datos de origen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
