# Alerting

## Overview

Alerting is configured at two levels: **Prometheus Alertmanager** for infrastructure and pipeline alerts, and **Grafana Alerting** for business metric thresholds.

## Prometheus Alerting

### Alert Rules

```yaml
# prometheus/rules/alerts.yml
groups:
  - name: streaming-alerts
    rules:
      # ==========================================
      # KAFKA ALERTS
      # ==========================================
      
      - alert: HighConsumerLag
        expr: kafka_consumergroup_lag{topic="web-events"} > 10000
        for: 5m
        labels:
          severity: warning
          component: kafka
          team: data-engineering
        annotations:
          summary: "High consumer lag on {{ $labels.consumergroup }}"
          description: |
            Consumer group {{ $labels.consumergroup }} on partition {{ $labels.partition }} 
            has lag of {{ $value | humanize }} messages.
            This indicates the consumer cannot keep up with the producer rate.
          runbook_url: "https://wiki.example.com/runbooks/kafka-high-lag"
      
      - alert: CriticalConsumerLag
        expr: kafka_consumergroup_lag{topic="web-events"} > 100000
        for: 2m
        labels:
          severity: critical
          component: kafka
          team: data-engineering
        annotations:
          summary: "Critical consumer lag on {{ $labels.consumergroup }}"
          description: |
            Consumer group {{ $labels.consumergroup }} is severely behind.
            Immediate action required - check consumer health and scale if needed.
      
      - alert: KafkaUnderReplicatedPartitions
        expr: kafka_server_replicamanager_under_replicated_partitions > 0
        for: 1m
        labels:
          severity: critical
          component: kafka
        annotations:
          summary: "Kafka under-replicated partitions detected"
          description: "{{ $value }} partitions are under-replicated. Risk of data loss if broker fails."
      
      - alert: KafkaOfflinePartitions
        expr: kafka_controller_kafkacontroller_offline_partitions_count > 0
        for: 30s
        labels:
          severity: critical
          component: kafka
        annotations:
          summary: "Kafka offline partitions detected"
          description: "{{ $value }} partitions have no leader. Producer/consumer requests will fail."
      
      - alert: KafkaBrokerDown
        expr: kafka_controller_kafkacontroller_active_broker_count < 3
        for: 1m
        labels:
          severity: critical
          component: kafka
        annotations:
          summary: "Kafka broker count below expected"
          description: "Only {{ $value }} brokers active (expected 3). Check broker health."
      
      - alert: KafkaDiskSpaceLow
        expr: (kafka_log_logsize_bytes / kafka_log_logdir_max_bytes) * 100 > 85
        for: 5m
        labels:
          severity: warning
          component: kafka
        annotations:
          summary: "Kafka disk usage above 85% on {{ $labels.instance }}"
      
      - alert: KafkaRequestLatencyHigh
        expr: histogram_quantile(0.99, rate(kafka_network_requestmetrics_request_latency_seconds_bucket[5m])) > 0.1
        for: 5m
        labels:
          severity: warning
          component: kafka
        annotations:
          summary: "Kafka P99 request latency > 100ms"

      # ==========================================
      # SPARK ALERTS
      # ==========================================
      
      - alert: SparkBatchLatencyHigh
        expr: (rate(spark_streaming_batch_processing_latency_sum[1m]) / rate(spark_streaming_batch_processing_latency_count[1m])) > 30
        for: 5m
        labels:
          severity: warning
          component: spark
        annotations:
          summary: "Spark batch latency exceeds 30 seconds"
          description: "Average batch processing time is {{ $value | humanizeDuration }}. Check for data skew or resource constraints."
      
      - alert: SparkBatchLatencyCritical
        expr: (rate(spark_streaming_batch_processing_latency_sum[1m]) / rate(spark_streaming_batch_processing_latency_count[1m])) > 60
        for: 2m
        labels:
          severity: critical
          component: spark
        annotations:
          summary: "Spark batch latency exceeds 60 seconds (trigger interval)"
          description: "Batches are taking longer than the trigger interval. Backlog will grow indefinitely."
      
      - alert: SparkExecutorMemoryHigh
        expr: (spark_executor_memory_used_bytes / spark_executor_memory_max_bytes) * 100 > 90
        for: 5m
        labels:
          severity: warning
          component: spark
        annotations:
          summary: "Spark executor memory usage above 90%"
          description: "Executor {{ $labels.executor_id }} on {{ $labels.instance }} at {{ $value | humanizePercentage }}. Risk of OOM."
      
      - alert: SparkExecutorLost
        expr: increase(spark_executor_lost_total[5m]) > 0
        for: 1m
        labels:
          severity: critical
          component: spark
        annotations:
          summary: "Spark executor lost"
          description: "Executor {{ $labels.executor_id }} lost. Check logs for OOM or network issues."
      
      - alert: SparkStreamingBackpressure
        expr: spark_streaming_backpressure_enabled == 1 and rate(spark_streaming_backpressure_ratio[5m]) > 0.5
        for: 5m
        labels:
          severity: warning
          component: spark
        annotations:
          summary: "Spark backpressure active"
          description: "Spark is rate-limiting ingestion due to processing delays."
      
      - alert: SparkJobFailed
        expr: increase(spark_job_failed_total[5m]) > 0
        for: 1m
        labels:
          severity: critical
          component: spark
        annotations:
          summary: "Spark job failed"
          description: "Job {{ $labels.job_id }} failed. Check Spark UI for details."

      # ==========================================
      # FLINK ALERTS
      # ==========================================
      
      - alert: FlinkCheckpointFailing
        expr: increase(flink_jobmanager_job_number_of_failed_checkpoints[5m]) > 0
        for: 2m
        labels:
          severity: critical
          component: flink
        annotations:
          summary: "Flink checkpoint failures detected"
          description: "Job {{ $labels.job_name }} has failing checkpoints. Exactly-once guarantees at risk."
      
      - alert: FlinkCheckpointSlow
        expr: flink_jobmanager_job_last_checkpoint_duration > 60000
        for: 5m
        labels:
          severity: warning
          component: flink
        annotations:
          summary: "Flink checkpoint duration exceeds 60 seconds"
          description: "Checkpoint taking {{ $value | humanizeDuration }}. May impact recovery time."
      
      - alert: FlinkCheckpointSizeLarge
        expr: flink_jobmanager_job_last_checkpoint_size > 10737418240
        for: 5m
        labels:
          severity: warning
          component: flink
        annotations:
          summary: "Flink checkpoint size exceeds 10GB"
          description: "Checkpoint size is {{ $value | humanizeBytes }}. Consider state TTL or cleanup."
      
      - alert: FlinkBackpressureHigh
        expr: flink_taskmanager_job_task_backpressure_ratio > 0.5
        for: 5m
        labels:
          severity: warning
          component: flink
        annotations:
          summary: "Flink task experiencing high backpressure"
          description: "Task {{ $labels.task_name }} backpressure ratio: {{ $value | humanizePercentage }}. Pipeline bottleneck."
      
      - alert: FlinkTaskFailover
        expr: increase(flink_taskmanager_job_task_restarting[5m]) > 0
        for: 1m
        labels:
          severity: critical
          component: flink
        annotations:
          summary: "Flink task failover detected"
          description: "Task {{ $labels.task_name }} restarted. Check task manager logs."
      
      - alert: FlinkJobNotRunning
        expr: flink_jobmanager_status_jobs_running == 0
        for: 1m
        labels:
          severity: critical
          component: flink
        annotations:
          summary: "No Flink jobs running"
          description: "Expected streaming job is not running. Check job manager."

      # ==========================================
      # MINIO ALERTS
      # ==========================================
      
      - alert: MinIODiskSpaceLow
        expr: (minio_cluster_usage_free_bytes / (minio_cluster_usage_total_bytes + minio_cluster_usage_free_bytes)) * 100 < 10
        for: 5m
        labels:
          severity: critical
          component: minio
        annotations:
          summary: "MinIO disk space below 10%"
          description: "Only {{ $value | humanizePercentage }} free. Add capacity or enable lifecycle policies."
      
      - alert: MinIODiskSpaceWarning
        expr: (minio_cluster_usage_free_bytes / (minio_cluster_usage_total_bytes + minio_cluster_usage_free_bytes)) * 100 < 20
        for: 10m
        labels:
          severity: warning
          component: minio
        annotations:
          summary: "MinIO disk space below 20%"
      
      - alert: MinIORequestErrorsHigh
        expr: rate(minio_s3_requests_total{status=~"5.."}[5m]) / rate(minio_s3_requests_total[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
          component: minio
        annotations:
          summary: "MinIO 5xx error rate above 5%"
          description: "{{ $value | humanizePercentage }} of requests failing with server errors."
      
      - alert: MinIONodeOffline
        expr: minio_cluster_nodes_online_total < 4
        for: 1m
        labels:
          severity: critical
          component: minio
        annotations:
          summary: "MinIO node offline"
          description: "Only {{ $value }} nodes online (expected 4). Quorum at risk."

      # ==========================================
      # POSTGRESQL ALERTS
      # ==========================================
      
      - alert: PostgresConnectionsHigh
        expr: (pg_stat_database_numbackends / pg_settings_max_connections) * 100 > 80
        for: 5m
        labels:
          severity: warning
          component: postgres
        annotations:
          summary: "PostgreSQL connections above 80%"
          description: "{{ $value | humanizePercentage }} of max connections in use. Consider PgBouncer."
      
      - alert: PostgresConnectionsCritical
        expr: (pg_stat_database_numbackends / pg_settings_max_connections) * 100 > 95
        for: 2m
        labels:
          severity: critical
          component: postgres
        annotations:
          summary: "PostgreSQL connections near exhaustion"
          description: "{{ $value | humanizePercentage }} used. New connections will be rejected."
      
      - alert: PostgresReplicationLag
        expr: pg_replication_lag_bytes > 1073741824
        for: 5m
        labels:
          severity: warning
          component: postgres
        annotations:
          summary: "PostgreSQL replication lag > 1GB"
          description: "Replica {{ $labels.replica }} lagging by {{ $value | humanizeBytes }}."
      
      - alert: PostgresDiskSpaceLow
        expr: (pg_database_size_bytes / pg_settings_max_disk_space) * 100 > 85
        for: 5m
        labels:
          severity: warning
          component: postgres
        annotations:
          summary: "PostgreSQL disk usage above 85%"
      
      - alert: PostgresLongRunningQuery
        expr: max by (pid) (time() - pg_stat_activity_query_start) > 300
        for: 5m
        labels:
          severity: warning
          component: postgres
        annotations:
          summary: "PostgreSQL query running > 5 minutes"
          description: "PID {{ $labels.pid }} running for {{ $value | humanizeDuration }}."

      # ==========================================
      # SYSTEM ALERTS
      # ==========================================
      
      - alert: HostMemoryHigh
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 90
        for: 5m
        labels:
          severity: warning
          component: system
        annotations:
          summary: "Host memory usage above 90% on {{ $labels.instance }}"
      
      - alert: HostMemoryCritical
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 95
        for: 2m
        labels:
          severity: critical
          component: system
        annotations:
          summary: "Host memory critical on {{ $labels.instance }}"
      
      - alert: HostCPUHigh
        expr: (100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)) > 90
        for: 10m
        labels:
          severity: warning
          component: system
        annotations:
          summary: "Host CPU usage above 90% on {{ $labels.instance }}"
      
      - alert: HostDiskFull
        expr: (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100 < 10
        for: 5m
        labels:
          severity: critical
          component: system
        annotations:
          summary: "Host disk space below 10% on {{ $labels.instance }}"
      
      - alert: HostNetworkErrors
        expr: rate(node_network_receive_errs_total[5m]) + rate(node_network_transmit_errs_total[5m]) > 10
        for: 5m
        labels:
          severity: warning
          component: system
        annotations:
          summary: "High network error rate on {{ $labels.instance }}"
      
      # ==========================================
      # BUSINESS ALERTS
      # ==========================================
      
      - alert: ZeroEventsReceived
        expr: rate(kafka_topic_partition_current_offset{topic="web-events"}[5m]) == 0
        for: 5m
        labels:
          severity: critical
          component: business
        annotations:
          summary: "No events received in 5 minutes"
          description: "Pipeline appears to be stalled. Check producer and Kafka."
      
      - alert: ErrorRateHigh
        expr: (sum(rate(realtime_metrics_error_count_total[5m])) / sum(rate(realtime_metrics_event_count_total[5m]))) * 100 > 5
        for: 5m
        labels:
          severity: warning
          component: business
        annotations:
          summary: "Error rate above 5%"
          description: "{{ $value | humanizePercentage }} of events are errors. Check error types in dashboard."
      
      - alert: RevenueDrop
        expr: sum(increase(realtime_metrics_revenue_total[1h])) < 100
        for: 30m
        labels:
          severity: warning
          component: business
        annotations:
          summary: "Revenue dropped below $100/hour"
          description: "Hourly revenue is ${{ $value }}. Check for tracking issues or real business impact."
      
      - alert: DataFreshness
        expr: time() - max(realtime_metrics_processed_at_timestamp) > 300
        for: 5m
        labels:
          severity: critical
          component: business
        annotations:
          summary: "Metrics data stale (> 5 minutes)"
          description: "Latest processed_at is {{ $value | humanizeDuration }} old. Pipeline may be down."
```

