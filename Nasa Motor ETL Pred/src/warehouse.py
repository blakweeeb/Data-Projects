"""Carga datos curated en Postgres (stand-in de Redshift) con modelo dimensional."""

from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path

import pandas as pd
import psycopg2

from src.config import CURATED_DIR

DEFAULTS = dict(
    host=os.getenv("WAREHOUSE_HOST", "localhost"),
    port=int(os.getenv("WAREHOUSE_PORT", "5433")),
    user=os.getenv("WAREHOUSE_USER", "warehouse"),
    password=os.getenv("WAREHOUSE_PASSWORD", "warehouse"),
    dbname=os.getenv("WAREHOUSE_DB", "warehouse"),
)

DDL = """
CREATE TABLE IF NOT EXISTS dim_motor (
    motor_id INTEGER,
    scenario  VARCHAR(8),
    PRIMARY KEY (motor_id, scenario)
);

CREATE TABLE IF NOT EXISTS fact_lecturas (
    motor_id INTEGER,
    cycle    INTEGER,
    scenario VARCHAR(8),
    op1 FLOAT, op2 FLOAT, op3 FLOAT,
    s1 FLOAT, s2 FLOAT, s3 FLOAT, s4 FLOAT, s5 FLOAT,
    s6 FLOAT, s7 FLOAT, s8 FLOAT, s9 FLOAT, s10 FLOAT,
    s11 FLOAT, s12 FLOAT, s13 FLOAT, s14 FLOAT, s15 FLOAT,
    s16 FLOAT, s17 FLOAT, s18 FLOAT, s19 FLOAT, s20 FLOAT, s21 FLOAT,
    rul INTEGER,
    label INTEGER,
    rul_predicho FLOAT,
    error FLOAT
);
"""

FACT_COLS = [
    "motor_id", "cycle", "scenario", "op1", "op2", "op3",
    *[f"s{i}" for i in range(1, 22)],
    "rul", "label", "rul_predicho", "error",
]


def connect(params: dict | None = None) -> psycopg2.extensions.connection:
    return psycopg2.connect(**(params or DEFAULTS))


def run_ddl(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(DDL)
    conn.commit()


def _copy_csv(conn, table: str, cols, csv_path: str) -> None:
    with conn.cursor() as cur, open(csv_path, "r", newline="") as f:
        cur.copy_expert(
            f"COPY {table} ({', '.join(cols)}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)",
            f,
        )
    conn.commit()


def load(parquet_path: Path = CURATED_DIR / "dashboard_data.parquet",
         params: dict | None = None) -> None:
    df = pd.read_parquet(parquet_path)
    conn = connect(params)
    try:
        run_ddl(conn)
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE fact_lecturas, dim_motor")
        conn.commit()
        df = df.rename(columns={"id": "motor_id"})
        dim = df[["motor_id", "scenario"]].drop_duplicates()
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as f:
            dim.to_csv(f.name, index=False)
            _copy_csv(conn, "dim_motor", ["motor_id", "scenario"], f.name)
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as f:
            df[FACT_COLS].to_csv(f.name, index=False)
            _copy_csv(conn, "fact_lecturas", FACT_COLS, f.name)
    finally:
        conn.close()
    print(f"[warehouse] cargadas {len(df)} filas en fact_lecturas")


def check_cuadratura(src_count: int, wh_count: int) -> bool:
    if src_count != wh_count:
        raise AssertionError(
            f"Cuadratura fallida: warehouse={wh_count} != source={src_count}"
        )
    return True


def cuadratura(parquet_path: Path = CURATED_DIR / "dashboard_data.parquet",
               params: dict | None = None):
    df = pd.read_parquet(parquet_path)
    conn = connect(params)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM fact_lecturas")
            wh = cur.fetchone()[0]
    finally:
        conn.close()
    src = len(df)
    check_cuadratura(src, wh)
    print(f"[warehouse] cuadratura OK: {wh} filas")
    return wh, src


if __name__ == "__main__":
    load()
    cuadratura()
