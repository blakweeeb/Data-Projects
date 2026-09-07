# Data Flow

## End-to-End Event Journey

### 1. Event Generation (Producer)

```
┌─────────────────────────────────────────────────────────────┐
│                    Python Producer                          │
├─────────────────────────────────────────────────────────────┤
│  • Generates realistic web events every 200ms              │
│  • Event schema: user_id, session_id, page, event_type,    │
│    timestamp, device, browser, OS, country, referrer, UTM  │
│  • Keyed by user_id for partitioning                        │
│  • Idempotent producer (enable.idempotence=true)           │
│  • Compression: Snappy                                      │
│  • Acks: all (wait for all replicas)                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Kafka Topic    │
                    │  web-events     │
                    │  (3 partitions) │
                    └─────────────────┘
```

### 2. Event Structure

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
  "referrer": "https://www.google.com/",
  "user_agent": "Mozilla/5.0...",
  "screen_resolution": "1920x1080",
  "language": "en-US",
  "utm_source": "google",
  "utm_medium": "organic",
  "utm_campaign": null
}
```

### 3. Kafka Topic Design

| Property | Value | Rationale |
|----------|-------|-----------|
| **Partitions** | 3 | Parallelism for 2-3 consumers |
| **Replication** | 1 (dev) / 3 (prod) | Durability |
| **Retention** | 7 days | Replay capability |
| **Cleanup** | delete | Size-based retention |
| **Segment size** | 1 GB | Balance I/O vs. retention |

### 4. Stream Processing (Spark Structured Streaming)

```
Kafka Source → Parse JSON → Watermark → Sliding Window → Multi-Sink
     │              │           │            │             │
     ▼              ▼           ▼            ▼             ▼
┌─────────┐   ┌──────────┐  ┌────────┐  ┌──────────┐  ┌─────────┐
│ Subscribe│   │ from_json│  │ 2 min  │  │ 1 min /  │  │ MinIO   │
│ to topic │   │ + schema │  │ watermark│  │ 30s slide│  │ Parquet │
└─────────┘   └──────────┘  └────────┘  └──────────┘  └─────────┘
                                                              ┌─────────┐
                                                              │PostgreSQL│
                                                              └─────────┘
```

#### Processing Logic

```python
# Watermark for late events (2 minutes)
watermarked = events.withWatermark("event_timestamp", "2 minutes")

# Sliding window: 1 minute window, 30 second slide
windowed = watermarked.groupBy(
    window("event_timestamp", "1 minute", "30 seconds"),
    "page", "event_type"
).agg(
    count("*").alias("event_count"),
    countDistinct("user_id").alias("unique_users"),
    countDistinct("session_id").alias("unique_sessions"),
    sum(when(col("event_type") == "purchase", col("total_amount"))).alias("revenue"),
    count(when(col("event_type") == "purchase", True)).alias("purchase_count"),
    count(when(col("event_type") == "add_to_cart", True)).alias("add_to_cart_count"),
    count(when(col("event_type") == "error", True)).alias("error_count")
)
```

#### Window Semantics

| Window | Duration | Slide | Output Frequency |
|--------|----------|-------|------------------|
| Sliding | 1 minute | 30 seconds | Every 30 seconds |

**Example**: Event at 10:00:15 appears in windows:
- [09:59:30 - 10:00:30]
- [10:00:00 - 10:01:00]
- [10:00:30 - 10:01:30]

### 5. Stream Processing (Apache Flink)

```
Kafka Source → JSON Parser → Watermark → KeyBy → Sliding Window → Kafka Sink
     │              │            │          │         │              │
     ▼              ▼            ▼          ▼         ▼              ▼
  bootstrap    ObjectMapper  2 min OOO  page|type  1min/30s    Exactly-once
  servers      + POJO        watermark  keyBy     window      transactions
```

#### Flink Key Design Decisions

| Decision | Implementation |
|----------|----------------|
| **Key** | `page|eventType` composite key |
| **Window** | `SlidingEventTimeWindows.of(Time.minutes(1), Time.seconds(30))` |
| **Watermark** | `forBoundedOutOfOrderness(Duration.ofMinutes(2))` |
| **State Backend** | RocksDB (incremental checkpoints) |
| **Checkpointing** | Every 30s, exactly-once, retained on cancel |
| **Sink** | Kafka transactional producer |

### 6. Storage Layer

#### MinIO (Data Lake)

```
s3a://metrics/web-events-metrics/
├── year=2024/
│   ├── month=1/
│   │   ├── day=15/
│   │   │   ├── hour=10/
│   │   │   │   ├── minute=0/
│   │   │   │   │   └── part-00000-xxx.parquet
│   │   │   │   ├── minute=30/
│   │   │   │   │   └── part-00001-xxx.parquet
```

**Partitioning Strategy**:
- **Year/Month/Day/Hour/Minute** = 5-level hierarchy
- Enables partition pruning for time-range queries
- Optimal for Athena, Trino, Spark SQL

**File Format**: Apache Parquet (columnar, compressed, schema evolution)

#### PostgreSQL (Operational Store)

```sql
-- Main table
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

-- Indexes for common queries
CREATE INDEX idx_realtime_metrics_window ON realtime_metrics(window_start, window_end);
CREATE INDEX idx_realtime_metrics_page ON realtime_metrics(page);
CREATE INDEX idx_realtime_metrics_event_type ON realtime_metrics(event_type);

-- Views for dashboards
CREATE VIEW latest_metrics AS ...;      -- Last 5 minutes
CREATE VIEW page_metrics AS ...;        -- Aggregated by page (1h)
CREATE VIEW event_type_metrics AS ...;  -- Aggregated by type (1h)
```

### 7. Observability Flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌─────────┐
│  Services   │────▶│   Exporters  │────▶│ Prometheus  │────▶│ Grafana │
│  (Metrics)  │     │  (Scrape)    │     │  (TSDB)     │     │(Dashbd) │
└─────────────┘     └──────────────┘     └─────────────┘     └─────────┘
       │                    │                    │                │
       ▼                    ▼                    ▼                ▼
  /metrics           kafka-exporter          Scrape every      Query &
  /actuator          node-exporter           15s               Visualize
  jmx                spark metrics
                     flink metrics
                     minio metrics
```

### 8. Latency Budget

| Stage | Expected Latency | Max Acceptable |
|-------|------------------|----------------|
| Producer → Kafka | < 10 ms | 50 ms |
| Kafka → Spark/Flink | < 100 ms | 500 ms |
| Processing (window) | 30-60 s | 90 s |
| Sink write | < 500 ms | 2 s |
| **End-to-end** | **30-60 s** | **90 s** |

> **Note**: End-to-end latency is dominated by window duration (1 minute). For lower latency, reduce window size or use tumbling windows with continuous processing mode.

## Data Quality Checks

### Producer Level
- Schema validation before send
- Required fields: event_id, timestamp, user_id, page, event_type
- Timestamp format: ISO 8601 UTC

### Processing Level
- Watermark tracks event-time progress
- Late events (> 2 min) dropped with metrics
- Null checks on key fields

### Storage Level
- Parquet schema enforcement
- PostgreSQL constraints (NOT NULL, FK)
- Row counts logged per batch

### Monitoring Level
- Consumer lag alerts
- Processing latency alerts
- Data freshness checks