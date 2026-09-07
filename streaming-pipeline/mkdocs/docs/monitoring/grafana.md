# Grafana Dashboards

## Overview

Grafana provides visualization and dashboarding for the streaming pipeline, connecting to Prometheus, PostgreSQL, and MinIO data sources.

## Data Sources

### Provisioned Datasources

```yaml
# grafana/datasources/datasources.yml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
    jsonData:
      timeInterval: "15s"
      queryTimeout: "60s"
      httpMethod: "POST"

  - name: PostgreSQL
    type: postgres
    access: proxy
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
    editable: false

  - name: MinIO (S3)
    type: grafana-s3-datasource
    access: proxy
    url: http://minio:9000
    jsonData:
      bucket: metrics
      region: us-east-1
      accessKey: minioadmin
      secretKey: minioadmin123
      endpoint: http://minio:9000
    editable: false
```

### Manual Configuration

If not provisioned, add via UI:
1. **Configuration** → **Data Sources** → **Add data source**
2. Select type and configure

## Dashboard Provisioning

```yaml
# grafana/dashboards/dashboard-provider.yml
apiVersion: 1

providers:
  - name: 'Streaming Pipeline Dashboards'
    orgId: 1
    folder: 'Streaming Pipeline'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
```

Dashboards placed in `/etc/grafana/provisioning/dashboards` are auto-loaded.

## Dashboards

### 1. Web Events Overview

**File**: `grafana/dashboards/web-events-overview.json`  
**Focus**: Business metrics and real-time event flow

#### Panels

| Panel | Type | Query | Purpose |
|-------|------|-------|---------|
| Kafka Throughput | Time Series | `rate(kafka_topic_partition_current_offset{topic="web-events"}[1m])` | Messages/sec per partition |
| Consumer Lag | Time Series | `kafka_consumergroup_lag{topic="web-events"}` | Lag per consumer group/partition |
| Memory Usage | Gauge | `(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100` | System memory % |
| CPU Usage | Gauge | `100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)` | System CPU % |
| Network I/O | Time Series | `rate(node_network_receive_bytes_total[5m])`, `rate(node_network_transmit_bytes_total[5m])` | Network throughput |
| Events per Page | Time Series | PostgreSQL: `SELECT window_start, SUM(event_count), page FROM realtime_metrics WHERE window_start >= NOW() - INTERVAL '10 minutes' GROUP BY window_start, page` | Page traffic |
| Events by Type | Time Series | PostgreSQL: `SELECT window_start, SUM(event_count), event_type FROM realtime_metrics WHERE window_start >= NOW() - INTERVAL '10 minutes' GROUP BY window_start, event_type` | Event type breakdown |
| Total Events (1h) | Stat | PostgreSQL: `SELECT SUM(event_count) FROM realtime_metrics WHERE window_start >= NOW() - INTERVAL '1 hour'` | Hourly total |
| Unique Users (1h) | Stat | PostgreSQL: `SELECT SUM(unique_users) FROM realtime_metrics WHERE window_start >= NOW() - INTERVAL '1 hour'` | Hourly users |
| Revenue (1h) | Stat | PostgreSQL: `SELECT SUM(revenue) FROM realtime_metrics WHERE window_start >= NOW() - INTERVAL '1 hour'` | Hourly revenue |
| Errors (1h) | Stat | PostgreSQL: `SELECT SUM(error_count) FROM realtime_metrics WHERE window_start >= NOW() - INTERVAL '1 hour'` | Hourly errors |

### 2. Processing Metrics

**File**: `grafana/dashboards/streaming-processing-metrics.json`  
**Focus**: Technical metrics for Spark, Flink, MinIO

#### Panels

| Panel | Type | Query | Purpose |
|-------|------|-------|---------|
| Spark Batch Latency | Time Series | `rate(spark_streaming_batch_processing_latency_sum[1m]) / rate(spark_streaming_batch_processing_latency_count[1m])` | Avg/Max batch latency |
| Spark Batch Records | Time Series | `spark_streaming_batch_input_records`, `spark_streaming_batch_output_records` | Input/output per batch |
| Flink Checkpoints | Time Series | `flink_jobmanager_job_last_checkpoint_duration`, `flink_jobmanager_job_last_checkpoint_size` | Checkpoint health |
| Flink Task Throughput | Time Series | `flink_taskmanager_job_task_numRecordsOutPerSecond` | Records/sec per task |
| MinIO Storage | Time Series | `minio_cluster_usage_total_bytes`, `minio_cluster_usage_free_bytes` | Storage usage |
| MinIO Request Rate | Time Series | `rate(minio_s3_requests_total[5m])` | S3 API rate by method/status |

