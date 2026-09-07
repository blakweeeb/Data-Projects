"""=====================================================================================
DAG: retail_lakehouse_elt
=====================================================================================
Migracion ELT de una base relacional (PostgreSQL) a un data lakehouse abierto
(Parquet + Hive Metastore + Trino), con dbt para las transformaciones.

Flujo:
    1. extract_postgres_to_minio   PostgreSQL -> CSV en MinIO  (zona staging)
    2. spark_csv_to_parquet        CSV        -> Parquet Snappy particionado (zona raw)
    3. sync_raw_partitions         registra las particiones en el Hive Metastore
    4. dbt_seed / dbt_run          modelos de staging/intermediate/marts
    5. dbt_test                    tests de calidad (not_null, unique, relationships...)
    6. dbt_docs_generate           documentacion -> http://localhost:8080

Todo es idempotente: se puede relanzar cuantas veces haga falta.
====================================================================================="""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.utils.trigger_rule import TriggerRule

# ---------------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------------
PROJECT_DIR = os.getenv("AIRFLOW_HOME", "/opt/airflow")
DBT_DIR = f"{PROJECT_DIR}/dbt"
EXTRACT_SCRIPT = f"{PROJECT_DIR}/extract/extract_postgres_to_minio.py"
SPARK_JOB = f"{PROJECT_DIR}/spark/jobs/raw_to_parquet.py"

# Tablas de la zona raw que estan particionadas por anio/mes
PARTITIONED_RAW_TABLES = ["orders", "order_items"]

SPARK_PACKAGES = (
    "org.apache.hadoop:hadoop-aws:3.3.4,"
    "com.amazonaws:aws-java-sdk-bundle:1.12.262"
)

default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "execution_timeout": timedelta(hours=1),
}


def sync_raw_partitions(**_) -> None:
    """Registra en el Hive Metastore las particiones recien escritas por Spark.

    Trino expone el procedimiento `system.sync_partition_metadata`, equivalente a
    `MSCK REPAIR TABLE` de Hive, para tablas externas sobre object storage.
    """
    from trino.dbapi import connect

    host = os.getenv("TRINO_HOST", "trino")
    port = int(os.getenv("TRINO_PORT", "8080"))
    user = os.getenv("TRINO_USER", "dbt")

    conn = connect(host=host, port=port, user=user, http_scheme="http")
    cur = conn.cursor()
    for table in PARTITIONED_RAW_TABLES:
        print(f"Sincronizando particiones de hive.raw.{table} ...")
        cur.execute(f"CALL hive.system.sync_partition_metadata('raw', '{table}', 'ADD')")
        cur.fetchall()

    # hive.information_schema.partitions no existe en Trino: la tabla sistema
    # "$partitions" expone las particiones registradas de cada tabla.
    for table in PARTITIONED_RAW_TABLES:
        cur.execute(f'SELECT count(*) FROM hive.raw."{table}$partitions"')
        (partitions,) = cur.fetchone()
        print(f"  hive.raw.{table}: {partitions} particiones registradas")


