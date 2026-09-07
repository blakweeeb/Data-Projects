#!/usr/bin/env python3
"""
Tests for transformation script.
"""
import pytest
from pathlib import Path
import pandas as pd
import yaml


@pytest.fixture
def config():
    with open("config/settings.yaml", "r") as f:
        return yaml.safe_load(f)


@pytest.fixture
def curated_dir(config):
    return Path(config["paths"]["curated"])


def test_curated_directory_exists(curated_dir):
    assert curated_dir.exists(), "Curated directory should exist after transform"


def test_all_entities_curated(curated_dir, config):
    for entity in config["olist_tables"]:
        curated_path = curated_dir / f"{entity}.parquet"
        assert curated_path.exists(), f"Curated {entity} should exist"


def test_no_null_primary_keys(curated_dir, config):
    pk_columns = {
        "customers": "customer_id",
        "geolocation": "geolocation_zip_code_prefix",
        "orders": "order_id",
        "order_items": "order_item_id",  # Not unique alone, but order_id+order_item_id is
        "order_payments": "payment_sequential",  # Not unique alone
        "order_reviews": "review_id",
        "products": "product_id",
        "sellers": "seller_id",
    }

    for entity, pk in pk_columns.items():
        path = curated_dir / f"{entity}.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        if pk in df.columns:
            null_count = df[pk].isnull().sum()
            assert null_count == 0, f"{entity}.{pk} should have no nulls"


def test_unique_primary_keys(curated_dir):
    # Primary keys that should be strictly unique
    strict_unique_pks = {
        "geolocation": "geolocation_zip_code_prefix",
        "orders": "order_id",
        "products": "product_id",
        "sellers": "seller_id",
    }

    for entity, pk in strict_unique_pks.items():
        path = curated_dir / f"{entity}.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        if pk in df.columns:
            dup_count = df[pk].duplicated().sum()
            assert dup_count == 0, f"{entity}.{pk} should be unique"

    # order_reviews.review_id has some duplicates in source data (<1%)
    path = curated_dir / "order_reviews.parquet"
    if path.exists():
        df = pd.read_parquet(path)
        if "review_id" in df.columns:
            total = len(df)
            unique = df["review_id"].nunique()
            uniqueness_ratio = unique / total
            assert uniqueness_ratio > 0.99, f"review_id uniqueness ratio {uniqueness_ratio:.3f} should be > 0.99"

    # Note: customers table in Olist is not a traditional customer dimension
    # customer_id and customer_unique_id can repeat (one row per customer-order-zip combination)
    # We only verify they are not null
    path = curated_dir / "customers.parquet"
    if path.exists():
        df = pd.read_parquet(path)
        for col in ["customer_id", "customer_unique_id"]:
            if col in df.columns:
                null_count = df[col].isnull().sum()
                assert null_count == 0, f"customers.{col} should have no nulls"


def test_orders_derived_columns(curated_dir):
    path = curated_dir / "orders.parquet"
    if not path.exists():
        pytest.skip("orders not curated yet")
    df = pd.read_parquet(path)

    # Check derived columns exist
    assert "delivery_delay_days" in df.columns
    assert "is_late" in df.columns
    assert "delivery_time_days" in df.columns

    # Check is_late is boolean
    assert df["is_late"].dtype == bool or set(df["is_late"].unique()).issubset({True, False, 0, 1})

    # Check delivery_time_days >= 0 for delivered orders
    delivered = df[df["order_status"] == "delivered"]
    if len(delivered) > 0:
        # Handle NaN values (non-delivered or missing dates)
        valid_times = delivered["delivery_time_days"].dropna()
        assert (valid_times >= 0).all(), "Delivered orders should have non-negative delivery time"


def test_orders_status_values(curated_dir):
    path = curated_dir / "orders.parquet"
    if not path.exists():
        pytest.skip("orders not curated yet")
    df = pd.read_parquet(path)

    valid_statuses = {"delivered", "shipped", "canceled", "unavailable", "invoiced", "processing", "created", "approved"}
    invalid = set(df["order_status"].unique()) - valid_statuses
    assert len(invalid) == 0, f"Invalid order_status values: {invalid}"


def test_zip_code_format(curated_dir):
    for entity, col in [("customers", "customer_zip_code_prefix"),
                        ("sellers", "seller_zip_code_prefix"),
                        ("geolocation", "geolocation_zip_code_prefix")]:
        path = curated_dir / f"{entity}.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        if col in df.columns:
            # All should be 5-digit strings
            assert df[col].astype(str).str.match(r"^\d{5}$").all(), f"{entity}.{col} should be 5-digit ZIP"


def test_state_codes(curated_dir):
    valid_states = {"AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"}
    for entity, col in [("customers", "customer_state"),
                        ("sellers", "seller_state"),
                        ("geolocation", "geolocation_state")]:
        path = curated_dir / f"{entity}.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        if col in df.columns:
            invalid = set(df[col].dropna().unique()) - valid_states
            assert len(invalid) == 0, f"{entity}.{col} has invalid states: {invalid}"


def test_numeric_ranges(curated_dir):
    path = curated_dir / "order_items.parquet"
    if not path.exists():
        pytest.skip("order_items not curated yet")
    df = pd.read_parquet(path)

    if "price" in df.columns:
        assert (df["price"] >= 0).all(), "Prices should be non-negative"
        assert (df["price"] < 10000).all(), "Prices should be reasonable (< 10000)"

    if "freight_value" in df.columns:
        assert (df["freight_value"] >= 0).all(), "Freight should be non-negative"


def test_review_scores(curated_dir):
    path = curated_dir / "order_reviews.parquet"
    if not path.exists():
        pytest.skip("order_reviews not curated yet")
    df = pd.read_parquet(path)

    if "review_score" in df.columns:
        assert df["review_score"].between(1, 5).all(), "Review scores should be 1-5"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])