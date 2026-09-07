# 🏗️ RetailLakehouse-ELT — Manual de uso

**Migración ELT de una base relacional a un data lakehouse abierto**
`PostgreSQL → MinIO (staging) → Spark (Parquet) → Hive Metastore → dbt → Trino`

> Este README es el manual del proyecto: **qué hace**, **cómo funciona por dentro**,
> **de dónde salen los datos** y **qué tienes que ejecutar tú, paso a paso** (con y sin Airflow).

---

## 0. TL;DR (30 segundos)

```bash
cd RetailLakehouse-ELT
cp .env.example .env                 # opcional
python scripts/generate_sample_data.py --out-dir data/raw   # 1) crea los datos de origen
docker compose up -d --build         # 2) levanta los 10 servicios (5-10 min la 1ª vez)
docker compose run --rm seed-postgres # 3) carga los CSV en PostgreSQL
docker compose exec -T airflow-scheduler airflow dags unpause retail_lakehouse_elt
docker compose exec -T airflow-scheduler airflow dags trigger retail_lakehouse_elt
```

Y abre <http://localhost:8081> (Airflow, `airflow`/`airflow`) para ver el DAG correr.
Al terminar: documentación en <http://localhost:8080> y consultas en Trino (`make trino-cli`).

Si prefieres **ejecutar cada etapa a mano**, salta a la [sección 5](#5-ejecución-manual-paso-a-paso).

> **Windows:** Git Bash **no trae `make`**. El `Makefile` es sólo azúcar sintáctica: todos los
> comandos de este README están escritos con `docker compose`, así que puedes seguirlo tal cual.
> (Si quieres `make`, instálalo con `choco install make`.)

---

## 1. ¿Qué hace?

Saca las ventas de una base transaccional PostgreSQL y las convierte en un **lakehouse**:
ficheros **Parquet** en un object storage tipo S3, **catalogados** en un Hive Metastore y
consultables con **SQL estándar** desde Trino, con las transformaciones **versionadas en dbt**.

| Antes (OLTP) | Después (Lakehouse) |
|---|---|
| El BI compite con la operación | Copia inmutable en object storage |
| Ficheros sueltos sin histórico | Parquet + Snappy particionado por `order_year/order_month` |
| Transformaciones en scripts sueltos | Modelos dbt documentados y con tests |
| Nadie sabe qué significa cada campo | Catálogo (Hive Metastore) + documentación dbt publicada |
| Un motor para todo | Spark para el peso pesado, Trino para consultas ad-hoc |

**Dominio:** e-commerce brasileño (mismo esquema que el dataset público de **Olist**:
`customers`, `orders`, `order_items`, `order_payments`, `order_reviews`, `products`, `sellers`, `geolocation`).

---

## 2. ¿Cómo funciona? (etapa por etapa)

```
PostgreSQL ──(1) extract──► MinIO staging/ (CSV) ──(2) spark──► MinIO lake/raw/ (Parquet)
                                                                        │
                                                          (3) sync_partition_metadata
                                                                        ▼
                                                       ┌─────────────────────────────┐
                                                       │ Hive Metastore (catálogo)   │
                                                       └──────────────┬──────────────┘
                                                                      │
                                    (4) dbt run/test/docs ────────────┤
                                                                      ▼
                                                  MinIO lake/lakehouse/ (Parquet de los marts)
                                                                      │
                                                        (5) SELECT … ▼
                                                                Trino
```

| # | Etapa | Quién lo ejecuta | Entra | Sale | Dónde queda |
|---|---|---|---|---|---|
| **1** | **Extract** | Airflow → `extract/extract_postgres_to_minio.py` | Tablas de PostgreSQL | CSV por chunks + `manifest.json` | `s3://staging/postgres/olist/<tabla>/ingest_date=AAAA-MM-DD/` |
| **2** | **Load / RAW** | Airflow → `SparkSubmitOperator` → `spark/jobs/raw_to_parquet.py` | Los CSV de staging | Parquet Snappy, deduplicado, particionado | `s3://lake/raw/<tabla>/` |
| **3** | **Catálogo** | Airflow (cliente Python de Trino) | Ficheros nuevos en `lake/raw/` | Particiones registradas | Hive Metastore (`hive.raw.*`) vía `sync_partition_metadata` |
| **4** | **Transform** | Airflow → `dbt seed/run/test/docs` | `hive.raw.*` + seed de categorías | Tablas y vistas analíticas | `hive.staging.*` (vistas) y `hive.lakehouse.*` (tablas Parquet) |
| **5** | **Consulta** | Tú (CLI/UI de Trino, BI, notebooks) | Catálogo + Parquet | Resultados SQL | — |

### Detalle de cada etapa

**1. Extracción — `extract/extract_postgres_to_minio.py`**
- Se conecta con **SQLAlchemy** y lee por *chunks* de 100 000 filas (no carga la tabla en memoria).
- Escribe un CSV por chunk directamente en MinIO con `boto3` (`put_object`).
- Guarda un `manifest.json` por ejecución (filas, bytes, query) → sirve para auditar y cuadrar.
- Soporta **extracción incremental**: con `--run-date D` extrae la ventana `[D, D+1)` de las tablas
  con columna temporal (`orders.order_purchase_timestamp`). El resto de tablas (dimensiones y
  `order_reviews`) se extraen completas en cada ejecución, porque su zona raw no está particionada
  y un `overwrite` incremental borraría el histórico. Con `--full-refresh` extrae todo.

**2. Spark — `spark/jobs/raw_to_parquet.py`**
- Esquema **declarado** (no inferido) para cada tabla → tipos estables y sin escaneo extra.
- Deduplica por clave primaria (`dropDuplicates`).
- Añade `order_year` / `order_month` a `orders`, y se los presta a `order_items` con un
  **broadcast join** por `order_id`.
- Escribe Parquet con compresión **Snappy**, `coalesce(1)` por partición (evita *small files*) y
  `partitionOverwriteMode=dynamic` → reejecutar sólo reescribe las particiones del lote (idempotente).

**3. Catálogo — Hive Metastore + Trino**
- `scripts/init_trino_schemas.sql` crea los esquemas (`raw`, `staging`, `lakehouse`) **apuntando a
  MinIO** y las tablas externas de la zona raw.
- Tras cada carga, el DAG ejecuta `CALL hive.system.sync_partition_metadata('raw','<tabla>','ADD')`
  (el equivalente a `MSCK REPAIR TABLE`) para que el catálogo descubra las carpetas
  `order_year=2017/order_month=5/`.

**4. dbt (con el adaptador dbt-trino)**
- `staging/` (8 vistas): limpieza, tipado, normalización (estados en mayúsculas, categorías traducidas al inglés…).
- `intermediate/`: `int_order_lines` (líneas enriquecidas), agregados de pagos y reseñas por pedido.
- `marts/` (6 tablas Parquet): `fct_orders`, `dim_customers`, `dim_products`, `agg_sales_monthly`,
  `agg_category_monthly`, `customer_retention_cohorts`.
  - `dim_customers` se construye a grano `customer_unique_id` (**persona**), no `customer_id`
    (que en Olist es una clave por pedido): así `lifetime_value` no se duplica al sumarlo en un BI.
- Macro propio `title_case()`: **Trino 442 no implementa `INITCAP` ni `TITLE_CASE`**, así que se
  resuelve con `split` + `transform` + `array_join` (`dbt/macros/title_case.sql`).
- Tests y documentación en cada ejecución.

**5. Trino**
- Motor SQL federado: puede consultar **a la vez** el PostgreSQL de origen y el lakehouse,
  lo que permite la **cuadratura** origen↔lakehouse en una sola query.

---

## 3. ¿Qué base de datos usa y de dónde salen los datos?

### Base de datos de ORIGEN
| | |
|---|---|
| Motor | **PostgreSQL 15** (contenedor `rl-postgres-source`) |
| Base / usuario / password | `olist` / `olist` / `olist` |
| Puerto en tu máquina | `5432` (cambiable con `PG_HOST_PORT` en `.env`) |
| Esquema | 8 tablas con FKs, PKs e índices (ver `scripts/seed_postgres.py`) |

| Tabla | Descripción | Filas (muestra) |
|---|---|---|
| `customers` | Maestro de clientes | 12 000 |
| `geolocation` | Referencia geográfica por CP | 3 000 |
| `sellers` | Vendedores | 300 |
| `products` | Productos + categoría | 2 000 |
| `orders` | Pedidos (cabecera) | 18 000 |
| `order_items` | Líneas de pedido | 44 604 |
| `order_payments` | Pagos (1-2 por pedido, suman el total) | 22 478 |
| `order_reviews` | Reseñas y score 1-5 | 10 472 |

Rango temporal de los pedidos: **2016-09 → 2018-08**.

### ¿De dónde saco los datos? Dos opciones

**A) Dataset sintético (por defecto, ya incluido)** ✅
- `scripts/generate_sample_data.py` genera CSVs **deterministas** (semilla fija) con el mismo
  esquema del dataset público de Olist: estados, categorías, distribución de precios, estatus de
  pedido, tiempos de entrega y reseñas realistas.
