"""Tests unitarios de la capa de extraccion.

Se ejecutan sin Docker y sin las dependencias del pipeline: las librerias que el
script usa en tiempo de ejecucion se sustituyen por mocks cuando no estan
instaladas, porque aqui solo nos interesa validar la logica pura.

    pytest tests/ -v
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

MODULE_PATH = Path(__file__).resolve().parents[1] / "extract" / "extract_postgres_to_minio.py"


def _load_module():
    for name in ("pandas", "boto3", "botocore", "botocore.client", "sqlalchemy"):
        if name not in sys.modules:
            sys.modules[name] = MagicMock()
    spec = importlib.util.spec_from_file_location("extract_postgres_to_minio", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


extract = _load_module()


def test_incremental_where_is_half_open():
    where = extract.build_incremental_where("order_purchase_timestamp", date(2017, 5, 1), date(2017, 5, 2))
    assert "order_purchase_timestamp >= TIMESTAMP '2017-05-01 00:00:00'" in where
    assert "order_purchase_timestamp < TIMESTAMP '2017-05-02 00:00:00'" in where


def test_no_date_column_means_full_extract():
    assert extract.build_incremental_where(None, date(2017, 5, 1), date(2017, 5, 2)) == ""


def test_build_extract_query_full_refresh_has_no_filter():
    table = {"name": "orders", "date_column": "order_purchase_timestamp"}
    query = extract.build_extract_query(table, date(2017, 5, 1), date(2017, 5, 2), full=True)
    assert query == "SELECT * FROM orders"


def test_build_extract_query_incremental():
    table = {"name": "orders", "date_column": "order_purchase_timestamp"}
    query = extract.build_extract_query(table, date(2017, 5, 1), date(2017, 5, 2))
    assert query.startswith("SELECT * FROM orders WHERE")
    assert "2017-05-01" in query


def test_staging_key_layout():
    key = extract.staging_key("orders", date(2017, 5, 1), part=3)
    assert key.endswith("orders_0003.csv")
    assert "ingest_date=2017-05-01" in key


def test_manifest_key_layout():
    assert extract.manifest_key(date(2017, 5, 1)).endswith("manifest.json")


def test_every_table_has_a_schema_counterpart_in_spark():
    """Las tablas declaradas en extract y en el job Spark deben coincidir."""
    spark_job = (Path(__file__).resolve().parents[1] / "spark" / "jobs" / "raw_to_parquet.py").read_text(
        encoding="utf-8"
    )
    for table in extract.TABLES:
        assert f'"{table["name"]}"' in spark_job, f"{table['name']} no esta en el job de Spark"
