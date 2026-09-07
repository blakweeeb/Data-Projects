# Latency Testing

## Overview

This guide covers measuring and validating end-to-end latency in the streaming pipeline, from event generation to dashboard visualization.

## Latency Components

```
Producer          Kafka           Spark/Flink          Storage          Dashboard
   │                │                  │                  │                │
   ▼                ▼                  ▼                  ▼                ▼
Generate        Produce           Consume +            Write +          Query +
Timestamp       to Kafka          Process              Commit           Render
   │                │                  │                  │                │
   └────────────────┴──────────────────┴─────────────────┴────────────────┘
                              │
                              ▼
                    END-TO-END LATENCY
                    (event.timestamp → dashboard render)
```

### Latency Breakdown

| Stage | Typical Latency | Max Acceptable |
|-------|-----------------|----------------|
| Producer → Kafka | 1-10 ms | 50 ms |
| Kafka → Consumer | 10-50 ms | 100 ms |
| Processing (window) | 30-60 s | 90 s |
| Sink Write | 100-500 ms | 2 s |
| Dashboard Query | 100-500 ms | 1 s |
| **Total** | **30-60 s** | **90 s** |

> **Note**: Window duration (1 minute) dominates latency. Events wait for window to close.

## Measuring Latency

### 1. Producer-Side Timestamp Injection

Modify producer to inject precise timestamp:

```python
# In producer.py generate_event()
import time

event = {
    # ... existing fields
    "produce_timestamp_ns": time.time_ns(),  # Nanosecond precision
    "produce_timestamp_ms": int(time.time() * 1000),
}
```

### 2. Consumer-Side Processing Timestamp

Spark/Flink adds `processed_at` to each aggregated record.

```python
# In Spark foreachBatch
processed_at = current_timestamp()  # Added to each row
```

### 3. End-to-End Latency Query

```sql
-- PostgreSQL: Compare event window vs processing time
SELECT 
    window_start,
    window_end,
    page,
    event_type,
    event_count,
    processed_at,
    EXTRACT(EPOCH FROM (processed_at - window_end)) as latency_seconds
FROM realtime_metrics
WHERE window_start >= NOW() - INTERVAL '10 minutes'
ORDER BY window_start DESC;
```

### 4. Automated Latency Measurement

```python
# measure_latency.py
import time
import json
from datetime import datetime
from confluent_kafka import Producer, Consumer
import psycopg2

KAFKA_BOOTSTRAP = "localhost:9092"
TOPIC = "web-events"

def measure_latency(num_events=100, interval_ms=200):
    """Measure end-to-end latency by injecting trace events."""
    
    trace_id = f"latency_test_{int(time.time() * 1000)}"
    produced_times = {}
    
    # Producer with trace IDs
    producer = Producer({'bootstrap.servers': KAFKA_BOOTSTRAP})
    
    def delivery_report(err, msg):
        if err is None:
            key = msg.key().decode('utf-8')
            produced_times[key] = time.time_ns()
    
    # Produce trace events
    print(f"Producing {num_events} trace events...")
    for i in range(num_events):
        event = {
            "event_id": f"{trace_id}_{i}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_id": f"latency_test_user_{i}",
            "session_id": f"latency_test_session_{i}",
            "page": "/latency-test",
            "event_type": "page_view",
            "trace_id": trace_id,
            "sequence": i,
            "produce_ns": time.time_ns()
        }
        
        producer.produce(
            TOPIC,
            key=event["user_id"].encode('utf-8'),
            value=json.dumps(event).encode('utf-8'),
            callback=delivery_report
        )
        producer.poll(0)
        time.sleep(interval_ms / 1000.0)
    
    producer.flush()
    print("Trace events produced. Waiting for processing...")
    
    # Wait for processing (window + trigger)
    wait_time = 90  # 1 min window + 30 sec trigger
    print(f"Waiting {wait_time} seconds for window to close...")
    time.sleep(wait_time)
    
    # Query PostgreSQL for results
    conn = psycopg2.connect(
        host="localhost", port=5432,
        database="streaming_metrics",
        user="streaming_user", password="streaming_pass"
    )
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT window_start, window_end, page, event_type, event_count, processed_at
        FROM realtime_metrics
        WHERE page = '/latency-test' AND window_start >= NOW() - INTERVAL '2 minutes'
        ORDER BY window_start
    """)
    
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if not results:
        print("❌ No results found in PostgreSQL")
        return
    
    # Calculate latencies
    latencies = []
    for row in results:
        window_start, window_end, page, event_type, event_count, processed_at = row
        
        # Latency from window end to processing
        latency = (processed_at - window_end).total_seconds()
        latencies.append(latency)
        
        print(f"Window: {window_start} - {window_end} | Events: {event_count} | Latency: {latency:.2f}s")
    
    # Statistics
    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)
    min_latency = min(latencies)
    
    print(f"\n📊 Latency Statistics (n={len(latencies)} windows):")
    print(f"   Average: {avg_latency:.2f}s")
    print(f"   Min:     {min_latency:.2f}s")
    print(f"   Max:     {max_latency:.2f}s")
    print(f"   Target:  < 90s (window + trigger)")
    
    if max_latency < 90:
        print("✅ Latency within acceptable range")
    else:
        print("⚠️  Latency exceeds target")

if __name__ == "__main__":
    measure_latency(50, 200)
```

