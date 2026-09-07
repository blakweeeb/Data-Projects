# ---------------------------------------------------------------------------------
# Imagen de Airflow con todo lo necesario para orquestar el pipeline ELT:
#   - Java 17 + PySpark 3.5.1   -> para lanzar el job Spark en modo client
#   - dbt-trino                 -> transformaciones y tests de calidad
#   - cliente Trino             -> sincronizacion de particiones del metastore
#   - SQLAlchemy/psycopg2/boto3 -> extraccion desde PostgreSQL hacia MinIO
# ---------------------------------------------------------------------------------
FROM apache/airflow:2.9.3-python3.11

USER root

# Java 17 (requerido por PySpark 3.5)
RUN apt-get update \
 && apt-get install -y --no-install-recommends openjdk-17-jre-headless curl unzip \
 && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

USER airflow

COPY docker/airflow/requirements.txt /requirements.txt

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r /requirements.txt

# Dependencias de dbt (dbt_utils) se instalan fuera del directorio montado
# para que el bind-mount de ./dbt no las borre en tiempo de ejecucion.
COPY dbt /tmp/dbt_bootstrap
ENV DBT_PACKAGES_INSTALL_PATH=/opt/airflow/dbt_packages
RUN mkdir -p /opt/airflow/dbt_packages \
 && cd /tmp/dbt_bootstrap \
 && dbt deps --profiles-dir /tmp/dbt_bootstrap || true

USER root
RUN rm -rf /tmp/dbt_bootstrap

USER airflow

ENV PYTHONPATH=/opt/airflow
ENV PYSPARK_PYTHON=/usr/local/bin/python