- Total ≈ **12 MB** en `data/raw/`. Están en el `.gitignore` (se regeneran con `make gen-data`),
  así que el repo pesa poco y nunca falla por falta de credenciales.

**B) Dataset real de Olist (Kaggle)** — opcional
1. Descarga <https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce>
   (`olist_customers_dataset.csv`, `olist_orders_dataset.csv`, …).
2. Renómbralos sin el prefijo `olist_` y sin el sufijo `_dataset` → `customers.csv`, `orders.csv`, …
   y déjalos en `data/raw/` (mismo nombre de columnas: ya coincide).
3. `docker compose run --rm seed-postgres`.

### Bases de datos *de soporte* (no son el origen)
- `postgres-meta` (`rl-postgres-meta`): aloja el esquema del **Hive Metastore** (`metastore`)
  y la metadata de **Airflow** (`airflow`). Se agrupan para ahorrar RAM.
- **MinIO**: object storage con dos buckets → `staging/` (CSV crudo) y `lake/` (Parquet).
- **Hive Metastore**: guarda *metadatos* (esquemas, tablas, particiones, rutas S3), no datos.

---

## 4. Requisitos y arranque

- **Docker Desktop encendido** con **≥ 8 GB de RAM** y **≥ 4 CPUs** asignados (10 contenedores).
  > ⚠️ Si `docker compose ps` da error de `npipe`/daemon, es que Docker Desktop no está abierto.
