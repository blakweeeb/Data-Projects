# Quick Start

## 1. Start the Stack

```bash
# Navigate to project directory
cd streaming-pipeline

# Start all services (pulls images on first run ~3GB)
docker compose up -d --build

# Verify all containers are running
docker compose ps
```

Expected output:
```
NAME                 IMAGE                                    STATUS
grafana              grafana/grafana:10.2.2                   Up
kafka                confluentinc/cp-kafka:7.5.0              Up (healthy)
kafka-exporter       danielqsj/kafka-exporter:v1.7.0          Up
kafka-topic-creator  confluentinc/cp-kafka:7.5.0              Exited (0)
minio                minio/minio:RELEASE.2024-01-16T16-07-38Z  Up (healthy)
minio-bucket-creator minio/mc:RELEASE.2024-01-16T16-07-38Z    Exited (0)
node-exporter        prom/node-exporter:v1.7.0                Up
postgres             postgres:16-alpine                       Up (healthy)
prometheus           prom/prometheus:v2.48.0                  Up
spark-master         bitnami/spark:3.5.0                      Up
spark-worker-1       bitnami/spark:3.5.0                      Up
spark-worker-2       bitnami/spark:3.5.0                      Up
zookeeper            confluentinc/cp-zookeeper:7.5.0          Up (healthy)
```

> **Note**: `kafka-topic-creator` and `minio-bucket-creator` exit after completing their initialization tasks. This is expected.

## 2. Verify Services

| Service | URL | Credentials | Health Check |
|---------|-----|-------------|--------------|
| **Grafana** | http://localhost:3000 | admin / admin123 | http://localhost:3000/api/health |
| **Prometheus** | http://localhost:9090 | - | http://localhost:9090/-/healthy |
| **Spark Master UI** | http://localhost:8080 | - | http://localhost:8080 |
| **Flink Web UI** | http://localhost:8081 | - | http://localhost:8081 |
| **MinIO Console** | http://localhost:9001 | minioadmin / minioadmin123 | http://localhost:9001/minio/health/live |
| **Kafka** | localhost:9092 | - | `docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092` |

### Quick Health Checks

```bash
# Check Kafka
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092
# Should show: web-events, web-events-dlq

# Check MinIO bucket
docker exec minio mc ls minio/metrics

# Check PostgreSQL
docker exec postgres psql -U streaming_user -d streaming_metrics -c "\dt"
# Should show: realtime_metrics

# Check Prometheus targets
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'
```

## 3. Run the Producer

### Install Dependencies

```bash
cd producer
python3.11 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

### Run Producer

```bash
# Create topic and start producing (5 events/sec)
python producer.py --create-topic

# Or with custom settings
python producer.py --interval 100 --max-events 50000
```

Expected output:
```
Starting producer for topic 'web-events' on localhost:9092
Producing events every 200ms...
Press Ctrl+C to stop

Sent 1000 events (errors: 0)
Sent 2000 events (errors: 0)
...
```

### Producer Options

```bash
python producer.py --help

# Options:
#   --bootstrap-servers    Kafka servers (default: localhost:9092)
#   --topic                Topic name (default: web-events)
#   --interval             Ms between events (default: 200)
#   --max-events           Stop after N events
#   --create-topic         Create topic before producing
```

## 4. Start Spark Streaming Job

### Submit Job

```bash
docker exec -it spark-master spark-submit \
  --master spark://spark-master:7077 \
  --deploy-mode cluster \
  --conf spark.sql.streaming.checkpointLocation=s3a://metrics/checkpoints \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,\
org.apache.hadoop:hadoop-aws:3.3.4,\
com.amazonaws:aws-java-sdk-bundle:1.12.262,\
org.postgresql:postgresql:42.7.3 \
  /opt/spark-apps/structured_streaming.py
```

### Verify Job Running

```bash
# Check Spark applications
curl -s http://localhost:8080/api/v1/applications | jq '.[] | {id: .id, name: .name, status: .attempts[0].sparkUser}'

# Check streaming query in Spark UI
# Open http://localhost:8080 and click on the running application
```

### Expected Logs

```bash
# Follow Spark logs
docker compose logs -f spark-master