### Alertmanager Configuration

```yaml
# alertmanager/alertmanager.yml
global:
  resolve_timeout: 5m
  smtp_smarthost: 'smtp.example.com:587'
  smtp_from: 'alerts@example.com'
  smtp_auth_username: 'alerts@example.com'
  smtp_auth_password: '${SMTP_PASSWORD}'

route:
  group_by: ['alertname', 'component', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'critical-alerts'
      continue: true
    - match:
        component: business
      receiver: 'business-alerts'

receivers:
  - name: 'default'
    email_configs:
      - to: 'data-team@example.com'
        send_resolved: true
        html: '{{ template "email.default.html" . }}'
    slack_configs:
      - api_url: '${SLACK_WEBHOOK_URL}'
        channel: '#data-alerts'
        send_resolved: true
        title: '{{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
  
  - name: 'critical-alerts'
    pagerduty_configs:
      - service_key: '${PAGERDUTY_KEY}'
        severity: critical
        description: '{{ .GroupLabels.alertname }} - {{ .Annotations.summary }}'
    opsgenie_configs:
      - api_key: '${OPSGENIE_KEY}'
        responders:
          - name: 'data-oncall'
            type: 'team'
  
  - name: 'business-alerts'
    slack_configs:
      - api_url: '${SLACK_WEBHOOK_URL}'
        channel: '#business-metrics'
        send_resolved: true
    email_configs:
      - to: 'business-team@example.com'
        send_resolved: true

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'component']

templates:
  - '/etc/alertmanager/template/*.tmpl'
```

