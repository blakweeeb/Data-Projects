# Prometheus Monitoring

## Overview

Prometheus collects and stores metrics from all pipeline components, enabling alerting and Grafana visualization.

## Configuration

### Prometheus.yml

```yaml
# prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'streaming-pipeline'
    environment: 'development'

alerting:
  alertmanagers:
    - static_configs:
        - targets: []

rule_files: []

scrape_configs:
  # Prometheus self-monitoring
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # Node Exporter (host metrics)
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

  # Kafka Exporter (consumer lag, topic metrics)
  - job_name: 'kafka-exporter'
    static_configs:
      - targets: ['kafka-exporter:9308']

  # Kafka JMX (broker metrics)
  - job_name: 'kafka-jmx'
    static_configs:
      - targets: ['kafka:9101']

  # Spark Master
  - job_name: 'spark-master'
    static_configs:
      - targets: ['spark-master:8080']
    metrics_path: '/metrics/prometheus/'

  # Spark Workers
  - job_name: 'spark-workers'
    static_configs:
      - targets: ['spark-worker-1:8080', 'spark-worker-2:8080']
    metrics_path: '/metrics/prometheus/'

  # Flink JobManager
  - job_name: 'flink-jobmanager'
    static_configs:
      - targets: ['flink-jobmanager:8081']
    metrics_path: '/metrics'

  # Flink TaskManagers
  - job_name: 'flink-taskmanagers'
    static_configs:
      - targets: ['flink-taskmanager:8081']
    metrics_path: '/metrics'

  # MinIO
  - job_name: 'minio'
    static_configs:
      - targets: ['minio:9000']
    metrics_path: '/minio/v2/metrics/cluster'

  # PostgreSQL (via postgres_exporter)
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  # Grafana
  - job_name: 'grafana'
    static_configs:
      - targets: ['grafana:3000']
    metrics_path: '/metrics'
```

### Service Discovery (Production)

```yaml
scrape_configs:
  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
        action: replace
        target_label: __metrics_path__
        regex: (.+)
      - source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]
        action: replace
        regex: ([^:]+)(?::\d+)?;(\d+)
        replacement: $1:$2
        target_label: __address__
```

## Scraped Components

### 1. Node Exporter (Host Metrics)

**Port**: 9100  
**Metrics**: CPU, memory, disk, network, filesystem

| Metric | Description |
|--------|-------------|
| `node_cpu_seconds_total` | CPU time by mode |
| `node_memory_MemTotal_bytes` | Total memory |
| `node_memory_MemAvailable_bytes` | Available memory |
| `node_filesystem_avail_bytes` | Disk space |
| `node_network_receive_bytes_total` | Network RX |
| `node_network_transmit_bytes_total` | Network TX |

### 2. Kafka Exporter

**Port**: 9308  
**Metrics**: Consumer lag, topic/partition offsets

| Metric | Description |
|--------|-------------|
| `kafka_consumergroup_lag` | Messages behind per partition |
| `kafka_consumergroup_current_offset` | Current consumer offset |
| `kafka_topic_partition_current_offset` | Latest topic offset |
| `kafka_topic_partition_oldest_offset` | Oldest retained offset |

### 3. Kafka JMX

**Port**: 9101  
**Metrics**: Broker-level metrics

| Metric | Description |
|--------|-------------|
| `kafka_server_brokertopicmetrics_messages_in_per_sec` | Incoming msg rate |
| `kafka_server_brokertopicmetrics_bytes_in_per_sec` | Incoming byte rate |
| `kafka_server_brokertopicmetrics_bytes_out_per_sec` | Outgoing byte rate |
| `kafka_server_replicamanager_under_replicated_partitions` | Under-replicated |
| `kafka_controller_kafkacontroller_active_broker_count` | Active brokers |

### 4. Spark Metrics

**Port**: 8080 (master), 8080 (workers)  
**Path**: `/metrics/prometheus/`

| Metric | Description |
|--------|-------------|
| `spark_streaming_batch_processing_latency` | Batch processing time |
| `spark_streaming_batch_input_records` | Records read |
| `spark_streaming_batch_output_records` | Records written |
| `spark_executor_memory_used_bytes` | Executor heap |
| `spark_executor_memory_max_bytes` | Executor max heap |
| `spark_executor_cpu_load` | CPU utilization |

### 5. Flink Metrics

**Port**: 8081 (JobManager), 8081 (TaskManagers)  
**Path**: `/metrics`

