# PostgreSQL

## Overview

PostgreSQL serves as the operational data store for real-time metrics, providing low-latency queries for Grafana dashboards and ad-hoc analysis.

## Configuration

### Docker Compose

```yaml
postgres:
  image: postgres:16-alpine
  environment:
    POSTGRES_DB: streaming_metrics
    POSTGRES_USER: streaming_user
    POSTGRES_PASSWORD: streaming_pass
  ports:
    - "5432:5432"
  volumes:
    - postgres-data:/var/lib/postgresql/data
    - ./sql/init.sql:/docker-entrypoint-initdb.d/init.sql
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U streaming_user -d streaming_metrics"]
    interval: 10s
    timeout: 5s
    retries: 5
```

### Initialization Script

```sql
-- sql/init.sql

-- Main metrics table
CREATE TABLE IF NOT EXISTS realtime_metrics (
    id BIGSERIAL PRIMARY KEY,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    page VARCHAR(255) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_count BIGINT NOT NULL,
    unique_users BIGINT NOT NULL,
    unique_sessions BIGINT NOT NULL,
    revenue DOUBLE PRECISION DEFAULT 0,
    purchase_count BIGINT DEFAULT 0,
    add_to_cart_count BIGINT DEFAULT 0,
    error_count BIGINT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_realtime_metrics_window ON realtime_metrics(window_start, window_end);
CREATE INDEX IF NOT EXISTS idx_realtime_metrics_page ON realtime_metrics(page);
CREATE INDEX IF NOT EXISTS idx_realtime_metrics_event_type ON realtime_metrics(event_type);
CREATE INDEX IF NOT EXISTS idx_realtime_metrics_created ON realtime_metrics(created_at);

-- View: Latest metrics (last 5 minutes)
CREATE OR REPLACE VIEW latest_metrics AS
SELECT 
    window_start,
    window_end,
    page,
    event_type,
    event_count,
    unique_users,
    unique_sessions,
    revenue,
    purchase_count,
    add_to_cart_count,
    error_count,
    (event_count::float / EXTRACT(EPOCH FROM (window_end - window_start))) as events_per_second
FROM realtime_metrics
WHERE window_start >= NOW() - INTERVAL '5 minutes'
ORDER BY window_start DESC, event_count DESC;

-- View: Page aggregates (last 1 hour)
CREATE OR REPLACE VIEW page_metrics AS
SELECT 
    page,
    SUM(event_count) as total_events,
    SUM(unique_users) as total_unique_users,
    SUM(unique_sessions) as total_sessions,
    SUM(revenue) as total_revenue,
    SUM(purchase_count) as total_purchases,
    MAX(window_end) as last_update
FROM realtime_metrics
WHERE window_start >= NOW() - INTERVAL '1 hour'
GROUP BY page
ORDER BY total_events DESC;

-- View: Event type aggregates (last 1 hour)
CREATE OR REPLACE VIEW event_type_metrics AS
SELECT 
    event_type,
    SUM(event_count) as total_events,
    SUM(unique_users) as total_unique_users,
    SUM(revenue) as total_revenue,
    SUM(purchase_count) as total_purchases,
    SUM(add_to_cart_count) as total_add_to_cart,
    SUM(error_count) as total_errors,
    MAX(window_end) as last_update
FROM realtime_metrics
WHERE window_start >= NOW() - INTERVAL '1 hour'
GROUP BY event_type
ORDER BY total_events DESC;
```

## Schema Details

### Table: realtime_metrics

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | BIGSERIAL | NO | Primary key |
| `window_start` | TIMESTAMPTZ | NO | Window start time |
| `window_end` | TIMESTAMPTZ | NO | Window end time |
| `page` | VARCHAR(255) | NO | Page URL |
| `event_type` | VARCHAR(50) | NO | Event type |
| `event_count` | BIGINT | NO | Total events in window |
| `unique_users` | BIGINT | NO | Distinct users |
| `unique_sessions` | BIGINT | NO | Distinct sessions |
| `revenue` | DOUBLE PRECISION | YES | Revenue from purchases |
| `purchase_count` | BIGINT | YES | Purchase events |
| `add_to_cart_count` | BIGINT | YES | Add to cart events |
| `error_count` | BIGINT | YES | Error events |
| `created_at` | TIMESTAMPTZ | NO | Record creation time |

