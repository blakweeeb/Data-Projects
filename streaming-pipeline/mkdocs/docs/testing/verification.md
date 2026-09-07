# Verification Tests

## Overview

This guide covers verification procedures to validate the streaming pipeline is working correctly end-to-end.

## Pre-Flight Checks

### 1. Infrastructure Health

```bash
# Check all containers running
docker compose ps

# Verify no restarting containers
docker compose ps --filter "status=restarting"

# Check resource usage
docker stats --no-stream
```

### 2. Service Endpoints

```bash
# Kafka
docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092

# Zookeeper
docker exec zookeeper nc -z localhost 2181 && echo "OK"

# Spark Master UI
curl -s http://localhost:8080 | grep -q "Spark Master" && echo "OK"

# Flink UI
curl -s http://localhost:8081 | grep -q "Flink" && echo "OK"

# MinIO
curl -s http://localhost:9000/minio/health/live && echo "OK"

# PostgreSQL
docker exec postgres pg_isready -U streaming_user -d streaming_metrics && echo "OK"

# Prometheus
curl -s http://localhost:9090/-/healthy && echo "OK"

# Grafana
curl -s http://localhost:3000/api/health | grep -q "ok" && echo "OK"
```

### 3. Kafka Topics

```bash
# List topics
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092

# Verify web-events topic
docker exec kafka kafka-topics --describe --topic web-events --bootstrap-server localhost:9092

# Expected output:
# Topic: web-events	PartitionCount: 3	ReplicationFactor: 1	Configs:
# 	Topic: web-events	Partition: 0	Leader: 1	Replicas: 1	Isr: 1
# 	Topic: web-events	Partition: 1	Leader: 1	Replicas: 1	Isr: 1
# 	Topic: web-events	Partition: 2	Leader: 1	Replicas: 1	Isr: 1
```

### 4. MinIO Bucket

```bash
# Check bucket exists
docker exec minio mc ls minio/metrics

# Verify structure
docker exec minio mc ls minio/metrics/web-events-metrics/
```

### 5. PostgreSQL Schema

```bash
# Connect and verify
docker exec -it postgres psql -U streaming_user -d streaming_metrics -c "\dt"

# Expected tables:
# realtime_metrics

# Verify views
docker exec -it postgres psql -U streaming_user -d streaming_metrics -c "\dv"

# Expected views:
# latest_metrics, page_metrics, event_type_metrics

# Check indexes
docker exec -it postgres psql -U streaming_user -d streaming_metrics -c "\di"
```

## Producer Verification

### 1. Basic Production Test

```bash
cd producer
python producer.py --max-events 10 --bootstrap-servers localhost:9092

# Expected output:
# Starting producer for topic 'web-events' on localhost:9092
# Producing events every 200ms...
# Press Ctrl+C to stop
# Sent 10 events (errors: 0)
# Producer shutdown complete
```

### 2. Verify Events in Kafka

```bash
# Consume test events
docker exec -it kafka kafka-console-consumer \
  --topic web-events \
  --from-beginning \
  --max-messages 10 \
  --bootstrap-server localhost:9092 \
  --property print.key=true \
  --property key.separator=" | "

# Expected: JSON events with keys
```

### 3. Event Schema Validation

```bash
# Save sample event
docker exec -it kafka kafka-console-consumer \
  --topic web-events \
  --from-beginning \
  --max-messages 1 \
  --bootstrap-server localhost:9092 > /tmp/sample_event.json

# Validate with jq
cat /tmp/sample_event.json | jq '.'
```

Expected structure:
```json
{
  "event_id": "evt_1705312800000_1234",
  "timestamp": "2024-01-15T10:00:00Z",
  "user_id": "user_1234",
  "session_id": "session_5678",
  "page": "/products/electronics",
  "event_type": "page_view",
  "device_type": "desktop",
  "browser": "Chrome",
  "os": "Windows 11",
  "country": "US",
  ...
}
```

## Spark Streaming Verification

### 1. Submit Job

```bash
docker exec -it spark-master spark-submit \
  --master spark://spark-master:7077 \
  --deploy-mode cluster \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,\
org.apache.hadoop:hadoop-aws:3.3.4,\
com.amazonaws:aws-java-sdk-bundle:1.12.262,\
org.postgresql:postgresql:42.7.3 \
  /opt/spark-apps/structured_streaming.py
```