### Alert Templates

```gotemplate
# alertmanager/template/email.default.html
{{ define "email.default.html" }}
<!DOCTYPE html>
<html>
<head>
  <style>
    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
    .alert { padding: 20px; border-radius: 5px; margin: 10px 0; }
    .critical { background: #fee; border: 1px solid #fcc; }
    .warning { background: #ffe; border: 1px solid #fc0; }
    .info { background: #eef; border: 1px solid #ccf; }
    .labels { background: #f5f5f5; padding: 10px; border-radius: 3px; }
    .annotations { padding: 10px; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
    th { background: #f5f5f5; }
  </style>
</head>
<body>
  <h2>{{ .Status | title }}: {{ .GroupLabels.alertname }}</h2>
  
  <div class="alert {{ .GroupLabels.severity }}">
    <h3>{{ .Annotations.summary }}</h3>
    <div class="annotations">{{ .Annotations.description }}</div>
  </div>
  
  <h3>Labels</h3>
  <div class="labels">
    <table>
      {{ range $k, $v := .GroupLabels }}
      <tr><td><strong>{{ $k }}</strong></td><td>{{ $v }}</td></tr>
      {{ end }}
    </table>
  </div>
  
  {{ if gt (len .Alerts) 1 }}
  <h3>All Instances</h3>
  <table>
    <tr><th>Instance</th><th>Value</th><th>Started</th></tr>
    {{ range .Alerts }}
    <tr>
      <td>{{ index .Labels "instance" }}</td>
      <td>{{ .ValueString }}</td>
      <td>{{ .StartsAt.Format "2006-01-02 15:04:05" }}</td>
    </tr>
    {{ end }}
  </table>
  {{ end }}
  
  <p><small>Generated by Alertmanager at {{ .Alerts.Firing | len }} firing, {{ .Alerts.Resolved | len }} resolved</small></p>
</body>
</html>
{{ end }}
```