def clean_seed_locations(**_) -> None:
    """Vacia en S3 los prefijos de los seeds antes de `dbt seed`.

    Por que existe: en este stack (Trino 442 + MinIO) el DROP TABLE elimina la
    tabla del metastore pero DEJA los ficheros Parquet en S3 (reproducido con
    tabla scratch). El siguiente CREATE falla con HIVE_PATH_ALREADY_EXISTS.
    Vaciar el prefijo con boto3 hace el seed idempotente en cada ejecucion.
    """
    import boto3

    endpoint = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    access = os.getenv("MINIO_ROOT_USER", os.getenv("AWS_ACCESS_KEY_ID", "minioadmin"))
    secret = os.getenv("MINIO_ROOT_PASSWORD", os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin"))
    bucket = os.getenv("MINIO_LAKE_BUCKET", "lake")
    prefixes = ["staging/product_category_name_translation/"]

    s3 = boto3.client(
        "s3", endpoint_url=endpoint,
        aws_access_key_id=access, aws_secret_access_key=secret,
    )
    for prefix in prefixes:
        keys: list[str] = []
        token = None
        while True:
            kwargs = {"Bucket": bucket, "Prefix": prefix}
            if token:
                kwargs["ContinuationToken"] = token
            resp = s3.list_objects_v2(**kwargs)
            keys += [o["Key"] for o in resp.get("Contents", [])]
            token = resp.get("NextContinuationToken")
            if not token:
                break
        if keys:
            for i in range(0, len(keys), 1000):
                chunk = keys[i:i + 1000]
                s3.delete_objects(
                    Bucket=bucket,
                    Delete={"Objects": [{"Key": k} for k in chunk]},
                )
            print(f"Limpieza s3://{bucket}/{prefix}: {len(keys)} objetos eliminados")
        else:
            print(f"Limpieza s3://{bucket}/{prefix}: sin restos")


def assert_trino_has_rows(**_) -> None:
    """Smoke test de la capa de consulta: falla si la zona raw quedo vacia."""
    from trino.dbapi import connect

    conn = connect(
        host=os.getenv("TRINO_HOST", "trino"),
        port=int(os.getenv("TRINO_PORT", "8080")),
        user=os.getenv("TRINO_USER", "dbt"),
        http_scheme="http",
    )
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM hive.raw.orders")
    rows = cur.fetchone()[0]
    print(f"hive.raw.orders -> {rows} filas")
    if rows == 0:
        raise ValueError("hive.raw.orders esta vacio: revisa el job de Spark")


with DAG(
    dag_id="retail_lakehouse_elt",
    description="ELT PostgreSQL -> MinIO -> Spark/Parquet -> Hive Metastore -> dbt -> Trino",
    default_args=default_args,
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["elt", "lakehouse", "spark", "dbt", "trino", "minio"],
    params={"full_refresh": True},
    doc_md=__doc__,
) as dag:

    # ---------------------------------------------------------------- 1. EXTRACT
    extract_to_staging = BashOperator(
        task_id="extract_postgres_to_minio",
        bash_command=(
            f"python {EXTRACT_SCRIPT} "
            f"--run-date {{{{ ds }}}} "
            f"{{% if params.full_refresh %}}--full-refresh{{% endif %}}"
        ),
        env={"RUN_DATE": "{{ ds }}"},
        append_env=True,
    )

    # ------------------------------------------------------------------ 2. LOAD
    spark_csv_to_parquet = SparkSubmitOperator(
        task_id="spark_csv_to_parquet",
        application=SPARK_JOB,
        conn_id="spark_default",
        application_args=[
            "--ingest-date",
            "{{ ds }}",
            "--mode",
            "overwrite",
        ],
        packages=SPARK_PACKAGES,
        conf={
            "spark.sql.sources.partitionOverwriteMode": "dynamic",
            "spark.sql.parquet.compression.codec": "snappy",
        },
        verbose=False,
    )

    # ------------------------------------------------- 3. REGISTRO EN EL CATALOGO
    sync_raw_partitions_task = PythonOperator(
        task_id="sync_raw_partitions",
        python_callable=sync_raw_partitions,
    )

    check_raw_not_empty = PythonOperator(
        task_id="check_raw_not_empty",
        python_callable=assert_trino_has_rows,
    )

    clean_seed_locations_task = PythonOperator(
        task_id="clean_seed_locations",
        python_callable=clean_seed_locations,
    )

    # ------------------------------------------------------------- 4. TRANSFORM
    # dbt deps SIEMPRE antes de seed/run: el `dbt deps` del build de la imagen
    # puede quedar vacio (fallo silencioso) y sin dbt_utils todo dbt falla.
    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command=f"dbt deps --project-dir {DBT_DIR} --profiles-dir {DBT_DIR}",
        append_env=True,
    )

    dbt_seed = BashOperator(
        task_id="dbt_seed",
        bash_command=f"dbt seed --project-dir {DBT_DIR} --profiles-dir {DBT_DIR}",
        append_env=True,
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"dbt run --project-dir {DBT_DIR} --profiles-dir {DBT_DIR}",
        append_env=True,
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"dbt test --project-dir {DBT_DIR} --profiles-dir {DBT_DIR}",
        append_env=True,
        trigger_rule=TriggerRule.ALL_SUCCESS,
    )

    # --------------------------------------------------------- 7. DOCUMENTACION
    dbt_docs_generate = BashOperator(
        task_id="dbt_docs_generate",
        bash_command=(
            f"dbt docs generate --project-dir {DBT_DIR} --profiles-dir {DBT_DIR} --static"
        ),
        append_env=True,
        trigger_rule=TriggerRule.ALL_DONE,
    )

    (
        extract_to_staging
        >> spark_csv_to_parquet
        >> sync_raw_partitions_task
        >> check_raw_not_empty
        >> clean_seed_locations_task
        >> dbt_deps
        >> dbt_seed
        >> dbt_run
        >> dbt_test
        >> dbt_docs_generate
    )