### 2. Verify Job Running

```bash
# Check Spark applications
curl -s http://localhost:8080/api/v1/applications | jq '.[] | {id: .id, name: .name, status: .attempts[0].completed}'

# Should show "WebEventsStreaming" with completed: false
```

### 3. Check Streaming Query

```bash
# Get streaming query status
curl -s http://localhost:8080/api/v1/applications/<app-id>/streaming | jq '.'

# Expected:
# {
#   "streamingQueries": [
#     {
#       "id": "...",
#       "name": "foreachBatch",
#       "status": "RUNNING",
#       "lastTrigger": {...}
#     }
#   ]
# }
```

### 4. Verify Batch Processing

```bash
# Follow logs
docker compose logs -f spark-master

# Look for:
# Batch 0: Written X records to MinIO
# Batch 0: Written X records to PostgreSQL
# Batch 1: Written X records to MinIO
# ...

# Or check Spark UI: http://localhost:8080
# Click on application → Streaming tab
```

### 5. Verify MinIO Output

```bash
# Wait for first batch (30-60 seconds), then check
docker exec minio mc ls minio/metrics/web-events-metrics/ --recursive

# Should see partitioned Parquet files
# year=2024/month=1/day=15/hour=10/minute=0/part-00000-xxx.parquet
```

### 6. Verify PostgreSQL Output

```bash
# Query latest metrics
docker exec -it postgres psql -U streaming_user -d streaming_metrics -c "
  SELECT window_start, page, event_type, event_count, unique_users 
  FROM latest_metrics 
  ORDER BY window_start DESC 
  LIMIT 20;
"

# Should show aggregated data
```

### 6. Query Parquet with Spark SQL

```bash
# Start Spark shell
docker exec -it spark-master spark-shell \
  --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 \
  --conf spark.hadoop.fs.s3a.endpoint=http://minio:9000 \
  --conf spark.hadoop.fs.s3a.access.key=minioadmin \
  --conf spark.hadoop.fs.s3a.secret.key=minioadmin123 \
  --conf spark.hadoop.fs.s3a.path.style.access=true

# In Spark shell:
val df = spark.read.parquet("s3a://metrics/web-events-metrics/")
df.show(20, false)
df.printSchema()

// Query
df.createOrReplaceTempView("metrics")
spark.sql("SELECT page, SUM(event_count) as total FROM metrics GROUP BY page ORDER BY total DESC").show()
```

## Flink Verification (Optional)

### 1. Build and Submit

```bash
cd flink_job
mvn clean package -DskipTests

docker cp target/web-events-flink-1.0.jar flink-jobmanager:/opt/flink/usrlib/

docker exec flink-jobmanager flink run \
  -d /opt/flink/usrlib/web-events-flink-1.0.jar \
  --kafka.bootstrap.servers kafka:29092 \
  --input.topic web-events \
  --output.topic web-events-aggregated \
  --group.id flink-web-events-consumer
```

### 2. Verify Job

```bash
# List jobs
docker exec flink-jobmanager flink list

# Expected: RUNNING job with name "Web Events Flink Streaming Job"
```

### 3. Check Output Topic

```bash
# Consume aggregated events
docker exec -it kafka kafka-console-consumer \
  --topic web-events-aggregated \
  --from-beginning \
  --max-messages 5 \
  --bootstrap-server localhost:9092
```

## Grafana Verification

### 1. Access Grafana

```bash
# Open browser
open http://localhost:3000

# Login: admin / admin123
```

### 2. Verify Dashboards

Navigate to **Dashboards** → **Streaming Pipeline** and verify:

- **Web Events Overview**: Shows business metrics
- **Processing Metrics**: Shows technical metrics

### 3. Verify Data Sources

Go to **Configuration** → **Data Sources** and test each:

| Data Source | Test |
|-------------|------|
| Prometheus | Should show "Data source is working" |
| PostgreSQL | Should show "Data source is working" |
| MinIO (S3) | Should show "Data source is working" |

### 4. Verify Panels

Each panel should show data (not "No data"):

