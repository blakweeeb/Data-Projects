# MinIO Storage

## Overview

MinIO provides high-performance, S3-compatible object storage for the data lake. It stores aggregated metrics as partitioned Parquet files, enabling cost-effective analytics and ML workloads.

## Configuration

### Docker Compose

```yaml
minio:
  image: minio/minio:RELEASE.2024-01-16T16-07-38Z
  command: server /data --console-address ":9001"
  ports:
    - "9000:9000"   # S3 API
    - "9001:9001"   # Web Console
  environment:
    MINIO_ROOT_USER: minioadmin
    MINIO_ROOT_PASSWORD: minioadmin123
  volumes:
    - minio-data:/data
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
    interval: 30s
    timeout: 20s
    retries: 3
```

### Bucket Creation

```yaml
minio-bucket-creator:
  image: minio/mc:RELEASE.2024-01-16T16-07-38Z
  depends_on:
    minio:
      condition: service_healthy
  entrypoint: >
    /bin/sh -c "
      until (/usr/bin/mc config host add minio http://minio:9000 minioadmin minioadmin123) do echo '...waiting...' && sleep 1; done;
      /usr/bin/mc mb minio/metrics --ignore-existing;
      /usr/bin/mc anonymous set public minio/metrics;
      echo 'Bucket created successfully';
    "
```

## S3A Configuration (Spark)

```python
spark.conf.set("spark.hadoop.fs.s3a.endpoint", "http://minio:9000")
spark.conf.set("spark.hadoop.fs.s3a.access.key", "minioadmin")
spark.conf.set("spark.hadoop.fs.s3a.secret.key", "minioadmin123")
spark.conf.set("spark.hadoop.fs.s3a.path.style.access", "true")
spark.conf.set("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
spark.conf.set("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
```

## Data Layout

### Partitioned Parquet Structure

```
s3a://metrics/web-events-metrics/
├── year=2024/
│   ├── month=1/
│   │   ├── day=15/
│   │   │   ├── hour=10/
│   │   │   │   ├── minute=0/
│   │   │   │   │   ├── part-00000-uuid.parquet
│   │   │   │   │   ├── part-00001-uuid.parquet
│   │   │   │   ├── minute=30/
│   │   │   │   │   ├── part-00002-uuid.parquet
```

### Partition Columns

| Column | Type | Description |
|--------|------|-------------|
| `year` | int | Year (2024) |
| `month` | int | Month (1-12) |
| `day` | int | Day of month (1-31) |
| `hour` | int | Hour (0-23) |
| `minute` | int | Minute (0, 30) |

### Parquet Schema

```python
root
 |-- window_start: timestamp (nullable = false)
 |-- window_end: timestamp (nullable = false)
 |-- page: string (nullable = false)
 |-- event_type: string (nullable = false)
 |-- event_count: long (nullable = false)
 |-- unique_users: long (nullable = false)
 |-- unique_sessions: long (nullable = false)
 |-- revenue: double (nullable = true)
 |-- purchase_count: long (nullable = true)
 |-- add_to_cart_count: long (nullable = true)
 |-- error_count: long (nullable = true)
 |-- processed_at: timestamp (nullable = true)
 |-- year: int (nullable = true)
 |-- month: int (nullable = true)
 |-- day: int (nullable = true)
 |-- hour: int (nullable = true)
 |-- minute: int (nullable = true)
```

## Writing Data (Spark)

```python
def write_to_minio(batch_df, batch_id):
    if batch_df.isEmpty():
        return
    
    # Add partition columns
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
```

## Querying Data

### Spark SQL

```python
# Read all data
df = spark.read.parquet("s3a://metrics/web-events-metrics/")
df.createOrReplaceTempView("metrics")

# Query with partition pruning (fast)
spark.sql("""
  SELECT page, event_type, SUM(event_count) as total_events
  FROM metrics
  WHERE year=2024 AND month=1 AND day=15
  GROUP BY page, event_type
  ORDER BY total_events DESC
""").show()

# Time range query
spark.sql("""
  SELECT window_start, page, SUM(event_count) as events
  FROM metrics
  WHERE year=2024 AND month=1 AND day=15 AND hour BETWEEN 10 AND 12
  GROUP BY window_start, page
  ORDER BY window_start
""").show()

# Top pages by traffic
spark.sql("""
  SELECT page, SUM(event_count) as total_events, SUM(unique_users) as total_users
  FROM metrics
  WHERE year=2024 AND month=1
  GROUP BY page
  ORDER BY total_events DESC
  LIMIT 10
""").show()
```

### Python (pandas + s3fs)

```python
import pandas as pd
import s3fs

fs = s3fs.S3FileSystem(
    client_kwargs={'endpoint_url': 'http://localhost:9000'},
    key='minioadmin',
    secret='minioadmin123'
)

# Read partitioned dataset
df = pd.read_parquet(
    "s3://metrics/web-events-metrics/",
    filesystem=fs,
    filters=[('year', '=', 2024), ('month', '=', 1)]
)

print(df.head())
print(df.groupby('page')['event_count'].sum().sort_values(ascending=False))
```

### AWS CLI (for testing)

```bash
# Configure AWS CLI for MinIO
aws configure set aws_access_key_id minioadmin
aws configure set aws_secret_access_key minioadmin123
aws configure set default.region us-east-1

# List objects
aws --endpoint-url http://localhost:9000 s3 ls s3://metrics/web-events-metrics/ --recursive

# Copy file locally
aws --endpoint-url http://localhost:9000 s3 cp s3://metrics/web-events-metrics/year=2024/month=1/day=15/hour=10/minute=0/part-00000.parquet ./local.parquet
```