- **Python 3.11+** en tu máquina (sólo para generar datos y correr los tests unitarios).
- Puertos libres: `5432, 7077, 8080-8084, 9000, 9001, 9083`.

```bash
cp .env.example .env     # opcional: cambia credenciales / PG_HOST_PORT si choca con tu Postgres local
```

### Servicios, puertos y accesos

| Servicio | URL | Credenciales |
|---|---|---|
| **dbt docs** (documentación) | <http://localhost:8080> | — |
| **Airflow** | <http://localhost:8081> | `airflow` / `airflow` |
| **Trino** | <http://localhost:8082> | usuario `dbt` (sin password) |
| **Spark Master** | <http://localhost:8083> | — |
| **Spark Worker** | <http://localhost:8084> | — |
| **MinIO API / Consola** | <http://localhost:9000> · <http://localhost:9001> | `minioadmin` / `minioadmin` |
| **PostgreSQL origen** | `localhost:5432` | db `olist`, user `olist`, pass `olist` |
| **Hive Metastore** | thrift `localhost:9083` | — |

> **Windows sin `make`**: todos los comandos del Makefile tienen su equivalente `docker compose …`
> en este README. Si tienes `make` (Git Bash / WSL / Chocolatey), `make help` los lista todos.

---

## 5. Ejecución manual paso a paso

### 5-A. Puesta en marcha (una sola vez)

```bash
# 0) Driver JDBC para el Hive Metastore (no se versiona, ~1 MB)
mkdir -p config/hive/lib
curl -sSL -o config/hive/lib/postgresql-42.7.3.jar https://jdbc.postgresql.org/download/postgresql-42.7.3.jar

# 1) Datos de origen (CSV en data/raw)
python scripts/generate_sample_data.py --out-dir data/raw

# 2) Levantar el stack (la 1ª vez construye la imagen de Airflow: Java 17 + PySpark + dbt)
docker compose up -d --build

# 3) Crear el esquema de ventas en PostgreSQL y cargar los CSV
docker compose run --rm seed-postgres

# 4) Comprobar que todo está arriba
docker compose ps
```
Salida esperada de `docker compose ps`: 10-11 contenedores `Up/healthy`
(`rl-postgres-source`, `rl-postgres-meta`, `rl-minio`, `rl-hive-metastore`, `rl-spark-master`,
`rl-spark-worker`, `rl-trino`, `rl-airflow-webserver`, `rl-airflow-scheduler`, `rl-dbt-docs`).

---

### 5-B. Ejecutar TODO con Airflow (lo habitual)