- Kafka Throughput: Lines for each partition
- Consumer Lag: Near zero lines
- System Resources: Gauges with values
- Events per Page: Time series lines
- Events by Type: Time series lines
- KPI Stats: Numbers > 0

## Prometheus Verification

### 1. Check Targets

```bash
# All targets should be UP
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, instance: .labels.instance, health: .health}'

# Expected: All "health": "up"
```

### 2. Verify Key Metrics

```bash
# Kafka metrics
curl -s "http://localhost:9090/api/v1/query?query=kafka_consumergroup_lag{topic=\"web-events\"}" | jq '.data.result'

# Spark metrics
curl -s "http://localhost:9090/api/v1/query?query=spark_streaming_batch_input_records" | jq '.data.result'

# Flink metrics
curl -s "http://localhost:9090/api/v1/query?query=flink_jobmanager_job_last_checkpoint_duration" | jq '.data.result'

# MinIO metrics
curl -s "http://localhost:9090/api/v1/query?query=minio_cluster_usage_total_bytes" | jq '.data.result'

# System metrics
curl -s "http://localhost:9090/api/v1/query?query=node_memory_MemAvailable_bytes" | jq '.data.result'
```

## End-to-End Flow Test

### Complete Pipeline Test

```bash
#!/bin/bash
# test_pipeline.sh

set -e

echo "=== Starting Pipeline Verification ==="

# 1. Start producer for 30 seconds
echo "1. Producing test events..."
cd producer
timeout 30 python producer.py --bootstrap-servers localhost:9092 || true

# 2. Wait for processing
echo "2. Waiting for stream processing..."
sleep 45

# 3. Check Kafka lag
echo "3. Checking consumer lag..."
LAG=$(docker exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --group spark-streaming-consumer 2>/dev/null | \
  awk '/web-events/ {sum+=$6} END {print sum}')
echo "   Consumer lag: ${LAG:-0}"

# 4. Check MinIO
echo "4. Checking MinIO output..."
FILE_COUNT=$(docker exec minio mc ls minio/metrics/web-events-metrics/ --recursive | wc -l)
echo "   Parquet files: $FILE_COUNT"

# 5. Check PostgreSQL
echo "5. Checking PostgreSQL output..."
ROW_COUNT=$(docker exec postgres psql -U streaming_user -d streaming_metrics -t -c \
  "SELECT COUNT(*) FROM realtime_metrics WHERE window_start >= NOW() - INTERVAL '2 minutes';")
echo "   Metrics rows: $ROW_COUNT"

# 6. Check Grafana
echo "6. Checking Grafana..."
curl -s http://localhost:3000/api/dashboards/uid/web-events-overview | jq -r '.dashboard.title'

echo "=== Verification Complete ==="
echo "Lag: ${LAG:-0} | Files: $FILE_COUNT | Rows: $ROW_COUNT"

# Success criteria
if [ "${LAG:-9999}" -lt 1000 ] && [ "$FILE_COUNT" -gt 0 ] && [ "$ROW_COUNT" -gt 0 ]; then
    echo "✅ ALL CHECKS PASSED"
    exit 0
else
    echo "❌ SOME CHECKS FAILED"
    exit 1
fi
```

## Data Quality Checks

### 1. Schema Validation

```python
# validate_schema.py
import json

def validate_event(event):
    required = ["event_id", "timestamp", "user_id", "session_id", "page", "event_type"]
    for field in required:
        assert field in event, f"Missing required field: {field}"
        assert event[field] is not None, f"Null value for: {field}"
    
    # Validate timestamp format
    from datetime import datetime
    datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
    
    # Validate event_type
    valid_types = ["page_view", "click", "scroll", "add_to_cart", "purchase", ...]
    assert event["event_type"] in valid_types, f"Invalid event_type: {event['event_type']}"
    
    return True

# Test with sample
with open("/tmp/sample_event.json") as f:
    event = json.load(f)
    validate_event(event)
    print("✅ Schema valid")
```

### 2. Aggregation Correctness

