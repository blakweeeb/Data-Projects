"""DAG de Airflow que orquesta el pipeline ETL de mantenimiento predictivo.

Levanta localmente con Docker (ver docker-compose.yml). Programado diariamente.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator

# Hacer visible la raíz del proyecto para importar el paquete src
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import CURATED_DIR, PROCESSED_DIR, RAW_DIR  # noqa: E402
from src.ingest import ingest  # noqa: E402
from src.transform import transform_pandas  # noqa: E402
from src.validate import assert_quality  # noqa: E402

import pandas as pd  # noqa: E402


def _ingest_all():
    for txt in sorted(RAW_DIR.glob("*.txt")):
        try:
            ingest(txt)
        except ValueError as e:
            print(f"[omitido] {e}")
            continue


def _transform_all():
    for pq in PROCESSED_DIR.glob("*.parquet"):
        transform_pandas(pq)


def _validate_all():
    for pq in CURATED_DIR.glob("*.parquet"):
        assert_quality(pd.read_parquet(pq))


def _create_tables():
    from src.warehouse import connect, run_ddl

    conn = connect()
    try:
        run_ddl(conn)
    finally:
        conn.close()


def _load_warehouse():
    from src.warehouse import load

    load()


def _cuadratura():
    from src.warehouse import cuadratura

    cuadratura()


with DAG(
    dag_id="etl_mantenimiento_predictivo",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["etl", "mecatronica", "predictivo", "redshift"],
    description="Pipeline batch de mantenimiento predictivo (NASA Turbofan) -> Warehouse",
) as dag:
    t_ingest = PythonOperator(task_id="ingest", python_callable=_ingest_all)
    t_transform = PythonOperator(task_id="transform", python_callable=_transform_all)
    t_validate = PythonOperator(task_id="validate", python_callable=_validate_all)
    t_create = PythonOperator(task_id="create_tables", python_callable=_create_tables)
    t_load = PythonOperator(task_id="load_warehouse", python_callable=_load_warehouse)
    t_cuadratura = PythonOperator(task_id="cuadratura", python_callable=_cuadratura)

    (
        t_ingest
        >> t_transform
        >> t_validate
        >> t_create
        >> t_load
        >> t_cuadratura
    )

