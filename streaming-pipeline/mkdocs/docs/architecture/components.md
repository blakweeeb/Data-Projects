# Components

## Apache Kafka

### Overview
Apache Kafka serves as the central message backbone for the streaming pipeline. It provides durable, ordered, and scalable event streaming.

### Configuration (docker-compose.yml)

```yaml
kafka:
  image: confluentinc/cp-kafka:7.5.0
  environment:
    KAFKA_BROKER_ID: 1
    KAFKA_ZOOKEEPER_CONNECT: 'zookeeper:2181'
    KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
    KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092
    KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    KAFKA_AUTO_CREATE_TOPICS_ENABLE: 'true'
    KAFKA_JMX_PORT: 9101
    KAFKA_JMX_HOSTNAME: kafka
```

### Topics

| Topic | Partitions | Replication | Retention | Purpose |
|-------|------------|-------------|-----------|---------|
| `web-events` | 3 | 1 | 7 days | Raw event stream |
| `web-events-dlq` | 3 | 1 | 7 days | Dead letter queue |
| `web-events-aggregated` | 3 | 1 | 7 days | Flink output (optional) |

### Producer Configuration

```python
producer_config = {
    'bootstrap.servers': 'localhost:9092',
    'client.id': 'web-events-producer',
    'acks': 'all',                    # Wait for all replicas
    'retries': 3,
    'retry.backoff.ms': 100,
    'batch.size': 16384,
    'linger.ms': 10,
    'buffer.memory': 33554432,
    'compression.type': 'snappy',
    'max.in.flight.requests.per.connection': 5,
    'enable.idempotence': True,       # Exactly-once semantics
}
```

### Consumer Configuration (Spark)

```python
kafka_options = {
    "kafka.bootstrap.servers": "kafka:29092",
    "subscribe": "web-events",
    "startingOffsets": "latest",
    "failOnDataLoss": "false",
    "group.id": "spark-streaming-consumer"
}
```

### Monitoring

Key metrics exposed via JMX (port 9101) and Kafka Exporter (port 9308):

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `kafka_topic_partition_current_offset` | Current offset per partition | - |
| `kafka_consumergroup_lag` | Consumer lag | > 10,000 |
| `kafka_server_brokertopicmetrics_messages_in_per_sec` | Incoming message rate | - |
| `kafka_server_brokertopicmetrics_bytes_in_per_sec` | Incoming byte rate | - |
| `kafka_server_replicamanager_under_replicated_partitions` | Under-replicated partitions | > 0 |
| `kafka_controller_kafkacontroller_active_broker_count` | Active brokers | < expected |

### Operational Commands

```bash
# List topics
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092

# Describe topic
docker exec kafka kafka-topics --describe --topic web-events --bootstrap-server localhost:9092

# Consumer groups
docker exec kafka kafka-consumer-groups --bootstrap-server localhost:9092 --list

# Describe consumer group
docker exec kafka kafka-consumer-groups --bootstrap-server localhost:9092 --describe --group spark-streaming-consumer

# Produce test message
docker exec -it kafka kafka-console-producer --topic web-events --bootstrap-server localhost:9092

# Consume messages
docker exec -it kafka kafka-console-consumer --topic web-events --from-beginning --bootstrap-server localhost:9092

# Reset consumer offset
docker exec kafka kafka-consumer-groups --bootstrap-server localhost:9092 --group spark-streaming-consumer --reset-offsets --to-earliest --execute --topic web-events
```

---

## Spark Structured Streaming

### Overview
Spark Structured Streaming provides a high-level API for stream processing with exactly-once guarantees, event-time processing, and watermarking.

### Job Configuration

```python
# Spark Session
spark = SparkSession.builder \
    .appName("WebEventsStreaming") \
    .config("spark.sql.streaming.checkpointLocation", "s3a://metrics/checkpoints") \
    .config("spark.sql.shuffle.partitions", "4") \
    .config("spark.default.parallelism", "4") \
    .config("spark.streaming.stopGracefullyOnShutdown", "true") \
    .config("spark.sql.adaptive.enabled", "true") \
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
    .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
    .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123") \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.jars.packages", 
            "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,"
            "org.apache.hadoop:hadoop-aws:3.3.4,"
            "com.amazonaws:aws-java-sdk-bundle:1.12.262,"
            "org.postgresql:postgresql:42.7.3") \
    .getOrCreate()
```