```sql
-- Verify window aggregations
SELECT 
    window_start,
    page,
    event_type,
    event_count,
    -- Manual count verification
    (SELECT COUNT(*) FROM web_events_raw 
     WHERE timestamp >= window_start AND timestamp < window_end
     AND page = m.page AND event_type = m.event_type) as raw_count
FROM realtime_metrics m
WHERE window_start >= NOW() - INTERVAL '10 minutes'
ORDER BY window_start DESC
LIMIT 10;
```

### 3. Duplicate Detection

```sql
-- Check for duplicate windows
SELECT window_start, window_end, page, event_type, COUNT(*)
FROM realtime_metrics
GROUP BY window_start, window_end, page, event_type
HAVING COUNT(*) > 1;
```

### 4. Null Checks

```sql
-- Check for nulls in required columns
SELECT 
    COUNT(*) FILTER (WHERE window_start IS NULL) as null_window_start,
    COUNT(*) FILTER (WHERE page IS NULL) as null_page,
    COUNT(*) FILTER (WHERE event_type IS NULL) as null_event_type,
    COUNT(*) FILTER (WHERE event_count IS NULL) as null_event_count
FROM realtime_metrics
WHERE window_start >= NOW() - INTERVAL '1 hour';
```

## Performance Baseline

### Expected Metrics (Development)

| Metric | Target | Acceptable Range |
|--------|--------|------------------|
| Events/second (producer) | 5 | 4-6 |
| Consumer lag | < 100 | < 1000 |
| Batch processing time | < 5s | < 30s |
| End-to-end latency | ~30-60s | < 90s |
| MinIO write latency | < 1s | < 5s |
| PostgreSQL write latency | < 500ms | < 2s |
| Memory usage (Spark) | < 2GB | < 4GB |
| Memory usage (Flink) | < 2GB | < 4GB |

### Measurement Commands

```bash
# Producer rate
docker exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --group test-consumer | grep web-events

# Batch processing time (from Spark UI or logs)
# Look for: "Batch X: processing took Y ms"

# End-to-end latency
# Compare event timestamp vs processed_at in PostgreSQL
docker exec postgres psql -U streaming_user -d streaming_metrics -c "
  SELECT 
    AVG(EXTRACT(EPOCH FROM (processed_at - window_end))) as avg_latency_sec,
    MAX(EXTRACT(EPOCH FROM (processed_at - window_end))) as max_latency_sec
  FROM realtime_metrics
  WHERE processed_at >= NOW() - INTERVAL '10 minutes';
"
```

## Automated Testing

### CI/CD Integration

```yaml
# .github/workflows/verify.yml
name: Pipeline Verification

on:
  push:
    branches: [main]
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Start stack
        run: docker compose up -d --build
        
      - name: Wait for services
        run: |
          sleep 60
          docker compose ps
          
      - name: Run producer
        run: |
          cd producer
          pip install -r requirements.txt
          timeout 60 python producer.py --bootstrap-servers localhost:9092 || true
          
      - name: Submit Spark job
        run: |
          docker exec -it spark-master spark-submit \
            --master spark://spark-master:7077 \
            --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,\
            org.apache.hadoop:hadoop-aws:3.3.4,\
            com.amazonaws:aws-java-sdk-bundle:1.12.262,\
            org.postgresql:postgresql:42.7.3 \
            /opt/spark-apps/structured_streaming.py &
          
      - name: Wait for processing
        run: sleep 90
        
      - name: Verify output
        run: |
          # Check MinIO
          FILES=$(docker exec minio mc ls minio/metrics/web-events-metrics/ --recursive | wc -l)
          if [ $FILES -eq 0 ]; then exit 1; fi
          
          # Check PostgreSQL
          ROWS=$(docker exec postgres psql -U streaming_user -d streaming_metrics -t -c \
            "SELECT COUNT(*) FROM realtime_metrics WHERE window_start >= NOW() - INTERVAL '5 minutes';")
          if [ $ROWS -eq 0 ]; then exit 1; fi
          
          # Check lag
          LAG=$(docker exec kafka kafka-consumer-groups \
            --bootstrap-server localhost:9092 \
            --describe --group spark-streaming-consumer 2>/dev/null | \
            awk '/web-events/ {sum+=$6} END {print sum}')
          if [ ${LAG:-9999} -gt 1000 ]; then exit 1; fi
          
      - name: Cleanup
        if: always()
        run: docker compose down -v
```