| Metric | Description |
|--------|-------------|
| `flink_jobmanager_job_last_checkpoint_duration` | Checkpoint time |
| `flink_jobmanager_job_last_checkpoint_size` | Checkpoint size |
| `flink_jobmanager_job_number_of_completed_checkpoints` | Success count |
| `flink_jobmanager_job_number_of_failed_checkpoints` | Failure count |
| `flink_taskmanager_job_task_numRecordsOutPerSecond` | Output throughput |
| `flink_taskmanager_job_task_backpressure_ratio` | Backpressure |
| `flink_taskmanager_job_task_idleTimeMsPerSecond` | Idle time |

### 6. MinIO Metrics

**Port**: 9000  
**Path**: `/minio/v2/metrics/cluster`

| Metric | Description |
|--------|-------------|
| `minio_cluster_usage_total_bytes` | Total used |
| `minio_cluster_usage_free_bytes` | Free space |
| `minio_cluster_objects_total` | Object count |
| `minio_s3_requests_total` | API requests |
| `minio_s3_request_duration_seconds` | Latency histogram |

### 7. PostgreSQL Exporter

**Port**: 9187 (if deployed)

| Metric | Description |
|--------|-------------|
| `pg_stat_database_xact_commit` | Commits |
| `pg_stat_database_xact_rollback` | Rollbacks |
| `pg_stat_database_blks_read` | Block reads |
| `pg_stat_database_blks_hit` | Block hits |
| `pg_database_size_bytes` | Database size |

## Prometheus UI

Access at http://localhost:9090

### Key Pages

| Page | URL | Purpose |
|------|-----|---------|
| **Graph** | `/graph` | Query & graph metrics |
| **Targets** | `/targets` | Scrape target health |
| **Alerts** | `/alerts` | Alert rules status |
| **Rules** | `/rules` | Recording/alerting rules |
| **Service Discovery** | `/service-discovery` | SD status |

### Useful Queries

```promql
# Kafka consumer lag
kafka_consumergroup_lag{topic="web-events"}

# Spark batch latency (avg)
rate(spark_streaming_batch_processing_latency_sum[1m]) / rate(spark_streaming_batch_processing_latency_count[1m])

# Flink checkpoint duration
flink_jobmanager_job_last_checkpoint_duration

# MinIO storage usage %
(minio_cluster_usage_total_bytes / (minio_cluster_usage_total_bytes + minio_cluster_usage_free_bytes)) * 100

# System memory usage %
(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100

# CPU usage %
100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
```

## Recording Rules

```yaml
# prometheus/rules/recording.yml
groups:
  - name: streaming-recording
    interval: 30s
    rules:
      # Kafka throughput
      - record: job:kafka:messages_per_second
        expr: sum(rate(kafka_topic_partition_current_offset{topic="web-events"}[1m])) by (job)
      
      # Spark batch latency (avg)
      - record: job:spark:batch_latency_avg_seconds
        expr: rate(spark_streaming_batch_processing_latency_sum[1m]) / rate(spark_streaming_batch_processing_latency_count[1m])
      
      # Flink throughput
      - record: job:flink:records_per_second
        expr: sum(rate(flink_taskmanager_job_task_numRecordsOutPerSecond[1m])) by (job)
      
      # System resources
      - record: instance:memory_usage_percent
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100
      
      - record: instance:cpu_usage_percent
        expr: 100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
```

Add to prometheus.yml:
```yaml
rule_files:
  - 'rules/*.yml'
```

## Alerting Rules

