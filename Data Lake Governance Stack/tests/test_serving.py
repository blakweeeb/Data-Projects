#!/usr/bin/env python3
"""
Tests for serving layer.
"""
import pytest
from pathlib import Path
import pandas as pd
import duckdb
import yaml


@pytest.fixture
def config():
    with open("config/settings.yaml", "r") as f:
        return yaml.safe_load(f)


@pytest.fixture
def serving_dir(config):
    return Path(config["paths"]["serving"])


@pytest.fixture
def curated_dir(config):
    return Path(config["paths"]["curated"])


@pytest.fixture
def duckdb_path(config):
    return Path(config["duckdb"]["path"])


def test_serving_directory_exists(serving_dir):
    assert serving_dir.exists(), "Serving directory should exist"


def test_fact_orders_exists(serving_dir):
    path = serving_dir / "fact_orders.parquet"
    assert path.exists(), "fact_orders should exist"
    df = pd.read_parquet(path)
    assert len(df) > 0, "fact_orders should have rows"


def test_fact_order_items_exists(serving_dir):
    path = serving_dir / "fact_order_items.parquet"
    assert path.exists(), "fact_order_items should exist"
    df = pd.read_parquet(path)
    assert len(df) > 0, "fact_order_items should have rows"


def test_dimension_tables_exist(serving_dir):
    dims = ["dim_customers", "dim_sellers", "dim_products", "dim_geolocation", "dim_date"]
    for dim in dims:
        path = serving_dir / f"{dim}.parquet"
        assert path.exists(), f"{dim} should exist"
        df = pd.read_parquet(path)
        assert len(df) > 0, f"{dim} should have rows"


def test_fact_orders_columns(serving_dir):
    path = serving_dir / "fact_orders.parquet"
    df = pd.read_parquet(path)
    
    required_cols = [
        "order_id", "customer_id", "order_status",
        "total_payment_value", "delivery_time_days", "is_late"
    ]
    for col in required_cols:
        assert col in df.columns, f"fact_orders missing column: {col}"


def test_row_count_reconciliation(serving_dir, curated_dir):
    """Verify fact table row counts match curated orders."""
    fact_path = serving_dir / "fact_orders.parquet"
    curated_path = curated_dir / "orders.parquet"
    
    if not fact_path.exists() or not curated_path.exists():
        pytest.skip("Files not ready")
    
    fact_count = len(pd.read_parquet(fact_path))
    curated_count = len(pd.read_parquet(curated_path))
    
    assert fact_count == curated_count, \
        f"Row count mismatch: fact_orders={fact_count}, curated orders={curated_count}"


def test_payment_value_reconciliation(serving_dir, curated_dir):
    """Verify total payment value matches."""
    fact_path = serving_dir / "fact_orders.parquet"
    payments_path = curated_dir / "order_payments.parquet"
    
    if not fact_path.exists() or not payments_path.exists():
        pytest.skip("Files not ready")
    
    fact_total = pd.read_parquet(fact_path)["total_payment_value"].sum()
    payments_total = pd.read_parquet(payments_path)["payment_value"].sum()
    
    assert abs(fact_total - payments_total) < 0.01, \
        f"Payment total mismatch: fact={fact_total:.2f}, payments={payments_total:.2f}"


def test_duckdb_database(duckdb_path):
    assert duckdb_path.exists(), "DuckDB database should exist"
    
    con = duckdb.connect(str(duckdb_path), read_only=True)
    tables = con.execute("SHOW TABLES").fetchall()
    table_names = [t[0] for t in tables]
    
    expected = ["fact_orders", "fact_order_items", "dim_customers", "dim_sellers", 
                "dim_products", "dim_geolocation", "dim_date"]
    for exp in expected:
        assert exp in table_names, f"DuckDB missing view: {exp}"
    
    # Verify data accessible
    for table in expected:
        count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert count > 0, f"DuckDB view {table} should have rows"
    
    con.close()


def test_duckdb_queries(duckdb_path):
    """Test analytical queries work."""
    con = duckdb.connect(str(duckdb_path), read_only=True)
    
    # GMV query
    gmv = con.execute("SELECT SUM(total_payment_value) FROM fact_orders").fetchone()[0]
    assert gmv is not None and gmv > 0
    
    # Orders per day
    daily = con.execute("""
        SELECT order_purchase_timestamp::DATE as dt, COUNT(*) as cnt
        FROM fact_orders
        GROUP BY 1
        ORDER BY 1
        LIMIT 10
    """).fetchall()
    assert len(daily) > 0
    
    # Join fact with dim
    joined = con.execute("""
        SELECT c.customer_state, COUNT(*) as orders
        FROM fact_orders f
        JOIN dim_customers c ON f.customer_id = c.customer_id
        GROUP BY 1
        ORDER BY 2 DESC
        LIMIT 5
    """).fetchall()
    assert len(joined) > 0
    
    con.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])