### Key Processing Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| Window Duration | 1 minute | Aggregation window size |
| Slide Duration | 30 seconds | Window slide interval |
| Watermark Delay | 2 minutes | Late event threshold |
| Trigger Interval | 30 seconds | Micro-batch frequency |
| Shuffle Partitions | 4 | Parallelism for aggregations |

### Event Schema

```python
EVENT_SCHEMA = StructType([
    StructField("event_id", StringType(), False),
    StructField("timestamp", StringType(), False),
    StructField("user_id", StringType(), False),
    StructField("session_id", StringType(), False),
    StructField("page", StringType(), False),
    StructField("event_type", StringType(), False),
    StructField("device_type", StringType(), True),
    StructField("browser", StringType(), True),
    StructField("os", StringType(), True),
    StructField("country", StringType(), True),
    StructField("referrer", StringType(), True),
    StructField("user_agent", StringType(), True),
    StructField("screen_resolution", StringType(), True),
    StructField("language", StringType(), True),
    StructField("utm_source", StringType(), True),
    StructField("utm_medium", StringType(), True),
    StructField("utm_campaign", StringType(), True),
    # Event-specific fields
    StructField("product_id", StringType(), True),
    StructField("quantity", IntegerType(), True),
    StructField("price", DoubleType(), True),
    StructField("order_id", StringType(), True),
    StructField("total_amount", DoubleType(), True),
    StructField("currency", StringType(), True),
    StructField("items_count", IntegerType(), True),
    StructField("search_query", StringType(), True),
    StructField("results_count", IntegerType(), True),
    StructField("video_id", StringType(), True),
    StructField("video_duration", IntegerType(), True),
    StructField("error_code", StringType(), True),
    StructField("error_message", StringType(), True),
])
```

### Aggregation Logic

```python
windowed = watermarked.groupBy(
    window(col("event_timestamp"), "1 minute", "30 seconds"),
    col("page"),
    col("event_type")
).agg(
    count("*").alias("event_count"),
    countDistinct("user_id").alias("unique_users"),
    countDistinct("session_id").alias("unique_sessions"),
    sum(when(col("event_type") == "purchase", col("total_amount")).otherwise(0)).alias("revenue"),
    count(when(col("event_type") == "purchase", True)).alias("purchase_count"),
    count(when(col("event_type") == "add_to_cart", True)).alias("add_to_cart_count"),
    count(when(col("event_type") == "error", True)).alias("error_count")
)
```

### Multi-Sink Output

```python
def foreach_batch_function(batch_df, batch_id):
    # 1. Write to MinIO (Parquet, partitioned)
    write_to_minio(batch_df, batch_id)
    
    # 2. Write to PostgreSQL (upsert)
    write_to_postgres(batch_df, batch_id)
    
    # 3. Console output (debugging)
    write_to_console(batch_df, batch_id)

query = windowed_df.writeStream \
    .foreachBatch(foreach_batch_function) \
    .option("checkpointLocation", CHECKPOINT_DIR) \
    .trigger(processingTime="30 seconds") \
    .start()
```

### MinIO Write (Partitioned Parquet)

```python
def write_to_minio(batch_df, batch_id):
    if batch_df.isEmpty():
        return
    
    batch_with_partitions = batch_df \
        .withColumn("year", year(col("window_start"))) \
        .withColumn("month", month(col("window_start"))) \
        .withColumn("day", dayofmonth(col("window_start"))) \
        .withColumn("hour", hour(col("window_start"))) \
        .withColumn("minute", minute(col("window_start")))
    
    batch_with_partitions.write \
        .mode("append") \
        .partitionBy("year", "month", "day", "hour", "minute") \
        .parquet(f"s3a://{MINIO_BUCKET}/web-events-metrics/")
```

### PostgreSQL Write (Bulk Upsert)

