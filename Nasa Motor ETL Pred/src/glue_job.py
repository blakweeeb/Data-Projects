"""Template de AWS Glue Job (PySpark) para ejecutar el ETL en la nube."""

from __future__ import annotations

import sys

# Librerías solo disponibles en el entorno de AWS Glue
from awsglue.utils import getResolvedOptions  # type: ignore
from pyspark.context import SparkContext  # type: ignore
from awsglue.context import GlueContext  # type: ignore
from pyspark.sql import functions as F  # type: ignore

RUL_THRESHOLD = 30
COLUMNS = ["id", "cycle", "op1", "op2", "op3", *[f"s{i}" for i in range(1, 22)]]


def run_job(src: str, dst: str) -> None:
    sc = SparkContext()
    glue_ctx = GlueContext(sc)
    spark = glue_ctx.spark_session

    df = (
        spark.read.option("header", False)
        .option("sep", " ")
        .csv(src)
        .toDF(*COLUMNS)
    )

    w = F.window("id")
    max_c = F.max("cycle").over(w)
    df = df.withColumn("rul", (max_c - F.col("cycle")).cast("int"))
    df = df.withColumn("label", (F.col("rul") <= RUL_THRESHOLD).cast("int"))

    df.write.mode("overwrite").parquet(dst)
    print(f"Glue job completado: {src} -> {dst}")


def main() -> None:
    args = getResolvedOptions(sys.argv, ["JOB_NAME", "SRC", "DST"])
    run_job(args["SRC"], args["DST"])


if __name__ == "__main__":
    main()