Run:
```bash
python measure_latency.py
```

## Kafka Consumer Lag as Latency Proxy

Consumer lag directly correlates with processing latency.

### Measuring Lag

```bash
# Real-time lag monitoring
docker exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --group spark-streaming-consumer

# Output interpretation:
# TOPIC           PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG
# web-events      0          1500            1500            0
# web-events      1          1498            1500            2
# web-events      2          1500            1500            0
```

### Prometheus Query for Lag

```promql
# Current lag per partition
kafka_consumergroup_lag{topic="web-events"}

# Max lag across partitions
max by (consumergroup) (kafka_consumergroup_lag{topic="web-events"})

# Lag trend (increasing = falling behind)
rate(kafka_consumergroup_lag{topic="web-events"}[5m])
```

### Lag to Latency Conversion

```python
# Approximate latency from lag
# If producing 5 events/sec and lag = 1000 messages:
# latency ≈ lag / produce_rate = 1000 / 5 = 200 seconds

produce_rate = 5  # events/sec
lag = 1000  # messages
estimated_latency = lag / produce_rate  # 200 seconds
```

## Spark Streaming Latency Metrics

### Batch Processing Latency

```promql
# Average batch processing time
rate(spark_streaming_batch_processing_latency_sum[1m]) 
/ rate(spark_streaming_batch_processing_latency_count[1m])

# Max batch processing time
max by (application) (spark_streaming_batch_processing_latency_max)

# Batch scheduling delay (time from trigger to start)
rate(spark_streaming_batch_scheduling_delay_sum[1m]) 
/ rate(spark_streaming_batch_scheduling_delay_count[1m])
```

### End-to-End Latency (Event Time)

```promql
# If Spark exposes event-time metrics
# (requires custom metric in Spark job)
spark_streaming_event_time_latency_seconds
```

## Flink Latency Metrics

### Checkpoint Duration

```promql
# Last checkpoint duration (ms)
flink_jobmanager_job_last_checkpoint_duration

# Checkpoint alignment time (part of checkpoint)
flink_jobmanager_job_last_checkpoint_alignment_duration
```

### Processing Latency

```promql
# Task latency (if latency tracking enabled)
flink_taskmanager_job_task_latency_mean

# Records processing latency
rate(flink_taskmanager_job_task_latency_sum[1m]) 
/ rate(flink_taskmanager_job_task_latency_count[1m])
```

### Enable Flink Latency Tracking

```java
// In Flink job
env.getConfig().setLatencyTrackingInterval(5000); // Track every 5s

// Or via metrics
metrics.reporter.slf4j.class: org.apache.flink.metrics.slf4j.Slf4jReporter
metrics.reporter.slf4j.interval: 60 SECONDS
```

## Dashboard Latency

### Grafana Query Latency

```bash
# Time dashboard queries
curl -w "\nDNS: %{time_namelookup}s\nConnect: %{time_connect}s\nTTFB: %{time_starttransfer}s\nTotal: %{time_total}s\n" \
  -o /dev/null -s "http://localhost:3000/api/ds/query"
```

### Panel Refresh Impact

```json
{
  "refresh": "10s",  // Dashboard auto-refresh
  "time": {
    "from": "now-1h",  // Query range affects latency
    "to": "now"
  }
}
```

## Latency Budget Validation

### Test Script

```bash
#!/bin/bash
# validate_latency.sh

set -e

echo "=== Latency Budget Validation ==="

# 1. Start fresh producer burst
echo "1. Sending latency trace events..."
cd producer
python producer.py --max-events 50 --interval 100 --bootstrap-servers localhost:9092 2>&1 | tail -3

# 2. Wait for full window + trigger
echo "2. Waiting for window processing (90s)..."
sleep 90

# 3. Measure PostgreSQL latency
echo "3. Measuring PostgreSQL latency..."
docker exec postgres psql -U streaming_user -d streaming_metrics -c "
  SELECT 
    AVG(EXTRACT(EPOCH FROM (processed_at - window_end))) as avg_latency_sec,
    MIN(EXTRACT(EPOCH FROM (processed_at - window_end))) as min_latency_sec,
    MAX(EXTRACT(EPOCH FROM (processed_at - window_end))) as max_latency_sec,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (processed_at - window_end))) as p50_latency_sec,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (processed_at - window_end))) as p95_latency_sec,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (processed_at - window_end))) as p99_latency_sec
  FROM realtime_metrics
  WHERE page = '/latency-test' 
  AND window_start >= NOW() - INTERVAL '2 minutes';
"

# 4. Check Kafka lag
echo "4. Checking Kafka consumer lag..."
docker exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --group spark-streaming-consumer | grep web-events

# 5. Check Prometheus metrics
echo "5. Prometheus latency metrics..."
curl -s "http://localhost:9090/api/v1/query?query=rate(spark_streaming_batch_processing_latency_sum[1m])/rate(spark_streaming_batch_processing_latency_count[1m])" | jq '.data.result[0].value[1]'

echo "=== Validation Complete ==="
```

