# =====================================================================================
# RetailLakehouse-ELT - atajos de operacion
# =====================================================================================
SHELL := /bin/bash
DC    := docker compose
DAG   := retail_lakehouse_elt

.PHONY: help up build down ps logs gen-data seed trigger dbt-run dbt-test dbt-docs \
        trino-cli trino-query minio docs test clean

help: ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ----------------------------------------------------------------- ciclo de vida
build: ## Construye las imagenes (solo la de Airflow es propia)
	$(DC) build

up: ## Levanta todo el stack en segundo plano
	$(DC) up -d --build

down: ## Detiene los contenedores
	$(DC) down

clean: ## Detiene y BORRA volumenes (MinIO, Postgres, metastore)
	$(DC) down -v

ps: ## Estado de los servicios
	$(DC) ps

logs: ## Logs del scheduler de Airflow (Ctrl+C para salir)
	$(DC) logs -f airflow-scheduler

# ------------------------------------------------------------------------ datos
gen-data: ## Genera el dataset de muestra en data/raw/
	python scripts/generate_sample_data.py --out-dir data/raw

data/raw/orders.csv:
	@$(MAKE) gen-data

seed: data/raw/orders.csv ## Carga los CSV en PostgreSQL (crea el esquema de ventas)
	$(DC) run --rm seed-postgres

# --------------------------------------------------------------------- pipeline
trigger: ## Lanza el DAG manualmente
	$(DC) exec -T airflow-scheduler airflow dags trigger $(DAG)

unpause: ## Activa el DAG (por defecto Airflow lo deja en pausa)
	$(DC) exec -T airflow-scheduler airflow dags unpause $(DAG)

dbt-run: ## Ejecuta los modelos dbt dentro del contenedor de Airflow
	$(DC) exec -T airflow-scheduler dbt run --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt

dbt-test: ## Ejecuta los tests de calidad de dbt
	$(DC) exec -T airflow-scheduler dbt test --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt

dbt-docs: ## Genera la documentacion estatica (visible en http://localhost:8080)
	$(DC) exec -T airflow-scheduler dbt docs generate --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt --static

# ----------------------------------------------------------------------- trino
trino-cli: ## Abre la CLI de Trino
	$(DC) exec -T trino trino --server localhost:8080

trino-query: ## Ejecuta una consulta de ejemplo sobre el lakehouse
	$(DC) exec -T trino trino --server localhost:8080 --execute \
	  "SELECT order_month_start, orders, revenue FROM hive.lakehouse.agg_sales_monthly ORDER BY order_month_start LIMIT 12"

test: ## Tests unitarios
	python -m pytest tests/ -v
