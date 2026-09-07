#!/usr/bin/env python
"""Extraccion (E) del pipeline ELT: PostgreSQL -> CSV en MinIO (zona staging).

Lee las tablas del esquema relacional de ventas con SQLAlchemy y las deposita en
`s3://staging/postgres/olist/<tabla>/ingest_date=<fecha>/` en formato CSV.

Caracteristicas pensadas para un entorno real:
  * Extraccion **incremental** por ventana temporal (fecha de ejecucion de Airflow).
  * Escritura por **chunks** para no agotar memoria en tablas grandes.
  * `manifest.json` con filas y bytes por tabla -> auditoria / cuadratura posterior.
  * Idempotente: reejecutar la misma fecha sobreescribe el mismo prefijo.

Uso:
    python extract_postgres_to_minio.py --run-date 2017-05-01
    python extract_postgres_to_minio.py --full-refresh
    python extract_postgres_to_minio.py --tables orders order_items
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import sys
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import boto3
import pandas as pd
from botocore.client import Config
from sqlalchemy import create_engine, text

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)-7s | %(message)s",
)
log = logging.getLogger("extract")

# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------
PG_URL = (
    "postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}".format(
        user=os.getenv("PG_USER", "olist"),
        password=os.getenv("PG_PASSWORD", "olist"),
        host=os.getenv("PG_HOST", "postgres-source"),
        port=os.getenv("PG_PORT", "5432"),
        db=os.getenv("PG_DATABASE", "olist"),
    )
)

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", os.getenv("S3_ENDPOINT", "http://minio:9000"))
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", os.getenv("AWS_ACCESS_KEY_ID", "minioadmin"))
MINIO_SECRET_KEY = os.getenv(
    "MINIO_ROOT_PASSWORD", os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")
)
STAGING_BUCKET = os.getenv("MINIO_STAGING_BUCKET", "staging")
STAGING_PREFIX = os.getenv("STAGING_PREFIX", "postgres/olist")
CHUNK_SIZE = int(os.getenv("EXTRACT_CHUNK_SIZE", "100000"))

# Tablas a extraer. `date_column` habilita la extraccion incremental por ventana.
TABLES: List[Dict[str, Any]] = [
    {"name": "customers", "date_column": None},
    {"name": "geolocation", "date_column": None},
    {"name": "order_items", "date_column": None},
    {"name": "order_payments", "date_column": None},
    # order_reviews se extrae completa siempre: la zona raw no esta particionada
    # para esta tabla y un overwrite incremental borraria el historico.
    {"name": "order_reviews", "date_column": None},
    {"name": "orders", "date_column": "order_purchase_timestamp"},
    {"name": "products", "date_column": None},
    {"name": "sellers", "date_column": None},
]


# ---------------------------------------------------------------------------
# Utilidades puras (cubiertas por tests unitarios en tests/test_extract.py)
# ---------------------------------------------------------------------------
def build_incremental_where(date_column: Optional[str], start: date, end: date) -> str:
    """Devuelve la clausula WHERE de una ventana [start, end).

    El rango es cerrado por la izquierda y abierto por la derecha para que dos
    ejecuciones consecutivas no dupliquen ni pierdan registros.
    """
    if not date_column:
        return ""
    return (
        f"WHERE {date_column} >= TIMESTAMP '{start.isoformat()} 00:00:00' "
        f"AND {date_column} < TIMESTAMP '{end.isoformat()} 00:00:00'"
    )


def build_extract_query(table: Dict[str, Any], start: date, end: date, full: bool = False) -> str:
    """Construye el SELECT de extraccion para una tabla."""
    where = "" if full else build_incremental_where(table.get("date_column"), start, end)
    return f"SELECT * FROM {table['name']} {where}".strip()


def staging_key(table: str, run_date: date, part: int = 0) -> str:
    """Ruta (key) del objeto CSV dentro del bucket de staging."""
    return f"{STAGING_PREFIX}/{table}/ingest_date={run_date.isoformat()}/{table}_{part:04d}.csv"


def manifest_key(run_date: date) -> str:
    return f"{STAGING_PREFIX}/_manifest/ingest_date={run_date.isoformat()}/manifest.json"


# ---------------------------------------------------------------------------
# Clientes
# ---------------------------------------------------------------------------
def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name=os.getenv("AWS_REGION", "us-east-1"),
    )


def get_engine():
    return create_engine(PG_URL, pool_pre_ping=True, isolation_level="AUTOCOMMIT")


def _put_csv(s3, key: str, df: pd.DataFrame) -> int:
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    payload = buffer.getvalue().encode("utf-8")
    s3.put_object(Bucket=STAGING_BUCKET, Key=key, Body=payload, ContentType="text/csv")
    return len(payload)


# ---------------------------------------------------------------------------
# Extraccion
# ---------------------------------------------------------------------------
def extract_table(
    s3, engine, table: Dict[str, Any], start: date, end: date, full: bool = False
) -> Dict[str, Any]:
    name = table["name"]
    query = build_extract_query(table, start, end, full)
    log.info("[%s] Extrayendo: %s", name, query)

    rows, bytes_written, parts = 0, 0, 0
    with engine.connect() as conn:
        for chunk_no, chunk in enumerate(
            pd.read_sql_query(text(query), conn, chunksize=CHUNK_SIZE)
        ):
            if chunk.empty:
                continue
            key = staging_key(name, start, part=chunk_no)
            bytes_written += _put_csv(s3, key, chunk)
            rows += len(chunk)
            parts += 1
            log.info("[%s]   -> s3://%s/%s (%s filas)", name, STAGING_BUCKET, key, len(chunk))

    if parts == 0:  # tabla sin filas en la ventana: escribimos cabecera vacia
        empty = pd.read_sql_query(text(f"SELECT * FROM {name} LIMIT 0"), engine.connect())
        key = staging_key(name, start, part=0)
        bytes_written += _put_csv(s3, key, empty)
        parts = 1
        log.warning("[%s]   sin filas en la ventana; se escribio solo cabecera", name)

    return {"table": name, "rows": rows, "parts": parts, "bytes": bytes_written, "query": query}


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extrae PostgreSQL -> CSV en MinIO")
    parser.add_argument(
        "--run-date",
        default=os.getenv("RUN_DATE", datetime.utcnow().date().isoformat()),
        help="Fecha logica de ejecucion (YYYY-MM-DD). Define la ventana incremental.",
    )
    parser.add_argument("--end-date", default=None, help="Fin de la ventana (YYYY-MM-DD).")
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Ignora la ventana y extrae la tabla completa.",
    )
    parser.add_argument("--tables", nargs="*", default=None, help="Subconjunto de tablas.")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    run_date = datetime.strptime(args.run_date, "%Y-%m-%d").date()
    end_date = (
        datetime.strptime(args.end_date, "%Y-%m-%d").date()
        if args.end_date
        else run_date + timedelta(days=1)
    )

    selected = TABLES
    if args.tables:
        selected = [t for t in TABLES if t["name"] in set(args.tables)]
        missing = set(args.tables) - {t["name"] for t in selected}
        if missing:
            log.error("Tablas desconocidas: %s", ", ".join(sorted(missing)))
            return 2

    log.info(
        "Extraccion hacia s3://%s/%s  ventana=[%s, %s)  full_refresh=%s",
        STAGING_BUCKET, STAGING_PREFIX, run_date, end_date, args.full_refresh,
    )

    s3 = get_s3_client()
    engine = get_engine()

    manifest: Dict[str, Any] = {
        "run_date": run_date.isoformat(),
        "window_start": run_date.isoformat(),
        "window_end": end_date.isoformat(),
        "full_refresh": args.full_refresh,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "tables": [],
    }

    for table in selected:
        try:
            manifest["tables"].append(
                extract_table(s3, engine, table, run_date, end_date, args.full_refresh)
            )
        except Exception as exc:  # noqa: BLE001 - queremos el detalle en los logs
            log.exception("Fallo extrayendo %s", table["name"])
            manifest["tables"].append({"table": table["name"], "error": str(exc), "rows": 0})
            raise

    _put_json(s3, manifest_key(run_date), manifest)
    log.info(
        "Extraccion finalizada: %s tablas, %s filas -> s3://%s/%s",
        len(manifest["tables"]),
        sum(t.get("rows", 0) for t in manifest["tables"]),
        STAGING_BUCKET,
        STAGING_PREFIX,
    )
    return 0


def _put_json(s3, key: str, payload: Dict[str, Any]) -> None:
    s3.put_object(
        Bucket=STAGING_BUCKET,
        Key=key,
        Body=json.dumps(payload, indent=2, default=str).encode("utf-8"),
        ContentType="application/json",
    )


if __name__ == "__main__":
    sys.exit(main())