## Grafana Alerting

### Alert Rules (Dashboard-based)

```json
{
  "alert": {
    "name": "High Error Rate",
    "conditions": [
      {
        "type": "query",
        "evaluator": {"type": "gt", "params": [5]},
        "operator": {"type": "and"},
        "query": {"params": ["A", "5m", "now"]},
        "reducer": {"type": "avg", "params": []}
      }
    ],
    "executionErrorState": "alerting",
    "frequency": "60s",
    "handler": 1,
    "noDataState": "no_data",
    "notifications": []
  }
}
```

### Multi-dimensional Alerting

```yaml
# For alerting on multiple pages/event types
- alert: PageErrorRateHigh
  expr: |
    sum by (page) (rate(realtime_metrics_error_count_total[5m])) 
    / 
    sum by (page) (rate(realtime_metrics_event_count_total[5m])) * 100 > 10
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "High error rate on page {{ $labels.page }}"
```

## Notification Channels

### Slack

```yaml
slack_configs:
  - api_url: 'https://hooks.slack.com/services/XXX/YYY/ZZZ'
    channel: '#alerts'
    send_resolved: true
    title: '{{ .GroupLabels.alertname }} [{{ .Status }}]'
    text: |
      {{ range .Alerts }}
      *{{ .Annotations.summary }}*
      {{ .Annotations.description }}
      {{ end }}
    color: '{{ if eq .Status "firing" }}danger{{ else }}good{{ end }}'
    fields:
      - title: Severity
        value: '{{ .GroupLabels.severity }}'
        short: true
      - title: Component
        value: '{{ .GroupLabels.component }}'
        short: true
```