### Indexes

```sql
-- Composite index for time-range + page queries
CREATE INDEX idx_realtime_window_page 
ON realtime_metrics(window_start, page);

-- Composite index for time-range + event_type queries
CREATE INDEX idx_realtime_window_event 
ON realtime_metrics(window_start, event_type);

-- Partial index for recent data (last 24h)
CREATE INDEX idx_realtime_recent 
ON realtime_metrics(window_start) 
WHERE window_start >= NOW() - INTERVAL '24 hours';
```

## Writing Data

### From Spark (foreachBatch)

```python
def write_to_postgres(batch_df, batch_id):
    if batch_df.isEmpty():
        return
    
    rows = batch_df.collect()
    data = [
        (
            row.window_start, row.window_end, row.page, row.event_type,
            row.event_count, row.unique_users, row.unique_sessions,
            float(row.revenue) if row.revenue else 0.0,
            row.purchase_count, row.add_to_cart_count, row.error_count,
            row.processed_at
        )
        for row in rows
    ]
    
    conn = psycopg2.connect(
        host=POSTGRES_HOST, port=POSTGRES_PORT,
        database=POSTGRES_DB, user=POSTGRES_USER, password=POSTGRES_PASSWORD
    )
    cursor = conn.cursor()
    
    execute_values(cursor, """
        INSERT INTO realtime_metrics 
        (window_start, window_end, page, event_type, event_count, unique_users, 
         unique_sessions, revenue, purchase_count, add_to_cart_count, error_count, processed_at)
        VALUES %s
        ON CONFLICT DO NOTHING
    """, data)
    
    conn.commit()
    cursor.close()
    conn.close()
```

### Upsert Strategy

```sql
-- For updates (if window can be updated)
INSERT INTO realtime_metrics (...) VALUES (...)
ON CONFLICT (window_start, window_end, page, event_type) 
DO UPDATE SET
    event_count = EXCLUDED.event_count,
    unique_users = EXCLUDED.unique_users,
    unique_sessions = EXCLUDED.unique_sessions,
    revenue = EXCLUDED.revenue,
    purchase_count = EXCLUDED.purchase_count,
    add_to_cart_count = EXCLUDED.add_to_cart_count,
    error_count = EXCLUDED.error_count,
    created_at = NOW();
```

## Querying Data

### Grafana Datasource

```yaml
# grafana/datasources/datasources.yml
- name: PostgreSQL
  type: postgres
  url: postgres:5432
  database: streaming_metrics
  user: streaming_user
  secureJsonData:
    password: streaming_pass
  jsonData:
    sslmode: "disable"
    maxOpenConns: 10
    maxIdleConns: 2
    connMaxLifetime: 14400
    timescaledb: false
```

### Common Queries

```sql
-- Latest metrics (dashboard)
SELECT * FROM latest_metrics LIMIT 100;

-- Page performance
SELECT * FROM page_metrics;

-- Event type breakdown
SELECT * FROM event_type_metrics;

-- Custom time range
SELECT 
    window_start,
    page,
    event_type,
    event_count,
    unique_users,
    revenue
FROM realtime_metrics
WHERE window_start BETWEEN '2024-01-15 10:00:00' AND '2024-01-15 11:00:00'
ORDER BY window_start, event_count DESC;

-- Hourly rollup
SELECT 
    DATE_TRUNC('hour', window_start) as hour,
    SUM(event_count) as total_events,
    SUM(unique_users) as total_users,
    SUM(revenue) as total_revenue
FROM realtime_metrics
WHERE window_start >= NOW() - INTERVAL '24 hours'
GROUP BY 1
ORDER BY 1;

-- Top pages by revenue
SELECT 
    page,
    SUM(revenue) as total_revenue,
    SUM(purchase_count) as purchases,
    SUM(event_count) as total_events
FROM realtime_metrics
WHERE window_start >= NOW() - INTERVAL '1 hour'
GROUP BY page
ORDER BY total_revenue DESC
LIMIT 10;

-- Error rate by page
SELECT 
    page,
    SUM(error_count)::float / NULLIF(SUM(event_count), 0) * 100 as error_rate_pct
FROM realtime_metrics
WHERE window_start >= NOW() - INTERVAL '1 hour'
GROUP BY page
HAVING SUM(event_count) > 100
ORDER BY error_rate_pct DESC;
```

