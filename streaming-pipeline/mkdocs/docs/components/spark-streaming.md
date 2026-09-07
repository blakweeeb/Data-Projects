# Spark Structured Streaming

## Overview

Spark Structured Streaming provides a high-level, declarative API for building streaming applications with exactly-once guarantees, event-time processing, and seamless batch/streaming unification.

## File Location

```
spark_streaming/
└── structured_streaming.py    # Main streaming job
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Spark Structured Streaming                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Kafka Source                    Watermark & Window                │
│  ┌─────────────┐                  ┌─────────────────┐              │
│  │ subscribe   │                  │ withWatermark   │              │
│  │ web-events  │──────┐           │ (2 min delay)   │              │
│  │ latest      │      │           └────────┬────────┘              │
│  └─────────────┘      │                    │                       │
│                       ▼                    ▼                       │
│              ┌─────────────────────────────────────┐               │
│              │     JSON Parsing & Schema           │               │
│              │     from_json(value, EVENT_SCHEMA)  │               │
│              └────────────────┬────────────────────┘               │
│                               │                                    │
│                               ▼                                    │
│              ┌─────────────────────────────────────┐               │
│              │     Sliding Window Aggregation      │               │
│              │     1 min window, 30 sec slide      │               │
│              │     Group by: page, event_type      │               │
│              └────────────────┬────────────────────┘               │
│                               │                                    │
│               ┌───────────────┼───────────────┐                    │
│               ▼               ▼               ▼                    │
│        ┌────────────┐  ┌────────────┐  ┌────────────┐             │
│        │   MinIO    │  │ PostgreSQL │  │  Console   │             │
│        │  (Parquet) │  │  (Upsert)  │  │  (Debug)   │             │
│        └────────────┘  └────────────┘  └────────────┘             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Configuration

### Spark Session

```python
spark = SparkSession.builder \
    .appName("WebEventsStreaming") \
    .config("spark.sql.streaming.checkpointLocation", "s3a://metrics/checkpoints") \
    .config("spark.sql.shuffle.partitions", "4") \
    .config("spark.default.parallelism", "4") \
    .config("spark.streaming.stopGracefullyOnShutdown", "true") \
    .config("spark.sql.adaptive.enabled", "true") \
    .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
    .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
    .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123") \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
    .config("spark.jars.packages", 
            "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,"
            "org.apache.hadoop:hadoop-aws:3.3.4,"
            "com.amazonaws:aws-java-sdk-bundle:1.12.262,"
            "org.postgresql:postgresql:42.7.3") \
    .getOrCreate()
```

### Key Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `checkpointLocation` | `s3a://metrics/checkpoints` | Exactly-once state storage |
| `shuffle.partitions` | 4 | Parallelism for aggregations |
| `trigger` | 30 seconds | Micro-batch interval |
| `watermark` | 2 minutes | Late event threshold |
| `window` | 1 minute | Aggregation window |
| `slide` | 30 seconds | Window slide interval |

## Event Schema

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

## Processing Pipeline

### 1. Read from Kafka

```python
kafka_df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:29092") \
    .option("subscribe", "web-events") \
    .option("startingOffsets", "latest") \
    .option("failOnDataLoss", "false") \
    .load()
```

### 2. Parse JSON Events

```python
parsed = kafka_df.select(
    from_json(col("value").cast("string"), EVENT_SCHEMA).alias("data"),
    col("timestamp").alias("kafka_timestamp"),
    col("partition"),
    col("offset")
).select("data.*", "kafka_timestamp", "partition", "offset")

# Convert timestamp string to timestamp type
events = parsed.withColumn(
    "event_timestamp",
    from_unixtime(unix_timestamp(col("timestamp"), "yyyy-MM-dd'T'HH:mm:ss'Z'")).cast(TimestampType())
)
```

### 3. Apply Watermark

```python
watermarked = events.withWatermark("event_timestamp", "2 minutes")
```

### 4. Sliding Window Aggregation

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
).select(
    col("window.start").alias("window_start"),
    col("window.end").alias("window_end"),
    col("page"),
    col("event_type"),
    col("event_count"),
    col("unique_users"),
    col("unique_sessions"),
    col("revenue"),
    col("purchase_count"),
    col("add_to_cart_count"),
    col("error_count"),
    current_timestamp().alias("processed_at")
)
```

### 5. Multi-Sink Output

```python
def foreach_batch_function(batch_df, batch_id):
    if batch_df.isEmpty():
        return
    
    # Sink 1: MinIO (Parquet, partitioned)
    write_to_minio(batch_df, batch_id)
    
    # Sink 2: PostgreSQL (bulk upsert)
    write_to_postgres(batch_df, batch_id)
    
    # Sink 3: Console (debugging)
    write_to_console(batch_df, batch_id)