## Latency Optimization

### If Latency Too High

| Bottleneck | Solution |
|------------|----------|
| **Kafka produce latency** | Reduce `linger.ms`, increase `batch.size`, use compression |
| **Consumer lag** | Increase consumer parallelism, optimize processing |
| **Spark batch time** | Reduce shuffle partitions, increase executor resources |
| **Window duration** | Use smaller windows (tumbling 30s instead of sliding 1m) |
| **Sink write latency** | Batch writes, use async sinks, connection pooling |
| **Dashboard query** | Add recording rules, materialized views, indexes |

### Configuration Tuning

```python
# Spark: Reduce trigger interval for lower latency
.trigger(processingTime="10 seconds")  # vs 30s default

# Spark: Reduce watermark for faster results
.withWatermark("event_timestamp", "30 seconds")  # vs 2 min

# Kafka: Low latency producer
producer_config = {
    'linger.ms': 1,
    'batch.size': 1024,
    'compression.type': 'none',  # or 'lz4' for speed
}

# Flink: Lower checkpoint interval
env.enableCheckpointing(10000)  # 10s vs 30s
```

### Window Trade-offs

| Window Type | Latency | Throughput | Complexity |
|-------------|---------|------------|------------|
| Tumbling 10s | ~10s | Lower | Simple |
| Tumbling 30s | ~30s | Medium | Simple |
| Sliding 1m/30s | ~60s | High | Medium |
| Session | Variable | High | Complex |

## Continuous Latency Monitoring

### Prometheus Recording Rules

```yaml
# prometheus/rules/latency.yml
groups:
  - name: latency-recording
    interval: 30s
    rules:
      - record: job:pipeline:e2e_latency_avg_seconds
        expr: |
          avg by (job) (
            time() - max by (job, window_start) (realtime_metrics_processed_at_timestamp)
          )
      
      - record: job:kafka:produce_latency_ms
        expr: histogram_quantile(0.99, rate(kafka_producer_record_send_latency_seconds_bucket[1m])) * 1000
      
      - record: job:spark:batch_latency_p99_seconds
        expr: histogram_quantile(0.99, rate(spark_streaming_batch_processing_latency_seconds_bucket[1m]))
```

### Grafana Latency Panel

```json
{
  "title": "End-to-End Latency",
  "type": "timeseries",
  "targets": [
    {
      "expr": "job:pipeline:e2e_latency_avg_seconds",
      "legendFormat": "Avg Latency",
      "refId": "A"
    },
    {
      "expr": "job:kafka:produce_latency_ms / 1000",
      "legendFormat": "Kafka Produce",
      "refId": "B"
    },
    {
      "expr": "job:spark:batch_latency_p99_seconds",
      "legendFormat": "Spark Batch P99",
      "refId": "C"
    }
  ],
  "fieldConfig": {
    "defaults": {
      "unit": "s",
      "thresholds": {
        "steps": [
          {"color": "green", "value": null},
          {"color": "yellow", "value": 60},
          {"color": "red", "value": 90}
        ]
      }
    }
  }
}
```

## Latency SLOs

### Service Level Objectives

| Metric | SLO | Target | Measurement |
|--------|-----|--------|-------------|
| End-to-end latency (p50) | < 60s | 99% | PostgreSQL `processed_at - window_end` |
| End-to-end latency (p99) | < 90s | 99% | PostgreSQL `processed_at - window_end` |
| Kafka produce latency (p99) | < 50ms | 99.9% | Producer metrics |
| Spark batch latency (p99) | < 30s | 99% | Spark metrics |
| Consumer lag (p99) | < 1000 | 99% | Kafka Exporter |
| Dashboard query latency (p95) | < 500ms | 99% | Grafana metrics |

### Alerting on SLO Violations

```yaml
- alert: E2ELatencySLOViolation
  expr: job:pipeline:e2e_latency_avg_seconds > 90
  for: 5m
  labels:
    severity: critical
    slo: e2e_latency
  annotations:
    summary: "End-to-end latency SLO violated"
    description: "Average latency {{ $value | humanizeDuration }} exceeds 90s target"
```