```python
def write_to_postgres(batch_df, batch_id):
    if batch_df.isEmpty():
        return
    
    rows = batch_df.collect()
    data = [
        (row.window_start, row.window_end, row.page, row.event_type,
         row.event_count, row.unique_users, row.unique_sessions,
         float(row.revenue) if row.revenue else 0.0,
         row.purchase_count, row.add_to_cart_count, row.error_count,
         row.processed_at)
        for row in rows
    ]
    
    conn = psycopg2.connect(...)
    execute_values(cursor, """
        INSERT INTO realtime_metrics 
        (window_start, window_end, page, event_type, event_count, unique_users, 
         unique_sessions, revenue, purchase_count, add_to_cart_count, error_count, processed_at)
        VALUES %s
        ON CONFLICT DO NOTHING
    """, data)
```

### Monitoring

Spark exposes metrics via Prometheus servlet at `/metrics/prometheus/`:

| Metric | Description |
|--------|-------------|
| `spark_streaming_batch_processing_latency_sum` | Total batch processing time |
| `spark_streaming_batch_processing_latency_count` | Number of batches |
| `spark_streaming_batch_input_records` | Records read per batch |
| `spark_streaming_batch_output_records` | Records written per batch |
| `spark_executor_memory_used_bytes` | Executor memory usage |
| `spark_executor_cpu_load` | Executor CPU utilization |

### Submitting the Job

```bash
# Using spark-submit
docker exec -it spark-master spark-submit \
  --master spark://spark-master:7077 \
  --deploy-mode cluster \
  --conf spark.sql.streaming.checkpointLocation=s3a://metrics/checkpoints \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,\
org.apache.hadoop:hadoop-aws:3.3.4,\
com.amazonaws:aws-java-sdk-bundle:1.12.262,\
org.postgresql:postgresql:42.7.3 \
  /opt/spark-apps/structured_streaming.py

# Check job status
curl http://localhost:8080/api/v1/applications
```

### Tuning Guidelines

| Scenario | Adjustment |
|----------|------------|
| High latency | Increase trigger interval, reduce shuffle partitions |
| OOM errors | Increase executor memory, reduce batch size |
| Backpressure | Enable `spark.streaming.backpressure.enabled` |
| Late events | Increase watermark delay |
| Throughput | Increase partitions, add executors |

---

## Apache Flink

### Overview
Apache Flink provides an alternative stream processing engine with true event-time semantics, exactly-once guarantees, and low-latency processing.

### Job Manager Configuration

```yaml
flink-jobmanager:
  image: flink:1.18.1-scala_2.12-java11
  command: jobmanager
  environment:
    FLINK_PROPERTIES: |
      jobmanager.memory.process.size: 2g
      taskmanager.memory.process.size: 2g
      state.backend: rocksdb
      state.backend.incremental: true
      execution.checkpointing.interval: 30s
      execution.checkpointing.mode: EXACTLY_ONCE
      execution.checkpointing.externalized-checkpoint-retention: RETAIN_ON_CANCELLATION
      restart-strategy: fixed-delay
      restart-strategy.fixed-delay.attempts: 3
      restart-strategy.fixed-delay.delay: 10s
```

### Task Manager Configuration

```yaml
flink-taskmanager:
  image: flink:1.18.1-scala_2.12-java11
  command: taskmanager
  scale: 2
  environment:
    FLINK_PROPERTIES: |
      taskmanager.memory.process.size: 2g
      taskmanager.numberOfTaskSlots: 4
      state.backend: rocksdb
      state.backend.incremental: true
```

### Key Flink Concepts

| Concept | Implementation |
|---------|----------------|
| **Event Time** | `WatermarkStrategy.forBoundedOutOfOrderness(Duration.ofMinutes(2))` |
| **Window** | `SlidingEventTimeWindows.of(Time.minutes(1), Time.seconds(30))` |
| **KeyBy** | `keyBy(event -> event.getPage() + "|" + event.getEventType())` |
| **State Backend** | RocksDB with incremental checkpoints |
| **Checkpointing** | Every 30s, exactly-once, retained on cancel |
| **Sink** | Kafka transactional producer |

### Building the Flink Job

