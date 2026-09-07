#!/usr/bin/env python3
"""Transform raw Parquet to curated layer: cleaning, type casting, enrichment."""
import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import yaml
from tqdm import tqdm


def load_config():
    with open("config/settings.yaml", "r") as f:
        return yaml.safe_load(f)


def clean_customers(df):
    df = df.copy()
    df["customer_zip_code_prefix"] = df["customer_zip_code_prefix"].astype(str).str.zfill(5)
    df["customer_city"] = df["customer_city"].str.title().str.strip()
    df["customer_state"] = df["customer_state"].str.upper().str.strip()
    return df


def clean_geolocation(df):
    df = df.copy()
    df["geolocation_zip_code_prefix"] = df["geolocation_zip_code_prefix"].astype(str).str.zfill(5)
    df["geolocation_city"] = df["geolocation_city"].str.title().str.strip()
    df["geolocation_state"] = df["geolocation_state"].str.upper().str.strip()
    df = df.drop_duplicates(subset=["geolocation_zip_code_prefix"], keep="first")
    return df


def clean_orders(df):
    df = df.copy()
    date_cols = ["order_purchase_timestamp", "order_approved_at",
                 "order_delivered_carrier_date", "order_delivered_customer_date",
                 "order_estimated_delivery_date"]
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    df["order_status"] = df["order_status"].str.lower().str.strip()
    df["delivery_delay_days"] = (df["order_delivered_customer_date"] - df["order_estimated_delivery_date"]).dt.total_seconds() / 86400
    df["is_late"] = df["delivery_delay_days"] > 0
    df["delivery_time_days"] = (df["order_delivered_customer_date"] - df["order_purchase_timestamp"]).dt.total_seconds() / 86400
    df["delivery_time_days"] = df["delivery_time_days"].clip(lower=0)
    return df


def clean_order_items(df):
    df = df.copy()
    df["shipping_limit_date"] = pd.to_datetime(df["shipping_limit_date"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["freight_value"] = pd.to_numeric(df["freight_value"], errors="coerce")
    return df


def clean_order_payments(df):
    df = df.copy()
    df["payment_installments"] = pd.to_numeric(df["payment_installments"], errors="coerce")
    df["payment_value"] = pd.to_numeric(df["payment_value"], errors="coerce")
    df["payment_type"] = df["payment_type"].str.lower().str.strip()
    return df


def clean_order_reviews(df):
    df = df.copy()
    df["review_score"] = pd.to_numeric(df["review_score"], errors="coerce")
    df["review_creation_date"] = pd.to_datetime(df["review_creation_date"], errors="coerce")
    df["review_answer_timestamp"] = pd.to_datetime(df["review_answer_timestamp"], errors="coerce")
    return df


def clean_products(df):
    df = df.copy()
    df["product_category_name"] = df["product_category_name"].fillna("unknown")
    numeric_cols = ["product_weight_g", "product_length_cm", "product_height_cm",
                    "product_width_cm", "product_photos_qty"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def clean_sellers(df):
    df = df.copy()
    df["seller_zip_code_prefix"] = df["seller_zip_code_prefix"].astype(str).str.zfill(5)
    df["seller_city"] = df["seller_city"].str.title().str.strip()
    df["seller_state"] = df["seller_state"].str.upper().str.strip()
    return df


def clean_category_translation(df):
    df = df.copy()
    df.columns = ["product_category_name", "product_category_name_english"]
    return df


CLEANERS = {
    "customers": clean_customers,
    "geolocation": clean_geolocation,
    "orders": clean_orders,
    "order_items": clean_order_items,
    "order_payments": clean_order_payments,
    "order_reviews": clean_order_reviews,
    "products": clean_products,
    "sellers": clean_sellers,
    "product_category_name_translation": clean_category_translation,
}


def main():
    config = load_config()
    raw_dir = Path(config["paths"]["raw"])
    curated_dir = Path(config["paths"]["curated"])
    curated_dir.mkdir(parents=True, exist_ok=True)
    print("Transforming raw data to curated layer...")
    for entity_dir in tqdm(list(raw_dir.iterdir()), desc="Processing entities"):
        if not entity_dir.is_dir():
            continue
        entity = entity_dir.name
        if entity not in config["olist_tables"]:
            continue
        print(f"\nProcessing {entity}...")
        df = pd.read_parquet(entity_dir)
        cleaner = CLEANERS.get(entity)
        if cleaner:
            df = cleaner(df)
        else:
            print(f"  WARNING: No cleaner defined for {entity}")
        df = df.dropna(axis=1, how="all")
        df.to_parquet(curated_dir / f"{entity}.parquet", index=False, compression="snappy")
        print(f"  -> Written {len(df):,} rows to {curated_dir / f'{entity}.parquet'}")
    print(f"\nTransformation complete. Curated data location: {curated_dir}")


if __name__ == "__main__":
    main()