```bash
docker compose exec -T airflow-scheduler airflow dags unpause retail_lakehouse_elt
docker compose exec -T airflow-scheduler airflow dags trigger retail_lakehouse_elt
docker compose logs -f airflow-scheduler      # Ctrl+C para salir
```
O desde la UI: <http://localhost:8081> → DAG `retail_lakehouse_elt` → **▶ Trigger**.

---

### 5-C. Ejecutar cada etapa A MANO (sin Airflow)

Úsalo para entender/depurar el pipeline. **Importante:** la fecha que pasas a la extracción
(`--run-date`) y a Spark (`--ingest-date`) **debe ser la misma**, porque Spark lee justo el prefijo
`ingest_date=` que escribió la extracción.

```bash
FECHA=2024-01-01
```

**① Extracción: PostgreSQL → CSV en MinIO**
```bash
docker compose exec -T airflow-scheduler \
  python /opt/airflow/extract/extract_postgres_to_minio.py --run-date $FECHA --full-refresh
```
- Quita `--full-refresh` para extracción incremental de ese día.
- Verifica en MinIO (<http://localhost:9001>): bucket `staging` →
  `postgres/olist/orders/ingest_date=2024-01-01/orders_0000.csv` y
  `postgres/olist/_manifest/ingest_date=2024-01-01/manifest.json`.

**② Spark: CSV → Parquet particionado**
```bash
docker compose exec -T airflow-scheduler spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 \
  /opt/airflow/spark/jobs/raw_to_parquet.py --ingest-date $FECHA --mode overwrite
```
- La primera ejecución tarda más: descarga los jars de S3A.
- Verifica: Spark UI <http://localhost:8083> y MinIO bucket `lake` →
  `raw/orders/order_year=2016/order_month=9/…parquet`.

**③ Registrar las particiones en el catálogo**
```bash
docker compose exec -T trino trino --server localhost:8080 --execute \
  "CALL hive.system.sync_partition_metadata('raw','orders','ADD')"
docker compose exec -T trino trino --server localhost:8080 --execute \
  "CALL hive.system.sync_partition_metadata('raw','order_items','ADD')"
docker compose exec -T trino trino --server localhost:8080 --execute \
  "SELECT count(*) FROM hive.raw.orders"
```
Debe devolver 18 000.

**④ dbt: modelos, tests y documentación**
```bash
D="--project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt"
docker compose exec -T airflow-scheduler dbt seed $D     # carga la tabla de traducción de categorías
docker compose exec -T airflow-scheduler dbt run  $D     # crea vistas y tablas
docker compose exec -T airflow-scheduler dbt test $D     # ~40 tests de calidad
docker compose exec -T airflow-scheduler dbt docs generate $D --static
```

**⑤ Consultar con Trino**
```bash
docker compose exec -T trino trino --server localhost:8080 --execute \
  "SELECT date_format(order_month_start,'%Y-%m') AS mes, orders, revenue
   FROM hive.lakehouse.agg_sales_monthly ORDER BY order_month_start"
```
Más consultas listas en [`docs/queries_trino.sql`](docs/queries_trino.sql).

---

## 6. Cómo saber que funcionó ✅

| # | Comprobación | Resultado esperado |
|---|---|---|
| 1 | `docker compose ps` | todos los servicios `Up (healthy)` |
| 2 | MinIO → bucket `staging` | CSV + `manifest.json` bajo `ingest_date=<fecha>/` |
| 3 | MinIO → bucket `lake` | `raw/orders/order_year=…/order_month=…/*.parquet` |
| 4 | `SELECT count(*) FROM hive.raw.orders` | 18 000 |
| 5 | `SHOW TABLES IN hive.lakehouse` | `fct_orders`, `dim_customers`, `dim_products`, `agg_sales_monthly`, `agg_category_monthly`, `customer_retention_cohorts` |
| 6 | Cuadratura origen vs lakehouse | `filas_postgres = filas_lakehouse` |
| 7 | `dbt test` | `PASS=…` y `Done.` sin `FAIL` |
| 8 | <http://localhost:8080> | Documentación dbt con el grafo de linaje |

Cuadratura (Trino consulta los dos orígenes a la vez):
```sql
SELECT (SELECT count(*) FROM postgresql.public.orders)  AS filas_postgres,
       (SELECT count(*) FROM hive.lakehouse.fct_orders) AS filas_lakehouse;
```

---

## 7. Estructura del repositorio

```
RetailLakehouse-ELT/
├── docker-compose.yml              # 10 servicios
├── Makefile                        # atajos: up / seed / trigger / dbt-* / trino-cli
├── .env.example
├── docker/airflow/                 # Dockerfile (Airflow + Java 17 + PySpark + dbt-trino)
├── config/
│   ├── hive/hive-site.xml          # metastore → PostgreSQL, warehouse en s3a://lake/
│   ├── spark/spark-defaults.conf   # S3A (MinIO) + Snappy + dynamic partition overwrite
│   └── trino/…                     # config + catálogos hive y postgresql
├── scripts/
│   ├── generate_sample_data.py     # dataset sintético determinista (origen de los datos)
│   ├── seed_postgres.py            # crea el OLTP y carga los CSV
│   └── init_trino_schemas.sql      # esquemas + tablas externas sobre el Parquet
├── extract/extract_postgres_to_minio.py   # E: SQLAlchemy → CSV en MinIO
├── spark/jobs/raw_to_parquet.py           # L: CSV → Parquet Snappy particionado
├── dbt/                            # modelos staging/intermediate/marts + tests + seeds
├── dags/dag_retail_lakehouse_elt.py       # orquestador de todo lo anterior
├── tests/test_extract.py           # pytest (lógica pura de extracción)
├── data/raw/                       # CSV de origen (generados)
└── docs/arquitectura.md, queries_trino.sql, video_script.md
```

---

## 8. Troubleshooting

| Síntoma | Causa | Solución |
|---|---|---|
| `error during connect: … npipe … dockerDesktopLinuxEngine` | Docker Desktop cerrado | Ábrelo y espera a que diga *Running* |
| `dbt run` no encuentra `hive.lakehouse` | `trino-init` no terminó | `docker compose logs trino-init` y `docker compose up -d trino-init` |
| Spark: `Failed to connect to master` | master inaccesible desde el driver | `docker compose ps` → `rl-spark-master` debe estar `Up`; el DAG usa `spark://spark-master:7077` |
| Spark: `ClassNotFoundException … s3a` | faltan los jars | El comando incluye `--packages …hadoop-aws:3.3.4`; la 1ª vez descarga (necesita internet) |
| Trino no ve particiones nuevas | falta sincronizar | `CALL hive.system.sync_partition_metadata('raw','orders','ADD')` |
| `make seed` → `Connection refused` | Postgres iniciando | El script reintenta 30 veces; si falla, `docker compose logs postgres-source` |
| Airflow no lista el DAG | error de importación | `docker compose exec -T airflow-scheduler airflow dags list-import-errors` |
| Puerto 5432 ocupado | Postgres local | `PG_HOST_PORT=5433` en `.env` y `docker compose up -d` |
| El equipo va muy lento | 10 contenedores | `docker compose stop spark-worker` (Spark sigue en el master) o baja la RAM de Trino en `config/trino/jvm.config` |

**Empezar de cero:** `docker compose down -v` (borra también los datos de MinIO y Postgres)
y repite la sección 5-A.

---

## 9. Para el portafolio

**Pitch de 30 s para una entrevista:**
> *"Migramos el OLTP de ventas a un lakehouse abierto. Airflow orquesta tres etapas: extracción
> incremental con SQLAlchemy que deja CSV inmutables en un bucket de staging; un job de PySpark que
> los convierte a Parquet Snappy particionado por año/mes y deduplicado; y dbt, que construye
> staging → intermediate → marts sobre Trino. El Hive Metastore es la única fuente de verdad del
> catálogo y Trino sincroniza las particiones tras cada carga. La calidad se asegura con ~40 tests
> de dbt —incluida una cuadratura automática origen vs lakehouse— y la documentación se publica en
> cada ejecución."*

**Equivalencias cloud (muy preguntadas):** MinIO↔S3 · Hive Metastore↔Glue Data Catalog ·
Spark↔EMR/Glue Jobs · Trino↔Athena · Airflow↔MWAA.

**Roadmap:** Apache Iceberg (time travel / MERGE) · Great Expectations en staging · modelos
incrementales diarios · Superset/Metabase sobre Trino · Terraform a AWS.

El guion del **video de 3 minutos** está en [`docs/video_script.md`](docs/video_script.md).

---

**Licencia:** MIT · **Datos:** sintéticos deterministas (o Olist real si lo descargas de Kaggle).