## Creating Custom Dashboards

### Panel Types

| Type | Use Case |
|------|----------|
| **Time Series** | Metrics over time (throughput, latency) |
| **Stat** | Single current value (KPIs) |
| **Gauge** | Percentage with thresholds (CPU, memory) |
| **Table** | Tabular data (top pages, error details) |
| **Bar Gauge** | Comparative values |
| **Pie Chart** | Distribution (event types) |
| **Heatmap** | Latency distributions |
| **Logs** | Log aggregation |

### Query Examples

#### Prometheus (Time Series)

```promql
# Rate of events per second
rate(kafka_topic_partition_current_offset{topic="web-events"}[1m])

# Consumer lag by group
kafka_consumergroup_lag{topic="web-events"}

# Spark processing latency (seconds)
rate(spark_streaming_batch_processing_latency_sum[1m]) / rate(spark_streaming_batch_processing_latency_count[1m])

# Memory usage %
(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100
```

#### PostgreSQL (Time Series)

```sql
-- Events over time by page
SELECT 
    window_start as time,
    SUM(event_count) as value,
    page as metric
FROM realtime_metrics
WHERE window_start >= NOW() - INTERVAL '10 minutes'
GROUP BY window_start, page
ORDER BY window_start

-- Revenue over time
SELECT 
    window_start as time,
    SUM(revenue) as value
FROM realtime_metrics
WHERE window_start >= NOW() - INTERVAL '1 hour'
GROUP BY window_start
ORDER BY window_start
```

#### PostgreSQL (Stat)

```sql
-- Total events last hour
SELECT SUM(event_count) as total_events
FROM realtime_metrics
WHERE window_start >= NOW() - INTERVAL '1 hour'

-- Unique users last hour
SELECT SUM(unique_users) as total_users
FROM realtime_metrics
WHERE window_start >= NOW() - INTERVAL '1 hour'
```

#### PostgreSQL (Table)

```sql
-- Top pages by events
SELECT 
    page,
    SUM(event_count) as events,
    SUM(unique_users) as users,
    SUM(revenue) as revenue
FROM realtime_metrics
WHERE window_start >= NOW() - INTERVAL '1 hour'
GROUP BY page
ORDER BY events DESC
LIMIT 20
```

## Variables

### Template Variables

```json
{
  "templating": {
    "list": [
      {
        "name": "interval",
        "type": "interval",
        "label": "Time Interval",
        "default": "1m",
        "options": ["10s", "30s", "1m", "5m", "15m"]
      },
      {
        "name": "page",
        "type": "query",
        "label": "Page",
        "datasource": "PostgreSQL",
        "query": "SELECT DISTINCT page FROM realtime_metrics WHERE window_start >= NOW() - INTERVAL '1 hour' ORDER BY page",
        "includeAll": true,
        "multi": true
      },
      {
        "name": "event_type",
        "type": "query",
        "label": "Event Type",
        "datasource": "PostgreSQL",
        "query": "SELECT DISTINCT event_type FROM realtime_metrics WHERE window_start >= NOW() - INTERVAL '1 hour' ORDER BY event_type",
        "includeAll": true,
        "multi": true
      }
    ]
  }
}
```

### Using Variables

```promql
# In PromQL queries
rate(kafka_topic_partition_current_offset{topic="web-events"}[$interval])

# In PostgreSQL queries
WHERE page IN ($page) AND event_type IN ($event_type)
```

## Alerting in Grafana

### Alert Rules (Grafana 9+)

```yaml
# In dashboard JSON or provisioned
"alert": {
  "conditions": [
    {
      "evaluator": {"params": [10000], "type": "gt"},
      "operator": {"type": "and"},
      "query": {"params": ["A"]},
      "reducer": {"params": [], "type": "avg"},
      "type": "query"
    }
  ],
  "executionErrorState": "alerting",
  "frequency": "60s",
  "handler": 1,
  "name": "High Consumer Lag",
  "noDataState": "no_data",
  "notifications": []
}
```

### Contact Points

Configure in **Alerting** → **Contact Points**:
- Email
- Slack
- Webhook
- PagerDuty
- Opsgenie

## Dashboard Best Practices

### Design Principles

1. **Single Purpose**: Each dashboard answers specific questions
2. **Logical Grouping**: Related panels together
3. **Consistent Time Range**: Default to last 1h, allow override
4. **Meaningful Titles**: Clear panel titles with units
5. **Thresholds**: Color-code for quick status assessment
6. **Legends**: Descriptive series names

### Panel Configuration