### Psql Commands

```bash
# Connect
docker exec -it postgres psql -U streaming_user -d streaming_metrics

# List tables
\dt

# Describe table
\d realtime_metrics

# List views
\dv

# Describe view
\d+ latest_metrics

# Show indexes
\di

# Run query
SELECT * FROM latest_metrics LIMIT 20;

# Exit
\q
```

## Grafana Dashboard Queries

### Time Series: Events per Page

```sql
-- Grafana format (time column = window_start)
SELECT 
    window_start as time,
    SUM(event_count) as value,
    page as metric
FROM realtime_metrics
WHERE window_start >= NOW() - INTERVAL '10 minutes'
GROUP BY window_start, page
ORDER BY window_start
```

### Stat: Total Events (1h)

```sql
SELECT SUM(event_count) as total_events
FROM realtime_metrics
WHERE window_start >= NOW() - INTERVAL '1 hour'
```

### Stat: Unique Users (1h)

```sql
SELECT SUM(unique_users) as total_users
FROM realtime_metrics
WHERE window_start >= NOW() - INTERVAL '1 hour'
```

### Stat: Revenue (1h)

```sql
SELECT SUM(revenue) as total_revenue
FROM realtime_metrics
WHERE window_start >= NOW() - INTERVAL '1 hour'
```

### Table: Top Pages

```sql
SELECT 
    page,
    SUM(event_count) as events,
    SUM(unique_users) as users,
    SUM(revenue) as revenue,
    MAX(window_end) as last_update
FROM realtime_metrics
WHERE window_start >= NOW() - INTERVAL '1 hour'
GROUP BY page
ORDER BY events DESC
LIMIT 20
```

## Performance Optimization

### Connection Pooling (PgBouncer)

```yaml
# docker-compose.yml addition
pgbouncer:
  image: edoburu/pgbouncer:1.18
  environment:
    DATABASES_HOST: postgres
    DATABASES_PORT: 5432
    DATABASES_DBNAME: streaming_metrics
    POOL_MODE: transaction
    MAX_CLIENT_CONN: 1000
    DEFAULT_POOL_SIZE: 25
    MIN_POOL_SIZE: 5
    RESERVE_POOL_SIZE: 5
    RESERVE_POOL_TIMEOUT: 5
  ports:
    - "6432:6432"
  depends_on:
    - postgres
```

### Partitioning (Large Scale)

```sql
-- Partition by month
CREATE TABLE realtime_metrics_partitioned (
    LIKE realtime_metrics INCLUDING ALL
) PARTITION BY RANGE (window_start);

-- Create monthly partitions
CREATE TABLE realtime_metrics_2024_01 PARTITION OF realtime_metrics_partitioned
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE realtime_metrics_2024_02 PARTITION OF realtime_metrics_partitioned
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
-- ... etc
```

### Vacuum & Analyze

```sql
-- Manual vacuum (autovacuum runs automatically)
VACUUM ANALYZE realtime_metrics;

-- Check table size
SELECT pg_size_pretty(pg_total_relation_size('realtime_metrics'));

-- Check index usage
SELECT * FROM pg_stat_user_indexes WHERE relname = 'realtime_metrics';
```

### Configuration Tuning

```sql
-- postgresql.conf (or ALTER SYSTEM)
-- Memory
shared_buffers = '2GB'
effective_cache_size = '6GB'
work_mem = '64MB'
maintenance_work_mem = '512MB'

# WAL
wal_buffers = '16MB'
min_wal_size = '1GB'
max_wal_size = '4GB'

# Parallelism
max_parallel_workers_per_gather = 4
max_parallel_workers = 8

# Connections
max_connections = 200
```