query = windowed.writeStream \
    .foreachBatch(foreach_batch_function) \
    .option("checkpointLocation", CHECKPOINT_DIR) \
    .trigger(processingTime="30 seconds") \
    .start()
```

## Sink Implementations

### MinIO (Partitioned Parquet)

```python
def write_to_minio(batch_df, batch_id):
    if batch_df.isEmpty():
        return
    
    # Add partition columns for time-based partitioning
    batch_with_partitions = batch_df \
        .withColumn("year", year(col("window_start"))) \
        .withColumn("month", month(col("window_start"))) \
        .withColumn("day", dayofmonth(col("window_start"))) \
        .withColumn("hour", hour(col("window_start"))) \
        .withColumn("minute", minute(col("window_start")))
    
    # Write partitioned Parquet
    batch_with_partitions.write \
        .mode("append") \
        .partitionBy("year", "month", "day", "hour", "minute") \
        .parquet("s3a://metrics/web-events-metrics/")
    
    print(f"Batch {batch_id}: Written {batch_df.count()} records to MinIO")
```

**Output Structure:**
```
s3a://metrics/web-events-metrics/
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

### PostgreSQL (Bulk Upsert)

```python
def write_to_postgres(batch_df, batch_id):
    if batch_df.isEmpty():
        return
    
    # Collect to driver (suitable for aggregated results)
    rows = batch_df.collect()
    if not rows:
        return
    
    # Prepare data for bulk insert
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
    
    # Bulk insert with ON CONFLICT DO NOTHING
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
    
    print(f"Batch {batch_id}: Written {len(data)} records to PostgreSQL")
```

### Console (Debugging)

```python
def write_to_console(batch_df, batch_id):
    if batch_df.isEmpty():
        return
    
    print(f"\n=== Batch {batch_id} ===")
    batch_df.show(truncate=False)
    print(f"Count: {batch_df.count()}")
```

## Checkpointing

Checkpointing enables exactly-once processing and fault tolerance:

```python
# Checkpoint location (must be durable, distributed storage)
CHECKPOINT_DIR = "s3a://metrics/checkpoints"

query = windowed.writeStream \
    .foreachBatch(foreach_batch_function) \
    .option("checkpointLocation", CHECKPOINT_DIR) \
    .trigger(processingTime="30 seconds") \
    .start()
```

### Checkpoint Structure

```
s3a://metrics/checkpoints/
├── offsets/
│   └── 0, 1, 2, ...          # Kafka offset commits
├── commits/
│   └── 0, 1, 2, ...          # Batch commit logs
├── sources/
│   └── 0/                    # Kafka source metadata
└── sinks/
    └── foreachBatch/         # Sink state
```

### Recovery

On restart, Spark:
1. Reads latest checkpoint
2. Restores Kafka offsets
3. Resumes from last committed batch
4. No duplicate processing (exactly-once)

## Submitting the Job

### Cluster Mode (Recommended)

```bash
docker exec -it spark-master spark-submit \
  --master spark://spark-master:7077 \
  --deploy-mode cluster \
  --conf spark.sql.streaming.checkpointLocation=s3a://metrics/checkpoints \
  --conf spark.sql.shuffle.partitions=8 \
  --conf spark.default.parallelism=8 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,\
org.apache.hadoop:hadoop-aws:3.3.4,\
com.amazonaws:aws-java-sdk-bundle:1.12.262,\
org.postgresql:postgresql:42.7.3 \
  /opt/spark-apps/structured_streaming.py
```

### Client Mode (Debugging)

```bash
docker exec -it spark-master spark-submit \
  --master spark://spark-master:7077 \
  --deploy-mode client \
  --packages ... \
  /opt/spark-apps/structured_streaming.py
```

### Local Mode (Development)

```bash
# On host with Spark installed
spark-submit --master local[*] structured_streaming.py
```

## Monitoring

### Spark UI

Access at http://localhost:8080:
- **Jobs**: Batch processing status
- **Stages**: Task distribution
- **Storage**: Cached data
- **Executors**: Resource usage
- **SQL**: Query plans
- **Streaming**: Batch timeline, latency

