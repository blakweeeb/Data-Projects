# Data Lake Governance Stack

**Versión:** 1.0 — Governanza de datos local / cloud-free  
**Storytelling:** *"Implementando gobernanza de datos desde cero sin costos de licencia"*

---

## 📖 Descripción

Este repositorio implementa un **Data Lake completo** con gobernanza de datos end-to-end usando únicamente software de código abierto y almacenamiento local. El proyecto cubre todo el ciclo de vida de los datos: ingestión, transformación, calidad, almacenamiento en estrella (schema) y visualización.

### Objetivo de portafolio
Demostrar habilidades de Data Engineering con pilas tecnológicas modernas sin licencias propietarias:
- **Great Expectations** para validación de calidad de datos
- **DuckDB** para consulta analítica embebida
- **Apache Superset** para dashboards interactivos
- **Pandas + PyArrow** para procesamiento de datos
- **Kaggle** para descarga de datasets

---

## 🏗️ Arquitectura (Medallion Pattern)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DATA LAKE GOVERNANCE STACK                           │
├─────────────────────────────────────────────────────────────────────────────│
│  ┌─────────────────┐    ┌────────────────────┐    ┌────────────────────┐ │
│  │  00_landing     │    │  01_raw          │    │  02_curated       │ │
│  │  (CSVs crudos)  │→→→→│  (Parquet part.)   │→→→→│  (Limpio, tipado) │ │
│  └─────────────────┘    └──────────────────┘    └──────────────────┘ │
│           │                      │                      │              │
│           ▼                      ▼                      ▼              │
│  ┌─────────────────┐    ┌────────────────────┐    ┌────────────────────┐ │
│  │  03_serving     │    │  DuckDB          │    │  Superset          │ │
│  │  (Star Schema)  │    │  (views sobre PK)│    │  (Dashboards)      │ │
│  └─────────────────┘    └────────────────────┘    └──────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Stack Tecnológico

| Capa | Herramienta | Propósito |
|------|-------------|-----------|
| **Ingestión** | `kagglehub` + Python | Descarga dataset Olist de Kaggle |
| **Procesamiento** | `Pandas` + `PyArrow` | Transformación, limpieza, Particionado |
| **Calidad** | **Great Expectations** (0.18+/1.x) | Expectation suites, checkpoints, Data Docs |
| **Almacenamiento** | Sistema de archivos local + **Parquet** | Columnar, compresión Snappy, particionado year=YYYY/month=MM |
| **Motor Analítico** | **DuckDB** | Queries SQL sobre archivos Parquet, vistas virtuales |
| **Visualización** | **Apache Superset** (Docker) | Dashboards interactivos, KPIs empresariales |
| **Testing** | `pytest` | 30 tests automatizados (ingest, transform, serving) |
| **Metadatos** | JSON Schema + Markdown | Diccionario, lineage, runbook |

---

## 📦 Datos Incluidos

- **Dataset:** Olist Brazilian E-commerce Database (Kaggle `olistbr/brazilian-ecommerce`)
- **Tamaño:** ~100 MB, 9 tablas (~1.5 millones de filas en total)
- **Período:** 2016-2018
- **Tablas:** `customers, geolocation, orders, order_items, order_payments, order_reviews, products, sellers, product_category_name_translation`

---

## 🚀 Instalación y Ejecución

### Prerrequisitos
- Python 3.10+
- Docker Desktop (para Superset)
- Git
- Pip (gestor de paquetes Python)

### 1. Clonar repositorio
```bash
git clone https://github.com/tu-usuario/data-lake-governance-stack.git
cd data-lake-governance-stack
```

### 2. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 3. Ejecutar el pipeline completo
```bash
make all
# O ejecuta los pasos individuales:
make init       # Levanta Docker (Superset + PostgreSQL) + instala deps + init GX
make ingest     # Descarga Olist → data_lake/01_raw/ (Parquet particionado)
make transform  # raw/ → curated/ (limpieza, tipado, enriquecimiento)
make validate   # Ejecuta checkpoints GX + genera Data Docs HTML
make serve      # Build star schema + configura Superset + dashboard
make test       # Ejecutar 30 tests pytest
```

### 4. Acceder a las interfaces
- **Superset:** http://localhost:8088 (usuario: `admin` / password: `admin`)
- **Data Docs:** `great_expectations/uncommitted/data_docs/local_site/index.html`
- **DuckDB queries:** `python -c "import duckdb; con=duckdb.connect('data_lake/03_serving/serving.duckdb'); ..."`

---

