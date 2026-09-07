# 🎬 Guion del video de 3 minutos

**Título:** *De PostgreSQL a un Data Lakehouse:* ELT con Airflow + Spark + dbt + Trino
**Formato:** screencast con locución, 1080p. Sin música, o música muy baja.
**Objetivo:** que en 3 min se vea el flujo completo y se entienda el *por qué*, no solo el *qué*.

Antes de grabar: `make up && make seed && make trigger` y deja el pipeline terminado una vez.

---

| # | Tiempo | Qué se ve en pantalla | Locución (texto para leer) |
|---|---|---|---|
| 1 | 0:00 – 0:20 | Diagrama de arquitectura (`docs/arquitectura.md`) | *"Una empresa tiene sus ventas en PostgreSQL y quiere analítica sin castigar la operación. Este proyecto migra ese OLTP a un lakehouse abierto: MinIO como object storage, Spark para convertir a Parquet, Hive Metastore como catálogo, dbt para modelar y Trino para consultar. Todo orquestado con Airflow y ejecutable con un `docker compose up`."* |
| 2 | 0:20 – 0:45 | Terminal: `docker compose ps` (10 contenedores *healthy*) + consola de MinIO mostrando `staging/` y `lake/` | *"Arranco el stack: PostgreSQL con el esquema de ventas, MinIO, Spark, el metastore, Trino y Airflow. En MinIO separo dos zonas: `staging`, donde aterriza la copia cruda en CSV, y `lake`, donde vive el Parquet ya curado."* |
| 3 | 0:45 – 1:05 | Código: `extract/extract_postgres_to_minio.py`; luego el DAG en la UI de Airflow | *"La extracción la hace un script de Python con SQLAlchemy: lee por chunks y escribe CSV particionados por fecha de ingesta, con un manifest de auditoría. Admite ventana incremental o carga completa."* |
| 4 | 1:05 – 1:35 | Trigger del DAG → vista *Graph* → tareas verde. Abrir la UI de Spark (8083) durante `spark_csv_to_parquet` | *"El DAG tiene siete tareas. La segunda lanza un job de PySpark: aplica el esquema declarado, deduplica por clave primaria, añade año y mes, y escribe Parquet comprimido en Snappy. Uso dynamic partition overwrite, así que relanzar la misma fecha no duplica nada."* |
| 5 | 1:35 – 2:00 | MinIO: `lake/raw/orders/order_year=2017/order_month=5/…parquet`. Después Trino: `SHOW TABLES IN hive.lakehouse` | *"Spark solo escribe ficheros; el catálogo se actualiza desde Trino con `sync_partition_metadata`, el equivalente a MSCK REPAIR. Por eso cualquier motor que hable con el metastore ve los datos al instante."* |
| 6 | 2:00 – 2:30 | `make dbt-run` (o tarea `dbt_run`); luego **<http://localhost:8080>** → grafo de linaje de `fct_orders` | *"Con dbt modelo las capas: staging limpia y tipa, intermediate enriquece las líneas de pedido, y los marts dejan las tablas de negocio: `fct_orders`, dimensiones de cliente y producto, ventas mensuales y cohortes de retención. La documentación y el linaje se generan solos en cada ejecución."* |
| 7 | 2:30 – 2:50 | `make dbt-test` → salida con ~40 tests PASS; señalar los dos singulares de cuadratura | *"Cada corrida ejecuta unos cuarenta tests: nulos, únicos, relaciones, valores permitidos y rangos. Y dos de cuadratura: uno compara los pedidos de PostgreSQL con los del lakehouse en la misma consulta, otro valida que lo pagado no se desvíe más de un uno por ciento del valor del pedido."* |
| 8 | 2:50 – 3:00 | CLI de Trino: ventas mensuales + top categorías (consultas 2 y 3 de `docs/queries_trino.sql`) | *"Y el resultado: SQL ad-hoc sobre el lakehouse sin mover datos. De PostgreSQL a Parquet gobernado por un catálogo abierto, con calidad y documentación automatizadas. El repo está en mi GitHub."* |

---

## Checklist de grabación

- [ ] `docker compose ps` muestra todos los servicios *healthy* antes de empezar.
- [ ] El DAG ya se ejecutó una vez (así la UI de Airflow y dbt docs tienen contenido).
- [ ] Zoom del terminal al 125 % y fuente grande (se suele ver en móvil).
- [ ] Ocultar tokens/claves: aquí todo es `minioadmin` / `olist`, no hay secretos reales.
- [ ] Exportar a MP4 1080p y subirlo como *video destacado* en el README (GitHub admite MP4 < 10 MB; si pesa más, súbelo a YouTube y pon un GIF de 10 s en el README).