### Key Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| Batch Processing Time | Time to process each micro-batch | < 30s |
| Input Records | Records read per batch | - |
| Output Records | Records written per batch | - |
| Processing Latency | Event time to processing time | < 60s |
| Memory Usage | Executor heap usage | < 80% |

### Prometheus Metrics

Enable in Spark config:
```python
.config("spark.metrics.conf.*.sink.prometheus.enabled", "true")
.config("spark.metrics.conf.*.sink.prometheus.path", "/metrics/prometheus")
```

Metrics available at `http://spark-master:8080/metrics/prometheus/`

| Metric | Description |
|--------|-------------|
| `spark_streaming_batch_processing_latency` | Batch processing time |
| `spark_streaming_batch_input_records` | Input records per batch |
| `spark_streaming_batch_output_records` | Output records per batch |
| `spark_executor_memory_used_bytes` | Executor memory |
| `spark_executor_cpu_load` | CPU utilization |

## Performance Tuning

### Batch Interval

```python
# Lower latency, more overhead
.trigger(processingTime="10 seconds")

# Higher latency, less overhead
.trigger(processingTime="60 seconds")
```

### Parallelism

```python
# Match Kafka partitions
spark.conf.set("spark.sql.shuffle.partitions", "6")
spark.conf.set("spark.default.parallelism", "6")
```

### Memory

```yaml
# docker-compose.yml
spark-worker-1:
  environment:
    - SPARK_WORKER_MEMORY=4G
    - SPARK_WORKER_CORES=4
```

```python
# Spark config
.config("spark.executor.memory", "4g")
.config("spark.executor.cores", "2")
.config("spark.driver.memory", "2g")
```

### Backpressure

```python
.config("spark.streaming.backpressure.enabled", "true")
.config("spark.streaming.backpressure.initialRate", "5000")
```

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `Task not serializable` | Lambda captures non-serializable object | Use named functions, broadcast variables |
| `OutOfMemoryError` | Executor memory too small | Increase `SPARK_WORKER_MEMORY` |
| `Checkpoint corrupted` | S3 eventual consistency | Use `s3a://` with strong consistency |
| `Late events dropped` | Watermark too short | Increase watermark delay |
| `Batch processing timeout` | Batch too large | Reduce trigger interval, increase parallelism |

### Debugging

```bash
# Check job logs
docker compose logs -f spark-master

# Check executor logs
docker compose logs spark-worker-1

# Spark UI
open http://localhost:8080

# Check checkpoint
docker exec minio mc ls minio/metrics/checkpoints/
```

### Query Checkpoint State

```bash
# List streaming queries
curl -s http://localhost:8080/api/v1/applications | jq '.[] | select(.name=="WebEventsStreaming")'

# Get query status
curl -s http://localhost:8080/api/v1/applications/<app-id>/streaming
```

## Best Practices

1. **Use foreachBatch for multiple sinks** - Single query, multiple outputs
2. **Partition by time** - Enables partition pruning in queries
3. **Set appropriate watermark** - Balance late events vs. state size
4. **Monitor batch processing time** - Should be < trigger interval
5. **Use exactly-once** - Idempotent sinks + checkpointing
6. **Test failure recovery** - Kill executor, verify no data loss
7. **Schema evolution** - Plan for schema changes in Parquet

## Extending the Job

### Add New Aggregations

```python
windowed = watermarked.groupBy(...).agg(
    # ... existing aggregations
    sum(when(col("event_type") == "wishlist_add", 1).otherwise(0)).alias("wishlist_adds"),
    avg(col("video_duration")).alias("avg_video_duration"),
    approx_count_distinct(col("product_id")).alias("unique_products_viewed")
)
```

### Add ML Inference

```python
from pyspark.ml import PipelineModel

model = PipelineModel.load("s3a://models/user-churn-model/")

def score_batch(batch_df, batch_id):
    predictions = model.transform(batch_df)
    # Write predictions
    predictions.write.mode("append").parquet("s3a://metrics/predictions/")

query = windowed.writeStream \
    .foreachBatch(score_batch) \
    ...
```

### Custom Sink

```python
class CustomSink:
    def __init__(self, config):
        self.config = config
    
    def write(self, batch_df, batch_id):
        # Custom logic
        pass

sink = CustomSink(config)
query = windowed.writeStream \
    .foreach(sink) \
    ...
```