## Monitoring

### Key Metrics

| Metric | Query | Alert Threshold |
|--------|-------|-----------------|
| Connections | `SELECT count(*) FROM pg_stat_activity` | > 80% of max_connections |
| Table size | `pg_total_relation_size('realtime_metrics')` | > 100GB |
| Index usage | `pg_stat_user_indexes` | idx_scan = 0 (unused) |
| Slow queries | `pg_stat_statements` | mean_time > 1s |
| Replication lag | `pg_stat_replication` | > 1s |

### Prometheus Exporter

```yaml
# Add postgres_exporter to docker-compose
postgres-exporter:
  image: prometheuscommunity/postgres-exporter:v0.15.0
  environment:
    DATA_SOURCE_NAME: "postgresql://streaming_user:streaming_pass@postgres:5432/streaming_metrics?sslmode=disable"
  ports:
    - "9187:9187"
  depends_on:
    - postgres
```

Add to prometheus.yml:
```yaml
- job_name: 'postgres'
  static_configs:
    - targets: ['postgres-exporter:9187']
```

## Backup & Recovery

### Logical Backup

```bash
# Backup
docker exec postgres pg_dump -U streaming_user streaming_metrics > backup.sql

# Restore
cat backup.sql | docker exec -i postgres psql -U streaming_user -d streaming_metrics
```

### Point-in-Time Recovery (PITR)

```bash
# Enable WAL archiving in postgresql.conf
archive_mode = on
archive_command = 'cp %p /var/lib/postgresql/archive/%f'
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `Connection refused` | Check container health, port 5432 |
| `Authentication failed` | Verify credentials in docker-compose |
| `Too many connections` | Add PgBouncer, increase max_connections |
| `Slow queries` | Check indexes, run ANALYZE, check query plan |
| `Disk full` | VACUUM, drop old partitions, increase storage |

### Common Queries for Debugging

```sql
-- Active connections
SELECT pid, usename, application_name, state, query_start, query
FROM pg_stat_activity
WHERE state = 'active';

-- Long-running queries
SELECT pid, now() - query_start as duration, query
FROM pg_stat_activity
WHERE state = 'active' AND now() - query_start > interval '30 seconds';

-- Table bloat
SELECT schemaname, tablename, n_dead_tup, n_live_tup
FROM pg_stat_user_tables
WHERE n_dead_tup > 1000;

-- Missing indexes
SELECT schemaname, tablename, seq_scan, seq_tup_read
FROM pg_stat_user_tables
WHERE seq_scan > 1000 AND seq_tup_read > 100000;
```

## Security (Production)

### SSL/TLS

```yaml
postgres:
  command: >
    -c ssl=on
    -c ssl_cert_file=/etc/postgresql/certs/server.crt
    -c ssl_key_file=/etc/postgresql/certs/server.key
    -c ssl_ca_file=/etc/postgresql/certs/ca.crt
  volumes:
    - ./postgres-certs:/etc/postgresql/certs:ro
```

### Row-Level Security

```sql
-- Enable RLS
ALTER TABLE realtime_metrics ENABLE ROW LEVEL SECURITY;

-- Policy for read access
CREATE POLICY read_metrics ON realtime_metrics
    FOR SELECT USING (current_user = 'grafana_user');
```

## Scaling

### Read Replicas

```yaml
# Add replica
postgres-replica:
  image: postgres:16-alpine
  environment:
    POSTGRES_DB: streaming_metrics
    POSTGRES_USER: streaming_user
    POSTGRES_PASSWORD: streaming_pass
  command: >
    -c hot_standby=on
    -c primary_conninfo="host=postgres port=5432 user=replicator password=repl_pass"
  depends_on:
    - postgres
```

### Citus (Horizontal Scaling)

```sql
-- Install Citus extension
CREATE EXTENSION citus;

-- Distribute table
SELECT create_distributed_table('realtime_metrics', 'window_start');
```