## 📊 Resultados del Proyecto

| Métrica | Resultado |
|---------|-----------|
| **Tests unitarios** | 30/30 passing (pytest) |
| **Tablas procesadas** | 9 raw → 9 curated → 7 serving |
| **Filos procesados** | ~1.5 millones |
| **Data Docs GX** | Reportes HTML con expectativas pass/fail |
| **Dashboards Superset** | 7+ KPIs (GMV, entregas, reviews, categorías) |
| **Calidad de datos** | 8 suites de expectation configuradas |

---

## 📁 Estructura del Proyecto

```
data-lake-governance-stack/
├── docker-compose.yml          # Superset + PostgreSQL
├── Makefile                    # Orquestación: make all, ingest, transform, etc.
├── requirements.txt            # Dependencias Python
├── .gitignore                  # Excluye datos generados, caches, venv
├── README.md                   # Este archivo
├── config/
│   ├── settings.yaml           # Rutas, particionado, tablas Olist
│   └── gx_datasources.yaml    # Configuración datasources GX
├── great_expectations/
│   ├── great_expectations.yml  # Configuración GX
│   ├── expectation_suites/     # 8 suites JSON (customers, geolocation, orders, etc.)
│   ├── checkpoints/            # 2 YAML checkpoints (raw, curated)
│   └── uncommitted/
│       └── data_docs/          # HTML reportes generados
├── scripts/
│   ├── ingest.py               # Kaggle → 01_raw (Parquet particionado)
│   ├── transform.py            # 01_raw → 02_curated (limpieza, tipado)
│   ├── build_serving.py        # 02_curated → 03_serving (star schema + DuckDB)
│   ├── gx_run_checkpoint.py    # Validación GX (file-based)
│   └── superset_init.py        # Configura Superset + dashboard
├── data_lake/                  # NO versionado (gitignored)
│   ├── 00_landing/
│   ├── 01_raw/
│   ├── 02_curated/
│   └── 03_serving/
├── catalog/
│   ├── schemas/                # JSON Schema generado en ingesta
│   ├── data_dictionary.md
│   ├── lineage.md
│   └── runbook.md
├── tests/
│   ├── test_ingest.py
│   ├── test_transform.py
│   ├── test_serving.py
│   └── test_gx_integration.py
└── README.md
```

---

## 🧪 Tests Automatizados

```bash
make test
# O: pytest tests/ -v
```

| Test | Valida |
|------|--------|
| `test_ingest` | Estructura raw, particionamiento, schemas JSON |
| `test_transform` | Tablas curadas, nulos, claves, formatos ZIP, estados |
| `test_serving` | Tablas serving, DuckDB, reconciliación de filas |
| `test_gx_integration` | Configuración GX, suites, checkpoints |

---

## 📊 Dashboards Superset (ejemplo)

El dashboard `Olist E-commerce - Data Lake Governance` incluye 7+ charts:

1. **GMV Diario** - Línea temporal con pago acumulado
2. **Pedidos por Día** - Volumen de órdenes
3. **Estados de Pedido** - Distribución pie chart
4. **Tiempo de Entrega** - Histograma de días
5. **Tasa Entregas Tardías** - KPI principal
6. **Top 10 Categorías** - Tabla revenue
7. **Review Score por Estado** - Promedio por estado

---

## 🔧 Personalización

### Cambiar dataset
Editar `config/settings.yaml` → `olist_tables` y añadir tablas propias.

### Añadir nuevas expectation suites
1. Crear `great_expectations/expectation_suites/mi_tabla.json`
2. Ejecutar `make validate` para verificar
3. El suite aparecerá en los Data Docs

### Particionado personalizado
Modificar `config/settings.yaml` → `partitioning.date_columns` para otras columnas de fecha.

### Backup/Restore
```bash
# Backup
tar -czf backup_$(date +%Y%m%d).tar.gz data_lake/03_serving/

# Restore
tar -xzf backup_YYYYMMDD.tar.gz
```

---

## 📜 Licencia

**MIT License** — Libre para uso educativo y comercial.

---

## 👨‍💻 Autor

Proyecto de portafolio de Data Engineering.  
Demuestra competencias en: Data Lake, Quality, Orchestration, BI, Python, Docker, DuckDB, Great Expectations, Superset.

---

## 📬 Contacto

- **GitHub:** [tu-usuario/data-lake-governance-stack](https://github.com/tu-usuario/data-lake-governance-stack)
- **Problemas:** Usa `issues` en el repositorio para reportar bugs o Feature Requests.