```json
{
  "fieldConfig": {
    "defaults": {
      "unit": "ops",           // Unit for formatting
      "thresholds": {          // Color thresholds
        "mode": "absolute",
        "steps": [
          {"color": "green", "value": null},
          {"color": "yellow", "value": 70},
          {"color": "red", "value": 90}
        ]
      },
      "decimals": 2
    }
  },
  "options": {
    "legend": {
      "displayMode": "list",
      "placement": "bottom"
    },
    "tooltip": {
      "mode": "single"
    }
  }
}
```

### Units Reference

| Unit | Example |
|------|---------|
| `ops` | Operations/sec |
| `Bps` | Bytes/sec |
| `ms` | Milliseconds |
| `s` | Seconds |
| `percent` | 0-100% |
| `percentunit` | 0-1% |
| `short` | SI prefix (k, M, G) |
| `bytes` | Byte size |
| `currencyUSD` | $ amount |
| `dtduration` | Duration |

## Advanced Features

### Annotations

```json
{
  "annotations": {
    "list": [
      {
        "name": "Deployments",
        "datasource": "Prometheus",
        "enable": true,
        "iconColor": "rgba(0, 211, 255, 1)",
        "query": "deployment_timestamp"
      }
    ]
  }
}
```

### Dashboard Links

```json
{
  "links": [
    {
      "title": "Spark UI",
      "url": "http://localhost:8080",
      "targetBlank": true
    },
    {
      "title": "Flink UI",
      "url": "http://localhost:8081",
      "targetBlank": true
    }
  ]
}
```

### Row Panels (Collapsible Sections)

```json
{
  "type": "row",
  "title": "Kafka Metrics",
  "collapsed": false,
  "panels": [...]
}
```

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| **No data** | Check datasource connection, query syntax, time range |
| **Empty time series** | Verify metric names, label filters |
| **PostgreSQL error** | Check SSL mode, credentials, network |
| **Slow dashboard** | Reduce query range, add recording rules, limit series |
| **Permission denied** | Verify datasource permissions, user roles |

### Debugging Queries

```bash
# Test Prometheus query
curl -G 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=kafka_consumergroup_lag{topic="web-events"}'

# Test PostgreSQL query
docker exec -it postgres psql -U streaming_user -d streaming_metrics \
  -c "SELECT * FROM latest_metrics LIMIT 5;"

# Check Grafana logs
docker compose logs grafana
```

## Dashboard Import/Export

### Export

1. Dashboard → **Settings** → **JSON Model** → **Save to file**

### Import

1. **+** → **Import** → Upload JSON or paste URL
2. Select datasource mappings
3. **Import**

### Grafana.com Dashboards

Import community dashboards:
- **Kafka**: ID 12620
- **Spark**: ID 10965
- **Flink**: ID 11574
- **MinIO**: ID 13502
- **Node Exporter**: ID 1860
- **PostgreSQL**: ID 9628

```bash
# Import via API
curl -X POST http://admin:admin123@localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @dashboard.json
```

## Provisioning Dashboards (GitOps)

### Directory Structure

```
grafana/
├── datasources/
│   └── datasources.yml
└── dashboards/
    ├── dashboard-provider.yml
    ├── web-events-overview.json
    └── streaming-processing-metrics.json
```

### Version Control

```bash
# All dashboard changes in git
git add grafana/dashboards/
git commit -m "Update dashboard: add error rate panel"
```

### CI/CD

```yaml
# .github/workflows/grafana.yml
- name: Validate dashboards
  run: |
    for f in grafana/dashboards/*.json; do
      jq empty "$f" || exit 1
    done

- name: Deploy to Grafana
  run: |
    # Using grafana-operator or API
    curl -X POST ...
```

## Performance

### Query Optimization

1. **Use recording rules** for complex PromQL
2. **Limit time range** - avoid "All time"
3. **Reduce resolution** - `$__interval` variable
4. **Filter early** - label matchers first

### Dashboard Loading

```json
{
  "refresh": "10s",           // Auto-refresh
  "time": {
    "from": "now-1h",         // Default range
    "to": "now"
  },
  "timezone": "utc"           // Consistent timezone
}
```

## Access Control

### Organization & Teams

```yaml
# grafana.ini or env
[auth]
disable_login_form = false
disable_signout_menu = false

[auth.anonymous]
enabled = false
```

### Role-Based Access

| Role | Permissions |
|------|-------------|
| **Viewer** | View dashboards |
| **Editor** | Create/edit dashboards |
| **Admin** | Manage datasources, users, org |

### Folder Permissions

```
Streaming Pipeline (folder)
├── Web Events Overview (Editor: team-data)
├── Processing Metrics (Editor: team-platform)
└── Executive Summary (Viewer: team-mgmt)
```