# Look for:
# "Streaming query started. Waiting for termination..."
# "Batch 0: Written X records to MinIO"
# "Batch 0: Written X records to PostgreSQL"
```

## 5. (Optional) Start Flink Job

### Build Flink Job

```bash
cd flink_job
mvn clean package -DskipTests
```

### Submit to Flink

```bash
# Copy jar to Flink container
docker cp target/web-events-flink-1.0.jar flink-jobmanager:/opt/flink/usrlib/

# Submit job
docker exec flink-jobmanager flink run \
  -d /opt/flink/usrlib/web-events-flink-1.0.jar \
  --kafka.bootstrap.servers kafka:29092 \
  --input.topic web-events \
  --output.topic web-events-aggregated \
  --group.id flink-web-events-consumer
```

### Verify Flink Job

```bash
# Check running jobs
docker exec flink-jobmanager flink list

# Check job details
docker exec flink-jobmanager flink info <job-id>
```

## 6. View Grafana Dashboards

### Access Grafana

1. Open http://localhost:3000
2. Login: **admin** / **admin123**
3. Navigate to **Dashboards** → **Streaming Pipeline**
4. Select:
   - **Web Events Overview** - Business metrics
   - **Processing Metrics** - Technical metrics

### Dashboard Overview

#### Web Events Overview
- **Kafka Throughput**: Messages/sec per partition
- **Consumer Lag**: Real-time lag monitoring
- **System Resources**: CPU, Memory, Network
- **Events per Page**: Time series by page
- **Events by Type**: Time series by event type
- **KPIs**: Total events, Unique users, Revenue, Errors (1h)

#### Processing Metrics
- **Spark Batch Latency**: Avg/Max processing time
- **Spark Batch Records**: Input/Output per batch
- **Flink Checkpoints**: Duration and size
- **Flink Task Throughput**: Records/sec per task
- **MinIO Storage**: Usage and request rates

## 7. Validate End-to-End

### Check MinIO Parquet Files

```bash
# Start Spark shell with MinIO config
docker exec -it spark-master spark-shell \
  --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 \
  --conf spark.hadoop.fs.s3a.endpoint=http://minio:9000 \
  --conf spark.hadoop.fs.s3a.access.key=minioadmin \
  --conf spark.hadoop.fs.s3a.secret.key=minioadmin123 \
  --conf spark.hadoop.fs.s3a.path.style.access=true

# In Spark shell:
val df = spark.read.parquet("s3a://metrics/web-events-metrics/")
df.show()
df.printSchema()
```

### Check PostgreSQL Data

```bash
docker exec -it postgres psql -U streaming_user -d streaming_metrics

-- View latest metrics
SELECT * FROM latest_metrics LIMIT 20;

-- View page aggregates
SELECT * FROM page_metrics;

-- View event type aggregates
SELECT * FROM event_type_metrics;
```

### Check Consumer Lag

```bash
docker exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --group spark-streaming-consumer
```

Expected: Lag should be low (< 1000) under normal load.

## 8. Stop the Stack

```bash
# Stop and remove containers (preserves volumes)
docker compose down

# Stop and remove everything including volumes
docker compose down -v

# Stop only (preserves state)
docker compose stop
```

## Troubleshooting Quick Reference

| Issue | Solution |
|-------|----------|
| Containers won't start | `docker compose logs <service>` |
| Kafka not ready | Wait for healthcheck, check Zookeeper |
| Spark job fails | Check Spark UI at :8080, increase memory |
| MinIO access denied | Verify bucket exists, check credentials |
| PostgreSQL connection failed | Check init.sql ran, verify credentials |
| Grafana dashboards empty | Check datasource config, Prometheus targets |
| High consumer lag | Increase Spark/Flink parallelism |

## Next Steps

- [Configuration](configuration.md) - Customize the pipeline
- [Components](../architecture/components.md) - Deep dive into each component
- [Monitoring](../monitoring/prometheus.md) - Set up alerting
- [Testing](../testing/verification.md) - Validate data quality