## MinIO Console

Access at http://localhost:9001

**Credentials:**
- Username: `minioadmin`
- Password: `minioadmin123`

### Features

- **Bucket Browser**: Navigate objects and folders
- **Object Details**: View metadata, download, share
- **Access Policies**: Configure bucket policies
- **Metrics**: Storage usage, request rates, latency
- **Identity**: Manage users and service accounts

## Lifecycle Management

### Expiration Rules

```bash
# Using mc (MinIO Client)
docker exec -it minio mc ilm rule add metrics/web-events-metrics \
  --expire-days 90 \
  --noncurrent-expire-days 30

# List rules
docker exec -it minio mc ilm rule ls metrics/web-events-metrics
```

### Tiering (Production)

```bash
# Add warm tier (e.g., to another MinIO cluster or S3)
mc ilm tier add metrics/web-events-metrics \
  --type warm \
  --endpoint https://warm-storage.example.com \
  --credentials access_key=xxx secret_key=yyy
```

## Monitoring

### Prometheus Metrics

MinIO exposes metrics at `/minio/v2/metrics/cluster`

| Metric | Description |
|--------|-------------|
| `minio_cluster_usage_total_bytes` | Total storage used |
| `minio_cluster_usage_free_bytes` | Free storage |
| `minio_cluster_objects_total` | Total objects |
| `minio_s3_requests_total` | S3 API request count |
| `minio_s3_request_duration_seconds` | Request latency histogram |
| `minio_s3_traffic_received_bytes` | Ingress bytes |
| `minio_s3_traffic_sent_bytes` | Egress bytes |
| `minio_drive_disk_space_free_bytes` | Per-drive free space |
| `minio_drive_disk_space_total_bytes` | Per-drive total space |

### Grafana Dashboard

Import MinIO dashboard from Grafana.com (ID: 13502) or use custom:

```json
{
  "panels": [
    {
      "title": "Storage Usage",
      "targets": [
        {"expr": "minio_cluster_usage_total_bytes", "legendFormat": "Used"},
        {"expr": "minio_cluster_usage_free_bytes", "legendFormat": "Free"}
      ]
    },
    {
      "title": "Request Rate",
      "targets": [
        {"expr": "rate(minio_s3_requests_total[5m])", "legendFormat": "{{method}}"}
      ]
    },
    {
      "title": "Request Latency (p99)",
      "targets": [
        {"expr": "histogram_quantile(0.99, rate(minio_s3_request_duration_seconds_bucket[5m]))", "legendFormat": "{{method}}"}
      ]
    }
  ]
}
```

## Performance Tuning

### Erasure Coding (Production)

```yaml
# MinIO distributed mode with erasure coding
minio:
  command: server http://minio{1...4}/data --console-address ":9001"
  # 4 nodes, 16 drives = 8 data + 8 parity (50% overhead)
```

### Disk Configuration

```yaml
# Use multiple disks per node
volumes:
  - minio-data-1:/data1
  - minio-data-2:/data2
  - minio-data-3:/data3
  - minio-data-4:/data4

command: server /data1 /data2 /data3 /data4 --console-address ":9001"
```

### Network

```yaml
# Enable compression
environment:
  MINIO_COMPRESS: "on"
  MINIO_COMPRESS_EXTENSIONS: ".parquet,.json,.csv"
  MINIO_COMPRESS_MIME_TYPES: "application/*,text/*"
```

## Security (Production)

### TLS/SSL

```yaml
minio:
  command: server /data --console-address ":9001" --certs-dir /etc/minio/certs
  volumes:
    - ./certs:/etc/minio/certs:ro
```

### IAM Policies

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": ["arn:aws:s3:::metrics/web-events-metrics/*"]
    },
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": ["arn:aws:s3:::metrics"]
    }
  ]
}
```

### Server-Side Encryption

```bash
# Enable SSE-S3
mc admin config set minio encrypt_s3 "on"

# Or SSE-KMS
mc admin config set minio encrypt_sse_kms "on" key_id="arn:aws:kms:..."
```

## Backup & Disaster Recovery

### Replication

```bash
# Add remote target
mc admin bucket remote add minio/metrics https://backup-minio.example.com \
  --access-key=xxx --secret-key=yyy

# Enable replication
mc replicate add minio/metrics --remote-target backup --priority 1
```

### Point-in-Time Recovery

```bash
# Enable versioning
mc version enable minio/metrics

# Restore deleted object
mc cp minio/metrics/web-events-metrics/year=2024/.../part.parquet#version-id .
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `Access Denied` | Check credentials, bucket policy |
| `Connection refused` | Verify MinIO is healthy: `curl http://localhost:9000/minio/health/live` |
| `Slow queries` | Ensure partition pruning works, check Parquet schema |
| `Disk full` | Add lifecycle rules, increase storage |
| `High latency` | Check network, enable compression |

## Useful Commands

```bash
# MinIO Client (mc) in container
docker exec -it minio mc --help

# List buckets
docker exec minio mc ls minio/

# Bucket size
docker exec minio mc du minio/metrics

# Object info
docker exec minio mc stat minio/metrics/web-events-metrics/year=2024/...

# Cat object (small files)
docker exec minio mc cat minio/metrics/web-events-metrics/.../part.parquet

# Mirror to local
docker exec minio mc mirror minio/metrics ./local-backup/
```