```xml
<!-- pom.xml dependencies -->
<dependencies>
    <dependency>
        <groupId>org.apache.flink</groupId>
        <artifactId>flink-streaming-java</artifactId>
        <version>1.18.1</version>
        <scope>provided</scope>
    </dependency>
    <dependency>
        <groupId>org.apache.flink</groupId>
        <artifactId>flink-connector-kafka</artifactId>
        <version>1.18.1</version>
    </dependency>
    <dependency>
        <groupId>com.fasterxml.jackson.core</groupId>
        <artifactId>jackson-databind</artifactId>
        <version>2.15.2</version>
    </dependency>
</dependencies>
```

```bash
# Build
mvn clean package -DskipTests

# Submit to cluster
flink run target/web-events-flink-1.0.jar \
  --kafka.bootstrap.servers kafka:29092 \
  --input.topic web-events \
  --output.topic web-events-aggregated \
  --group.id flink-web-events-consumer
```

### Flink Web UI

Access at http://localhost:8081 for:
- Job overview and status
- Checkpoint history
- Task manager metrics
- Backpressure monitoring
- Flame graphs

### Monitoring

Flink metrics exposed at `/metrics`:

| Metric | Description |
|--------|-------------|
| `flink_jobmanager_job_last_checkpoint_duration` | Last checkpoint duration |
| `flink_jobmanager_job_last_checkpoint_size` | Last checkpoint size |
| `flink_taskmanager_job_task_numRecordsOutPerSecond` | Output throughput |
| `flink_taskmanager_job_task_backpressure_ratio` | Backpressure ratio |
| `flink_jobmanager_status_jobs_running` | Running jobs count |

---

## MinIO

### Overview
MinIO provides S3-compatible object storage for the data lake, storing aggregated metrics as partitioned Parquet files.

### Configuration

```yaml
minio:
  image: minio/minio:RELEASE.2024-01-16T16-07-38Z
  command: server /data --console-address ":9001"
  environment:
    MINIO_ROOT_USER: minioadmin
    MINIO_ROOT_PASSWORD: minioadmin123
  ports:
    - "9000:9000"
    - "9001:9001"
```

### Bucket Structure

```
metrics/
└── web-events-metrics/
    ├── year=2024/
    │   ├── month=1/
    │   │   ├── day=15/
    │   │   │   ├── hour=10/
    │   │   │   │   ├── minute=0/
    │   │   │   │   │   ├── part-00000-xxx.parquet
    │   │   │   │   │   └── part-00001-xxx.parquet
    │   │   │   │   ├── minute=30/
    │   │   │   │   │   └── part-00002-xxx.parquet
```

### S3A Configuration (Spark)

```python
spark.conf.set("spark.hadoop.fs.s3a.endpoint", "http://minio:9000")
spark.conf.set("spark.hadoop.fs.s3a.access.key", "minioadmin")
spark.conf.set("spark.hadoop.fs.s3a.secret.key", "minioadmin123")
spark.conf.set("spark.hadoop.fs.s3a.path.style.access", "true")
spark.conf.set("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
spark.conf.set("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
```

### Querying Parquet Files

```python
# Spark SQL
df = spark.read.parquet("s3a://metrics/web-events-metrics/")
df.createOrReplaceTempView("metrics")

# Query by time partition
spark.sql("""
  SELECT page, event_type, SUM(event_count) as total_events
  FROM metrics
  WHERE year=2024 AND month=1 AND day=15
  GROUP BY page, event_type
  ORDER BY total_events DESC
""").show()

# Time-range query (partition pruning)
spark.sql("""
  SELECT window_start, page, event_type, event_count
  FROM metrics
  WHERE year=2024 AND month=1 AND day=15 AND hour=10
  ORDER BY event_count DESC
""").show()
```

### MinIO Console

Access at http://localhost:9001:
- Username: `minioadmin`
- Password: `minioadmin123`

Features:
- Bucket management
- Object browser
- Access policies
- Metrics dashboard

### Monitoring

MinIO exposes Prometheus metrics at `/minio/v2/metrics/cluster`:

| Metric | Description |
|--------|-------------|
| `minio_cluster_usage_total_bytes` | Total storage used |
| `minio_cluster_usage_free_bytes` | Free storage |
| `minio_s3_requests_total` | S3 API request count |
| `minio_s3_request_duration_seconds` | Request latency |
| `minio_drive_disk_space_free_bytes` | Per-drive free space |