### PagerDuty

```yaml
pagerduty_configs:
  - service_key: '${PAGERDUTY_INTEGRATION_KEY}'
    severity: '{{ .GroupLabels.severity }}'
    description: '{{ .GroupLabels.alertname }}: {{ .Annotations.summary }}'
    details:
      component: '{{ .GroupLabels.component }}'
      runbook: '{{ .Annotations.runbook_url }}'
```

### Opsgenie

```yaml
opsgenie_configs:
  - api_key: '${OPSGENIE_API_KEY}'
    message: '{{ .GroupLabels.alertname }}: {{ .Annotations.summary }}'
    description: '{{ .Annotations.description }}'
    tags: ['{{ .GroupLabels.component }}', '{{ .GroupLabels.severity }}']
    priority: '{{ if eq .GroupLabels.severity "critical" }}P1{{ else }}P3{{ end }}'
    responders:
      - name: 'data-oncall'
        type: 'team'
```

### Webhook (Custom Integration)

```yaml
webhook_configs:
  - url: 'http://alert-handler:5000/webhook'
    http_config:
      basic_auth:
        username: 'alertmanager'
        password: '${WEBHOOK_PASSWORD}'
    send_resolved: true
```

## Alert Routing

### Time-based Routing

```yaml
route:
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'critical-pagerduty'
    - match:
        component: business
      receiver: 'business-slack'
    - match_re:
        alertname: '.*Batch.*'
      receiver: 'spark-team'
      continue: true
```

