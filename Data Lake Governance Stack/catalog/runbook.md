# Runbook - Data Lake Governance Stack

## Quick Start

```bash
# 1. Start infrastructure
make init

# 2. Run full pipeline
make all

# 3. Access Superset
# http://localhost:8088 (admin/admin)

# 4. View Data Docs
# great_expectations/uncommitted/data_docs/local_site/index.html
```

## Step-by-Step Execution

### 1. Initialize Environment
```bash
make init
```
- Starts Docker containers (Superset + PostgreSQL)
- Installs Python dependencies
- Initializes Great Expectations config

**Expected**: Superset at http://localhost:8088, GX config in `great_expectations/`

### 2. Ingest Data
```bash
make ingest
```
- Downloads Olist dataset from Kaggle (~100MB)
- Converts 9 CSV files to partitioned Parquet
- Generates JSON schemas

**Output**: `data_lake/01_raw/{entity}/year=YYYY/month=MM/*.parquet`

**If fails**: Check internet connection, Kaggle API availability

### 3. Transform Data
```bash
make transform
```
- Reads partitioned raw data
- Applies cleaning rules per entity
- Writes cleaned Parquet to curated layer

**Output**: `data_lake/02_curated/{entity}.parquet`

**If fails**: Check `scripts/transform.py` for missing cleaners

### 4. Validate Quality
```bash
make validate
```
- Runs `raw_checkpoint` on 01_raw/
- Runs `curated_checkpoint` on 02_curated/
- Generates Data Docs HTML

**Output**: `great_expectations/uncommitted/data_docs/local_site/index.html`

**If fails**: Open Data Docs to see failed expectations, fix data or expectations

### 5. Build Serving Layer
```bash
make serve
```
- Creates star schema (facts + dimensions)
- Builds DuckDB database with views
- Configures Superset connection and dashboard

**Output**: `data_lake/03_serving/*.parquet`, `data_lake/03_serving/serving.duckdb`

**If fails**: Check DuckDB connection, Superset API availability

## Troubleshooting

### Superset Not Accessible
```bash
# Check container status
docker compose ps

# Check logs
docker compose logs superset

# Restart
docker compose restart superset
```

### Great Expectations Errors
```bash
# Run checkpoint manually with verbose output
cd great_expectations
gx checkpoint run curated_checkpoint -v
```

### Data Not Appearing in Superset
1. Verify DuckDB database exists: `ls -la data_lake/03_serving/serving.duckdb`
2. Check Superset database connection: Settings → Database Connections
3. Test SQL Lab: SQL Lab → SQL Editor → Select "Data Lake Governance" database
4. Run: `SELECT * FROM fact_orders LIMIT 10;`

### Pipeline Stuck / Hanging
```bash
# Check disk space
df -h

# Check memory
free -h

# Kill stuck processes
pkill -f "python scripts/"
```

### Re-run Single Step
```bash
# Re-ingest (cleans raw first)
make clean && make ingest

# Re-transform only
make transform

# Re-validate only
make validate

# Re-serve only
make serve
```

## Data Quality Debugging

### Failed Expectations
1. Open Data Docs: `great_expectations/uncommitted/data_docs/local_site/index.html`
2. Navigate to failed checkpoint run
3. Review failed expectations with sample data
4. Decide: Fix data (transform) or adjust expectation (schema drift)

### Common Issues
| Issue | Cause | Fix |
|-------|-------|-----|
| Null PK | Source data quality | Add cleaning rule in transform.py |
| Duplicate PK | Ingestion duplication | Check partition logic, deduplicate |
| Value out of range | New data values | Update expectation `mostly` threshold or range |
| Row count drop | Partition filter error | Verify date column parsing |

## Maintenance

### Update Expectations
```bash
# Edit suite JSON directly
vim great_expectations/expectation_suites/olist_orders.json

# Or use GX CLI to edit interactively
gx suite edit olist_orders
```

### Add New Table
1. Add to `config/settings.yaml` → `olist_tables`
2. Add cleaner in `scripts/transform.py` → `CLEANERS` dict
3. Create expectation suite in `great_expectations/expectation_suites/`
4. Run `make ingest transform validate`

### Backup/Restore
```bash
# Backup serving layer
tar -czf serving_backup_$(date +%Y%m%d).tar.gz data_lake/03_serving/

# Restore
tar -xzf serving_backup_YYYYMMDD.tar.gz
```

### Upgrade Dependencies
```bash
# Update Python packages
pip install --upgrade -r requirements.txt

# Upgrade Docker images
docker compose pull
docker compose up -d
```

## Monitoring

### Key Metrics to Watch
- Row counts per table (should be stable)
- GX validation pass rate (target: 100%)
- Superset dashboard load time (<5s)
- DuckDB query performance (<1s for dashboard queries)

### Log Locations
- Pipeline logs: Console output from `make` commands
- Superset logs: `docker compose logs superset`
- GX Data Docs: `great_expectations/uncommitted/data_docs/`

## Emergency Procedures

### Complete Rebuild
```bash
make rebuild
# Equivalent to: make clean && make all
```

### Superset Reset
```bash
docker compose down -v
docker compose up -d
make serve
```

### Data Corruption
```bash
# Remove all generated data
make clean
# Re-run from ingestion
make all
```

## Contacts / Escalation
- **Data Engineering**: Check pipeline logs, Data Docs
- **Platform**: Docker, Superset connectivity
- **Business**: Dashboard metrics, data freshness

## Version Information
- GX Version: 0.18+
- Superset: 3.0+
- DuckDB: 0.9+
- Python: 3.10+