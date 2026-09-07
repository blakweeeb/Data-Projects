#!/usr/bin/env python3
"""Build serving layer (star schema) from curated data. Creates fact/dim tables for DuckDB/Superset."""
import sys
from pathlib import Path

import duckdb
import pandas as pd
import yaml
from tqdm import tqdm


def load_config():
    with open("config/settings.yaml", "r") as f:
        return yaml.safe_load(f)


def build_serving():
    config = load_config()
    curated_dir = Path(config["paths"]["curated"])
    serving_dir = Path(config["paths"]["serving"])
    duckdb_path = Path(config["duckdb"]["path"])
    serving_dir.mkdir(parents=True, exist_ok=True)
    print("Building serving layer (star schema)...")
    tables = {}
    for entity in config["olist_tables"]:
        path = curated_dir / f"{entity}.parquet"
        if path.exists():
            tables[entity] = pd.read_parquet(path)
            print(f"  {entity}: {len(tables[entity]):,} rows")
    # Dimension tables
    print("\nBuilding dimension tables...")
    if "customers" in tables:
        dim_customers = tables["customers"][["customer_id", "customer_unique_id",
                                             "customer_zip_code_prefix", "customer_city", "customer_state"]].copy()
        dim_customers.to_parquet(serving_dir / "dim_customers.parquet", index=False)
        print(f"  dim_customers: {len(dim_customers):,} rows")
    if "sellers" in tables:
        dim_sellers = tables["sellers"][["seller_id", "seller_zip_code_prefix",
                                         "seller_city", "seller_state"]].copy()
        dim_sellers.to_parquet(serving_dir / "dim_sellers.parquet", index=False)
        print(f"  dim_sellers: {len(dim_sellers):,} rows")
    if "products" in tables and "product_category_name_translation" in tables:
        products = tables["products"].merge(tables["product_category_name_translation"], on="product_category_name", how="left")
        dim_products = products[["product_id", "product_category_name",
                                "product_category_name_english", "product_weight_g",
                                "product_length_cm", "product_height_cm", "product_width_cm"]].copy()
        dim_products.to_parquet(serving_dir / "dim_products.parquet", index=False)
        print(f"  dim_products: {len(dim_products):,} rows")
    if "geolocation" in tables:
        dim_geo = tables["geolocation"][["geolocation_zip_code_prefix",
                                       "geolocation_lat", "geolocation_lng",
                                       "geolocation_city", "geolocation_state"]].copy()
        dim_geo = dim_geo.drop_duplicates(subset=["geolocation_zip_code_prefix"])
        dim_geo.to_parquet(serving_dir / "dim_geolocation.parquet", index=False)
        print(f"  dim_geolocation: {len(dim_geo):,} rows")
    if "orders" in tables:
        orders = tables["orders"]
        dates = pd.DataFrame({"date": pd.date_range(orders["order_purchase_timestamp"].min(),
                                                     orders["order_purchase_timestamp"].max(), freq="D")})
        dates["year"] = dates["date"].dt.year
        dates["month"] = dates["date"].dt.month
        dates["day"] = dates["date"].dt.day
        dates["day_of_week"] = dates["date"].dt.dayofweek
        dates["day_name"] = dates["date"].dt.day_name()
        dates["month_name"] = dates["date"].dt.month_name()
        dates["quarter"] = dates["date"].dt.quarter
        dates["is_weekend"] = dates["day_of_week"] >= 5
        dates.to_parquet(serving_dir / "dim_date.parquet", index=False)
        print(f"  dim_date: {len(dates):,} rows")
    # Fact tables
    print("\nBuilding fact tables...")
    if "orders" in tables and "order_items" in tables and "order_payments" in tables and "order_reviews" in tables:
        orders = tables["orders"].copy()
        items = tables["order_items"].copy()
        payments = tables["order_payments"].copy()
        reviews = tables["order_reviews"].copy()
        items_agg = items.groupby("order_id").agg(item_count=("order_item_id", "count"),
                                                  total_price=("price", "sum"),
                                                  total_freight=("freight_value", "sum"),
                                                  unique_sellers=("seller_id", "nunique"),
                                                  unique_categories=("product_id", lambda x: x.nunique())).reset_index()
        payments_agg = payments.groupby("order_id").agg(payment_count=("payment_sequential", "count"),
                                                        total_payment_value=("payment_value", "sum"),
                                                        payment_types=("payment_type", lambda x: ",".join(x.unique()))).reset_index()
        reviews_agg = reviews.groupby("order_id").agg(review_count=("review_id", "count"),
                                                    avg_review_score=("review_score", "mean"),
                                                    max_review_score=("review_score", "max")).reset_index()
        fact = orders.merge(items_agg, on="order_id", how="left") \
                      .merge(payments_agg, on="order_id", how="left") \
                      .merge(reviews_agg, on="order_id", how="left")
        fact["order_date_key"] = fact["order_purchase_timestamp"].dt.strftime("%Y%m%d").astype(int)
        fact["delivery_date_key"] = pd.to_numeric(fact["order_delivered_customer_date"].dt.strftime("%Y%m%d"), errors="coerce").astype("Int64")
        fact_cols = ["order_id", "customer_id", "order_status", "order_purchase_timestamp",
                     "order_approved_at", "order_delivered_carrier_date", "order_delivered_customer_date",
                     "order_estimated_delivery_date", "order_date_key", "delivery_date_key",
                     "item_count", "total_price", "total_freight", "unique_sellers",
                     "payment_count", "total_payment_value", "payment_types",
                     "review_count", "avg_review_score", "max_review_score",
                     "delivery_delay_days", "is_late", "delivery_time_days"]
        fact = fact[fact_cols]
        fact.to_parquet(serving_dir / "fact_orders.parquet", index=False)
        print(f"  fact_orders: {len(fact):,} rows")
    if "order_items" in tables and "products" in tables:
        items = tables["order_items"].merge(tables["products"][["product_id", "product_category_name"]], on="product_id", how="left")
        if "product_category_name_translation" in tables:
            items = items.merge(tables["product_category_name_translation"], on="product_category_name", how="left")
        items["order_date_key"] = items["shipping_limit_date"].dt.strftime("%Y%m%d").astype(int)
        items.to_parquet(serving_dir / "fact_order_items.parquet", index=False)
        print(f"  fact_order_items: {len(items):,} rows")
    print(f"\nCreating DuckDB database at {duckdb_path}...")
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(duckdb_path))
    for parquet_file in serving_dir.glob("*.parquet"):
        view_name = parquet_file.stem
        con.execute(f"CREATE OR REPLACE VIEW {view_name} AS SELECT * FROM read_parquet('{parquet_file}')")
        count = con.execute(f"SELECT COUNT(*) FROM {view_name}").fetchone()[0]
        print(f"  View {view_name}: {count:,} rows")
    con.close()
    print(f"\nServing layer complete. Data location: {serving_dir}")
    print(f"DuckDB database: {duckdb_path}")


if __name__ == "__main__":
    build_serving()