### Inhibition Rules

```yaml
inhibit_rules:
  # Inhibit warning if critical exists for same component
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['component', 'instance']
  
  # Inhibit Kafka alerts if broker down
  - source_match:
      alertname: 'KafkaBrokerDown'
    target_match_re:
      alertname: 'Kafka.*'
    equal: ['instance']
```

## Testing Alerts

### Prometheus Rule Testing

```bash
# Test rule syntax
docker run --rm -v $(pwd)/prometheus:/etc/prometheus \
  prom/prometheus:v2.48.0 promtool check rules /etc/prometheus/rules/*.yml

# Test with sample data
promtool test rules test.yml
```

### Alertmanager Testing

```bash
# Test configuration
docker run --rm -v $(pwd)/alertmanager:/etc/alertmanager \
  prom/alertmanager:v0.26.0 alertmanager --config.file=/etc/alertmanager/alertmanager.yml --check-config

# Send test alert
amtool alert add test_alert severity=critical component=test \
  --annotation=summary="Test alert" \
  --annotation=description="This is a test"
```

### Generator URL Testing

```bash
# Test webhook receiver
curl -X POST http://localhost:9093/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '[{
    "labels": {"alertname": "TestAlert", "severity": "critical"},
    "annotations": {"summary": "Test", "description": "Test alert"},
    "startsAt": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
  }]'
```

## Silencing Alerts

### Via Alertmanager UI

1. Open http://localhost:9093
2. Click **Silences** → **New Silence**
3. Configure matchers and duration

### Via CLI

```bash
# Silence for 1 hour
amtool silence add alertname=HighConsumerLag \
  --duration=1h \
  --comment="Planned maintenance"

# List silences
amtool silence query

# Expire silence
amtool silence expire <silence-id>
```

## Runbooks

### Template

```markdown
# Runbook: {{ Alert Name }}

## Symptoms
- {{ What triggers this alert }}
- {{ User-visible impact }}

## Diagnosis
1. Check {{ dashboard/component }}
2. Run `{{ diagnostic command }}`
3. Look for {{ specific log/error }}

## Resolution
1. {{ Step 1 }}
2. {{ Step 2 }}
3. {{ Verification }}

## Prevention
- {{ Long-term fix }}
- {{ Monitoring improvement }}

## Contacts
- Primary: {{ team/person }}
- Escalation: {{ manager/oncall }}
```

### Example Runbooks

```
runbooks/
├── kafka-high-lag.md
├── spark-batch-latency.md
├── flink-checkpoint-failing.md
├── minio-disk-space.md
└── postgres-connections.md
```

## Best Practices

1. **Alert on symptoms, not causes** - "High latency" not "GC pause"
2. **Set appropriate `for` duration** - Avoid flapping
3. **Use meaningful labels** - Enable routing and grouping
4. **Include runbook URLs** - Reduce MTTR
5. **Test alerts regularly** - Fire drill monthly
6. **Review and tune** - Remove noisy alerts
7. **Document everything** - Runbooks for every alert
8. **Separate concerns** - Infra vs business alerts
9. **Use inhibition** - Reduce notification noise
10. **Version control** - GitOps for alert rules