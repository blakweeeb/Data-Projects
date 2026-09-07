#!/usr/bin/env python
"""Transformacion (L) del pipeline ELT: CSV en MinIO -> Parquet (Snappy) particionado.

Lee los CSV depositados por `extract/extract_postgres_to_minio.py` en la zona
staging y escribe la zona RAW del lakehouse como Parquet comprimido en Snappy,
particionado por anio/mes cuando la tabla tiene dimension temporal.

Buenas practicas aplicadas:
  * Esquema **declarado** (no inferido) -> evita sorpresas de tipos y escaneos extra.
  * Deduplicacion por clave primaria declarada en `TABLES`.
  * Escritura particionada + `partitionOverwriteMode=dynamic` -> reejecuciones
    idempotentes: solo se reescriben las particiones presentes en el lote.
  * Un Parquet por particion (coalesce) -> evita el problema de "small files".

Uso:
    spark-submit --master spark://spark-master:7077 \
        spark/jobs/raw_to_parquet.py --ingest-date 2017-05-01

    spark-submit ... spark/jobs/raw_to_parquet.py --tables orders customers --mode overwrite
"""

from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("raw_to_parquet")

STAGING_BUCKET = os.getenv("MINIO_STAGING_BUCKET", "staging")
LAKE_BUCKET = os.getenv("MINIO_LAKE_BUCKET", "lake")
STAGING_PREFIX = os.getenv("STAGING_PREFIX", "postgres/olist")
RAW_PREFIX = os.getenv("RAW_PREFIX", "raw")

S3_STAGING = f"s3a://{STAGING_BUCKET}/{STAGING_PREFIX}"
S3_RAW = f"s3a://{LAKE_BUCKET}/{RAW_PREFIX}"

# ---------------------------------------------------------------------------------
# Esquemas declarados (mismo dominio que el dataset publico de Olist)
# ---------------------------------------------------------------------------------
SCHEMAS: Dict[str, StructType] = {
    "customers": StructType([
        StructField("customer_id", StringType()),
        StructField("customer_unique_id", StringType()),
        StructField("customer_zip_code_prefix", StringType()),
        StructField("customer_city", StringType()),
        StructField("customer_state", StringType()),
    ]),
    "geolocation": StructType([
        StructField("geolocation_zip_code_prefix", StringType()),
        StructField("geolocation_lat", DoubleType()),
        StructField("geolocation_lng", DoubleType()),
        StructField("geolocation_city", StringType()),
        StructField("geolocation_state", StringType()),
    ]),
    "orders": StructType([
        StructField("order_id", StringType()),
        StructField("customer_id", StringType()),
        StructField("order_status", StringType()),
        StructField("order_purchase_timestamp", TimestampType()),
        StructField("order_approved_at", TimestampType()),
        StructField("order_delivered_carrier_date", TimestampType()),
        StructField("order_delivered_customer_date", TimestampType()),
        StructField("order_estimated_delivery_date", TimestampType()),
    ]),
    "order_items": StructType([
        StructField("order_id", StringType()),
        StructField("order_item_id", IntegerType()),
        StructField("product_id", StringType()),
        StructField("seller_id", StringType()),
        StructField("shipping_limit_date", TimestampType()),
        StructField("price", DoubleType()),
        StructField("freight_value", DoubleType()),
    ]),
    "order_payments": StructType([
        StructField("order_id", StringType()),
        StructField("payment_sequential", IntegerType()),
        StructField("payment_type", StringType()),
        StructField("payment_installments", IntegerType()),
        StructField("payment_value", DoubleType()),
    ]),
    "order_reviews": StructType([
        StructField("review_id", StringType()),
        StructField("order_id", StringType()),
        StructField("review_score", IntegerType()),
        StructField("review_comment_title", StringType()),
        StructField("review_comment_message", StringType()),
        StructField("review_creation_date", TimestampType()),
        StructField("review_answer_timestamp", TimestampType()),
    ]),
    "products": StructType([
        StructField("product_id", StringType()),
        StructField("product_category_name", StringType()),
        StructField("product_name_lenght", IntegerType()),
        StructField("product_description_lenght", IntegerType()),
        StructField("product_photos_qty", IntegerType()),
        StructField("product_weight_g", DoubleType()),
        StructField("product_length_cm", DoubleType()),
        StructField("product_height_cm", DoubleType()),
        StructField("product_width_cm", DoubleType()),
    ]),
    "sellers": StructType([
        StructField("seller_id", StringType()),
        StructField("seller_zip_code_prefix", StringType()),
        StructField("seller_city", StringType()),
        StructField("seller_state", StringType()),
    ]),
}

# primary key -> se usa para deduplicar;  partition_by -> columnas de particion
TABLES: Dict[str, Dict[str, List[str]]] = {
    "customers": {"pk": ["customer_id"], "partition_by": []},
    "geolocation": {
        "pk": ["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng"],
        "partition_by": [],
    },
    "orders": {"pk": ["order_id"], "partition_by": ["order_year", "order_month"]},
    "order_items": {
        "pk": ["order_id", "order_item_id"],
        "partition_by": ["order_year", "order_month"],
    },
    "order_payments": {"pk": ["order_id", "payment_sequential"], "partition_by": []},
    "order_reviews": {"pk": ["review_id"], "partition_by": []},
    "products": {"pk": ["product_id"], "partition_by": []},
    "sellers": {"pk": ["seller_id"], "partition_by": []},
}