---

## PostgreSQL

### Overview
PostgreSQL stores the latest aggregated metrics for low-latency dashboard queries and ad-hoc analysis.

### Schema

```sql
-- Main metrics table
CREATE TABLE realtime_metrics (
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
    processed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_realtime_metrics_window ON realtime_metrics(window_start, window_end);
CREATE INDEX idx_realtime_metrics_page ON realtime_metrics(page);
CREATE INDEX idx_realtime_metrics_event_type ON realtime_metrics(event_type);
CREATE INDEX idx_realtime_metrics_processed ON realtime_metrics(processed_at);

-- Views for dashboards
CREATE VIEW latest_metrics AS
SELECT window_start, window_end, page, event_type, event_count,
       unique_users, unique_sessions, revenue,
       (event_count::float / EXTRACT(EPOCH FROM (window_end - window_start))) as events_per_second
FROM realtime_metrics
WHERE window_start >= NOW() - INTERVAL '5 minutes'
ORDER BY window_start DESC, event_count DESC;

CREATE VIEW page_metrics AS
SELECT page, SUM(event_count) as total_events,
       SUM(unique_users) as total_unique_users,
       MAX(window_end) as last_update
FROM realtime_metrics
WHERE window_start >= NOW() - INTERVAL '1 hour'
GROUP BY page ORDER BY total_events DESC;

CREATE VIEW event_type_metrics AS
SELECT event_type, SUM(event_count) as total_events,
       MAX(window_end) as last_update
FROM realtime_metrics
WHERE window_start >= NOW() - INTERVAL '1 hour'
GROUP BY event_type ORDER BY total_events DESC;
```

### Connection Pool (Grafana)

```yaml
# grafana/datasources/datasources.yml
- name: PostgreSQL
  type: postgres
  url: postgres:5432
  database: streaming_metrics
  user: streaming_user
  jsonData:
    sslmode: "disable"
    maxOpenConns: 10
    maxIdleConns: 2
    connMaxLifetime: 14400
    timescaledb: false
```

### Querying

```bash
# Connect
docker exec -it postgres psql -U streaming_user -d streaming_metrics

# Useful queries
SELECT * FROM latest_metrics LIMIT 20;
SELECT * FROM page_metrics;
SELECT * FROM event_type_metrics;

-- Custom time range
SELECT page, SUM(event_count) as total
FROM realtime_metrics
WHERE window_start BETWEEN '2024-01-15 10:00:00' AND '2024-01-15 11:00:00'
GROUP BY page ORDER BY total DESC;
```

### Performance Tips

| Optimization | Implementation |
|--------------|----------------|
| Partitioning | Partition by `window_start` (monthly) |
| Indexing | Composite index on (window_start, page, event_type) |
| Vacuum | `autovacuum` enabled, tune for high write volume |
| Connection pooling | PgBouncer for production |
| Read replicas | For dashboard query scaling |

---

## Prometheus & Grafana

### Prometheus Configuration

```yaml
# prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'kafka-exporter'
    static_configs:
      - targets: ['kafka-exporter:9308']

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

  - job_name: 'spark-master'
    static_configs:
      - targets: ['spark-master:8080']
    metrics_path: '/metrics/prometheus/'

  - job_name: 'flink-jobmanager'
    static_configs:
      - targets: ['flink-jobmanager:8081']
    metrics_path: '/metrics'
```

### Grafana Datasources

```yaml
# grafana/datasources/datasources.yml
datasources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090
    isDefault: true

  - name: PostgreSQL
    type: postgres
    url: postgres:5432
    database: streaming_metrics
    user: streaming_user

  - name: MinIO (S3)
    type: grafana-s3-datasource
    url: http://minio:9000
    jsonData:
      bucket: metrics
      region: us-east-1
```

### Dashboard Provisioning

```yaml
# grafana/dashboards/dashboard-provider.yml
providers:
  - name: 'Streaming Pipeline Dashboards'
    orgId: 1
    folder: 'Streaming Pipeline'
    type: file
    options:
      path: /etc/grafana/provisioning/dashboards
```