```yaml
# prometheus/rules/alerts.yml
groups:
  - name: streaming-alerts
    rules:
      # Kafka Alerts
      - alert: HighConsumerLag
        expr: kafka_consumergroup_lag{topic="web-events"} > 10000
        for: 5m
        labels:
          severity: warning
          component: kafka
        annotations:
          summary: "High consumer lag on {{ $labels.consumergroup }}"
          description: "Consumer group {{ $labels.consumergroup }} on partition {{ $labels.partition }} has lag of {{ $value }} messages"
      
      - alert: KafkaUnderReplicated
        expr: kafka_server_replicamanager_under_replicated_partitions > 0
        for: 1m
        labels:
          severity: critical
          component: kafka
        annotations:
          summary: "Kafka under-replicated partitions detected"
      
      - alert: KafkaBrokerDown
        expr: kafka_controller_kafkacontroller_active_broker_count < 3
        for: 1m
        labels:
          severity: critical
          component: kafka
        annotations:
          summary: "Kafka broker count below expected"

      # Spark Alerts
      - alert: SparkBatchLatencyHigh
        expr: (rate(spark_streaming_batch_processing_latency_sum[1m]) / rate(spark_streaming_batch_processing_latency_count[1m])) > 30
        for: 5m
        labels:
          severity: warning
          component: spark
        annotations:
          summary: "Spark batch latency exceeds 30 seconds"
      
      - alert: SparkExecutorMemoryHigh
        expr: (spark_executor_memory_used_bytes / spark_executor_memory_max_bytes) * 100 > 90
        for: 5m
        labels:
          severity: warning
          component: spark
        annotations:
          summary: "Spark executor memory usage above 90%"

      # Flink Alerts
      - alert: FlinkCheckpointFailing
        expr: increase(flink_jobmanager_job_number_of_failed_checkpoints[5m]) > 0
        for: 2m
        labels:
          severity: critical
          component: flink
        annotations:
          summary: "Flink checkpoint failures detected"
      
      - alert: FlinkCheckpointSlow
        expr: flink_jobmanager_job_last_checkpoint_duration > 60000
        for: 5m
        labels:
          severity: warning
          component: flink
        annotations:
          summary: "Flink checkpoint duration exceeds 60 seconds"
      
      - alert: FlinkBackpressureHigh
        expr: flink_taskmanager_job_task_backpressure_ratio > 0.5
        for: 5m
        labels:
          severity: warning
          component: flink
        annotations:
          summary: "Flink task experiencing high backpressure"

      # MinIO Alerts
      - alert: MinIODiskSpaceLow
        expr: (minio_cluster_usage_free_bytes / (minio_cluster_usage_total_bytes + minio_cluster_usage_free_bytes)) * 100 < 10
        for: 5m
        labels:
          severity: critical
          component: minio
        annotations:
          summary: "MinIO disk space below 10%"

      # System Alerts
      - alert: HostMemoryHigh
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 90
        for: 5m
        labels:
          severity: warning
          component: system
        annotations:
          summary: "Host memory usage above 90%"
      
      - alert: HostCPUHigh
        expr: (100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)) > 90
        for: 5m
        labels:
          severity: warning
          component: system
        annotations:
          summary: "Host CPU usage above 90%"
      
      - alert: HostDiskFull
        expr: (node_filesystem_avail_bytes / node_filesystem_size_bytes) * 100 < 10
        for: 5m
        labels:
          severity: critical
          component: system
        annotations:
          summary: "Host disk space below 10%"
```

## Alertmanager Configuration

```yaml
# alertmanager/alertmanager.yml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'component']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'default'

receivers:
  - name: 'default'
    email_configs:
      - to: 'team@example.com'
        send_resolved: true
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/XXX'
        channel: '#alerts'
        send_resolved: true
    webhook_configs:
      - url: 'http://webhook:5000/alert'

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['component']
```

## Federation (Multi-Cluster)

```yaml
# prometheus.yml (central)
scrape_configs:
  - job_name: 'federate'
    honor_labels: true
    metrics_path: '/federate'
    params:
      'match[]':
        - '{job=~".+"}'
    static_configs:
      - targets:
        - 'prometheus-dc1:9090'
        - 'prometheus-dc2:9090'
```

## Remote Write (Long-term Storage)

```yaml
# prometheus.yml
remote_write:
  - url: "http://thanos:10902/api/v1/receive"
    queue_config:
      capacity: 10000
      max_shards: 100
      min_shards: 1
    write_relabel_configs:
      - source_labels: [__name__]
        regex: 'go_.*|process_.*'
        action: drop
```

## Troubleshooting

### Targets Down

```bash
# Check target health
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.health!="up")'

# Common issues:
# - Target not reachable (network/firewall)
# - Wrong port/path
# - Service not exporting metrics
```

### High Cardinality

```bash
# Check label cardinality
curl -s http://localhost:9090/api/v1/label/__name__/values | jq '.data | length'

# Drop high-cardinality labels
# Add to scrape config:
metric_relabel_configs:
  - source_labels: [__name__]
    regex: '.*_bucket$'
    action: drop
```

### Storage Issues

```bash
# Check storage
curl -s http://localhost:9090/api/v1/status/tsdb | jq '.data'

# Compact blocks
curl -X POST http://localhost:9090/api/v1/admin/tsdb/compact
```

## Best Practices

1. **Use recording rules** for expensive queries
2. **Limit label cardinality** - avoid user_id, session_id as labels
3. **Set appropriate scrape intervals** - 15s default, 5s for critical
4. **Use federation** for multi-cluster
5. **Enable remote write** for long-term retention
6. **Monitor Prometheus itself** - self-scraping
7. **Version rule files** in git
8. **Test alerts** with `amtool`