def build_spark_session(app_name: str = "raw_to_parquet") -> SparkSession:
    return (
        SparkSession.builder.appName(app_name)
        .config("spark.sql.parquet.compression.codec", "snappy")
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )


def read_staging_csv(spark: SparkSession, table: str, ingest_date: str) -> DataFrame:
    path = f"{S3_STAGING}/{table}/ingest_date={ingest_date}/"
    log.info("Leyendo %s", path)
    return (
        spark.read.schema(SCHEMAS[table])
        .option("header", "true")
        .option("mode", "PERMISSIVE")
        .option("timestampFormat", "yyyy-MM-dd HH:mm:ss")
        .csv(path)
    )


def add_partition_columns(df: DataFrame, source_ts_col: str = "order_purchase_timestamp") -> DataFrame:
    return (
        df.withColumn("order_year", F.year(F.col(source_ts_col)))
        .withColumn("order_month", F.month(F.col(source_ts_col)))
    )


def dedupe(df: DataFrame, pk: List[str]) -> DataFrame:
    """Mantiene un unico registro por PK (el mas reciente segun el orden del CSV)."""
    if not pk:
        return df
    return df.dropDuplicates(subset=pk).dropna(subset=pk)


def attach_order_partitions(items: DataFrame, orders: DataFrame) -> DataFrame:
    """Propaga anio/mes del pedido a las lineas de pedido (dimension prestada)."""
    dims = orders.select(
        "order_id",
        F.col("order_year").alias("ord_year"),
        F.col("order_month").alias("ord_month"),
    ).dropDuplicates(subset=["order_id"])
    return (
        items.join(F.broadcast(dims), on="order_id", how="left")
        .withColumn("order_year", F.coalesce(F.col("ord_year"), F.lit(1900)))
        .withColumn("order_month", F.coalesce(F.col("ord_month"), F.lit(1)))
        .drop("ord_year", "ord_month")
    )


def write_parquet(df: DataFrame, table: str, partition_by: List[str], mode: str) -> None:
    target = f"{S3_RAW}/{table}/"
    writer = df.coalesce(1).write.mode(mode).format("parquet")
    if partition_by:
        writer = writer.partitionBy(*partition_by)
    log.info("Escribiendo %s -> %s (particiones: %s)", table, target, partition_by or "ninguna")
    writer.save(target)


def process_table(spark: SparkSession, table: str, ingest_date: str, mode: str, orders: Optional[DataFrame]) -> int:
    df = read_staging_csv(spark, table, ingest_date)

    if table == "orders":
        df = add_partition_columns(df)
    elif table == "order_items":
        if orders is None:
            orders = add_partition_columns(read_staging_csv(spark, "orders", ingest_date))
        df = attach_order_partitions(df, orders)

    df = dedupe(df, TABLES[table]["pk"])
    df = df.select(*[c for c in SCHEMAS[table].fieldNames() if c in df.columns]
                   + [c for c in TABLES[table]["partition_by"] if c in df.columns])

    count = df.count()
    write_parquet(df, table, TABLES[table]["partition_by"], mode)
    log.info("[%s] %s filas escritas en la zona raw", table, count)
    return count


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CSV staging -> Parquet lake (zona raw)")
    parser.add_argument(
        "--ingest-date",
        default=os.getenv("RUN_DATE", datetime.utcnow().date().isoformat()),
        help="Prefijo ingest_date=... escrito por la extraccion.",
    )
    parser.add_argument("--mode", default=os.getenv("WRITE_MODE", "overwrite"),
                        choices=["overwrite", "append"])
    parser.add_argument("--tables", nargs="*", default=list(TABLES.keys()))
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    spark = build_spark_session()
    spark.sparkContext.setLogLevel(os.getenv("SPARK_LOG_LEVEL", "WARN"))
    log.info("Inicio raw_to_parquet | ingest_date=%s | modo=%s", args.ingest_date, args.mode)

    # `orders` se procesa primero porque aporta la dimension temporal a order_items
    ordered = [t for t in ["orders", "order_items"] if t in args.tables] + [
        t for t in args.tables if t not in ("orders", "order_items")
    ]
    orders_df = None
    for table in ordered:
        if table == "orders":
            orders_df = add_partition_columns(read_staging_csv(spark, "orders", args.ingest_date))
            orders_df = dedupe(orders_df, TABLES["orders"]["pk"])
            write_parquet(orders_df, "orders", TABLES["orders"]["partition_by"], args.mode)
            log.info("[orders] %s filas escritas en la zona raw", orders_df.count())
        else:
            process_table(spark, table, args.ingest_date, args.mode, orders_df)

    log.info("raw_to_parquet finalizado")
    spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
