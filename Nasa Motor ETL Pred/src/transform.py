"""Transformación: agrega RUL (ciclos restantes) y etiqueta de fallo inminente."""

from pathlib import Path

import pandas as pd

from src.config import CURATED_DIR, PROCESSED_DIR, RUL_THRESHOLD


def add_rul_pandas(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega columna 'rul' (ciclos restantes) y 'label' (fallo inminente)."""
    max_cycle = df.groupby("id")["cycle"].transform("max")
    df = df.copy()
    df["rul"] = (max_cycle - df["cycle"]).astype(int)
    df["label"] = (df["rul"] <= RUL_THRESHOLD).astype(int)
    return df


def transform_pandas(path_in: str | Path, path_out: str | Path | None = None) -> pd.DataFrame:
    """Lee Parquet procesado, aplica RUL y guarda en capa curated."""
    df = pd.read_parquet(path_in)
    df = add_rul_pandas(df)
    if path_out is None:
        path_out = CURATED_DIR / Path(path_in).name
    Path(path_out).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path_out, index=False)
    print(f"[transform] {len(df)} filas -> {path_out}")
    return df


def transform_spark(path_in: str, path_out: str) -> None:
    """Versión PySpark (escalable) del mismo proceso."""
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F

    spark = SparkSession.builder.appName("etl-predictivo").getOrCreate()
    df = spark.read.parquet(path_in)
    w = F.window("id")
    max_c = F.max("cycle").over(w)
    df = df.withColumn("rul", (max_c - F.col("cycle")).cast("int"))
    df = df.withColumn("label", (F.col("rul") <= RUL_THRESHOLD).cast("int"))
    df.write.mode("overwrite").parquet(path_out)
    print(f"[transform_spark] -> {path_out}")
    spark.stop()


if __name__ == "__main__":
    for pq in PROCESSED_DIR.glob("*.parquet"):
        transform_pandas(pq)
