# Apache Flink Job

## Overview

Apache Flink provides a distributed stream processing engine with true event-time semantics, exactly-once guarantees, and low-latency processing. This job serves as an alternative to Spark Structured Streaming.

## File Location

```
flink_job/
└── WebEventsFlinkJob.java    # Main Flink streaming job
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Apache Flink Job                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Kafka Source              Event Time & Watermark                   │
│  ┌─────────────┐           ┌─────────────────────┐                 │
│  │ web-events  │──────┐    │ WatermarkStrategy   │                 │
│  │ consumer    │      │    │ BoundedOutOfOrder   │                 │
│  │ group       │      │    │ (2 minutes)         │                 │
│  └─────────────┘      │    └──────────┬──────────┘                 │
│                       │               │                              │
│                       ▼               ▼                              │
│              ┌─────────────────────────────────────┐                │
│              │        JSON Parsing                  │                │
│              │  ObjectMapper → WebEvent POJO       │                │
│              └────────────────┬────────────────────┘                │
│                               │                                     │
│                               ▼                                     │
│              ┌─────────────────────────────────────┐                │
│              │      KeyBy: page|eventType           │                │
│              └────────────────┬────────────────────┘                │
│                               │                                     │
│                               ▼                                     │
│              ┌─────────────────────────────────────┐                │
│              │   Sliding Window: 1min/30sec        │                │
│              │   ProcessWindowFunction             │                │
│              └────────────────┬────────────────────┘                │
│                               │                                     │
│                               ▼                                     │
│              ┌─────────────────────────────────────┐                │
│              │     Kafka Sink (Transactional)      │                │
│              │     web-events-aggregated           │                │
│              └─────────────────────────────────────┘                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Execution Environment

```java
StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();

// Checkpointing for exactly-once
env.enableCheckpointing(30000); // Every 30 seconds
env.getCheckpointConfig().setMinPauseBetweenCheckpoints(10000);
env.getCheckpointConfig().setCheckpointTimeout(60000);
env.getCheckpointConfig().setTolerableCheckpointFailureNumber(3);
env.getCheckpointConfig().setExternalizedCheckpointCleanup(
    ExternalizedCheckpointCleanup.RETAIN_ON_CANCELLATION
);

// Parallelism
env.setParallelism(4);
```

### 2. Kafka Source

```java
KafkaSource<String> kafkaSource = KafkaSource.<String>builder()
    .setBootstrapServers("kafka:29092")
    .setTopics("web-events")
    .setGroupId("flink-web-events-consumer")
    .setStartingOffsets(OffsetsInitializer.latest())
    .setValueOnlyDeserializer(new SimpleStringSchema())
    .build();

DataStream<String> rawEvents = env.fromSource(
    kafkaSource,
    WatermarkStrategy.noWatermarks(),
    "Kafka Source"
);
```

### 3. JSON Parsing

```java
public static class JsonParserFunction extends MapFunction<String, WebEvent> {
    private final ObjectMapper mapper = new ObjectMapper();
    
    @Override
    public WebEvent map(String json) throws Exception {
        JsonNode node = mapper.readTree(json);
        WebEvent event = new WebEvent();
        event.setEventId(node.get("event_id").asText());
        event.setTimestamp(node.get("timestamp").asText());
        event.setUserId(node.get("user_id").asText());
        event.setSessionId(node.get("session_id").asText());
        event.setPage(node.get("page").asText());
        event.setEventType(node.get("event_type").asText());
        // ... other fields
        
        // Parse timestamp to epoch millis
        Instant instant = Instant.parse(node.get("timestamp").asText());
        event.setEventTimestamp(instant.toEpochMilli());
        
        return event;
    }
}
```

### 4. Watermark Strategy

```java
WatermarkStrategy<WebEvent> watermarkStrategy = WatermarkStrategy
    .<WebEvent>forBoundedOutOfOrderness(Duration.ofMinutes(2))
    .withTimestampAssigner((event, timestamp) -> event.getEventTimestamp())
    .withIdleness(Duration.ofMinutes(1));

DataStream<WebEvent> watermarkedEvents = events
    .assignTimestampsAndWatermarks(watermarkStrategy);
```

### 5. KeyBy & Sliding Window

```java
DataStream<AggregatedMetrics> aggregated = watermarkedEvents
    .keyBy(event -> event.getPage() + "|" + event.getEventType())
    .window(SlidingEventTimeWindows.of(Time.minutes(1), Time.seconds(30)))
    .process(new WindowAggregationFunction());
```

### 6. Window Aggregation Function

```java
public static class WindowAggregationFunction 
    extends ProcessWindowFunction<WebEvent, AggregatedMetrics, String, TimeWindow> {
    
    @Override
    public void process(String key, Context context, 
                        Iterable<WebEvent> elements, Collector<AggregatedMetrics> out) {
        
        long windowStart = context.window().getStart();
        long windowEnd = context.window().getEnd();
        
        // Parse composite key
        String[] parts = key.split("\\|", 2);
        String page = parts[0];
        String eventType = parts.length > 1 ? parts[1] : "";
        
        // Aggregate
        long eventCount = 0;
        Set<String> uniqueUsers = new HashSet<>();
        Set<String> uniqueSessions = new HashSet<>();
        double revenue = 0.0;
        long purchaseCount = 0;
        long addToCartCount = 0;
        long errorCount = 0;
        
        for (WebEvent event : elements) {
            eventCount++;
            uniqueUsers.add(event.getUserId());
            uniqueSessions.add(event.getSessionId());
            
            if ("purchase".equals(event.getEventType())) purchaseCount++;
            if ("add_to_cart".equals(event.getEventType())) addToCartCount++;
            if ("error".equals(event.getEventType())) errorCount++;
        }
        
        AggregatedMetrics metrics = new AggregatedMetrics();
        metrics.setWindowStart(windowStart);
        metrics.setWindowEnd(windowEnd);
        metrics.setPage(page);
        metrics.setEventType(eventType);
        metrics.setEventCount(eventCount);
        metrics.setUniqueUsers(uniqueUsers.size());
        metrics.setUniqueSessions(uniqueSessions.size());
        metrics.setRevenue(revenue);
        metrics.setPurchaseCount(purchaseCount);
        metrics.setAddToCartCount(addToCartCount);
        metrics.setErrorCount(errorCount);
        metrics.setProcessedAt(System.currentTimeMillis());
        
        out.collect(metrics);
    }
}
```

### 7. Kafka Sink (Exactly-Once)

```java
KafkaSink<AggregatedMetrics> kafkaSink = KafkaSink.<AggregatedMetrics>builder()
    .setBootstrapServers("kafka:29092")
    .setRecordSerializer(KafkaRecordSerializationSchema.builder()
        .setTopic("web-events-aggregated")
        .setValueSerializationSchema(new MetricsSerializationSchema())
        .build())
    .setDeliveryGuarantee(DeliveryGuarantee.EXACTLY_ONCE)
    .setTransactionalIdPrefix("flink-web-events")
    .build();

aggregated.sinkTo(kafkaSink).name("Kafka Sink").uid("kafka-sink");
```

### 8. Serialization Schema

```java
public static class MetricsSerializationSchema 
    implements SerializationSchema<AggregatedMetrics> {
    
    private final ObjectMapper mapper = new ObjectMapper();
    
    @Override
    public byte[] serialize(AggregatedMetrics metrics) {
        Map<String, Object> map = new HashMap<>();
        map.put("window_start", metrics.getWindowStart());
        map.put("window_end", metrics.getWindowEnd());
        map.put("page", metrics.getPage());
        map.put("event_type", metrics.getEventType());
        map.put("event_count", metrics.getEventCount());
        map.put("unique_users", metrics.getUniqueUsers());
        map.put("unique_sessions", metrics.getUniqueSessions());
        map.put("revenue", metrics.getRevenue());
        map.put("purchase_count", metrics.getPurchaseCount());
        map.put("add_to_cart_count", metrics.getAddToCartCount());
        map.put("error_count", metrics.getErrorCount());
        map.put("processed_at", metrics.getProcessedAt());
        return mapper.writeValueAsBytes(map);
    }
}
```

## POJO Classes

### WebEvent

```java
public static class WebEvent {
    private String eventId;
    private String timestamp;
    private String userId;
    private String sessionId;
    private String page;
    private String eventType;
    private String deviceType;
    private String browser;
    private String os;
    private String country;
    private String referrer;
    private String userAgent;
    private long eventTimestamp;
    
    // Getters and setters...
}
```

### AggregatedMetrics

```java
public static class AggregatedMetrics {
    private long windowStart;
    private long windowEnd;
    private String page;
    private String eventType;
    private long eventCount;
    private long uniqueUsers;
    private long uniqueSessions;
    private double revenue;
    private long purchaseCount;
    private long addToCartCount;
    private long errorCount;
    private long processedAt;
    
    // Getters and setters...
}
```

## Building the Job

### Maven pom.xml

```xml
<project>
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.streaming</groupId>
    <artifactId>web-events-flink</artifactId>
    <version>1.0</version>
    
    <properties>
        <flink.version>1.18.1</flink.version>
        <java.version>11</java.version>
        <maven.compiler.source>11</maven.compiler.source>
        <maven.compiler.target>11</maven.compiler.target>
    </properties>
    
    <dependencies>
        <!-- Flink Streaming -->
        <dependency>
            <groupId>org.apache.flink</groupId>
            <artifactId>flink-streaming-java</artifactId>
            <version>${flink.version}</version>
            <scope>provided</scope>
        </dependency>
        
        <!-- Kafka Connector -->
        <dependency>
            <groupId>org.apache.flink</groupId>
            <artifactId>flink-connector-kafka</artifactId>
            <version>${flink.version}</version>
        </dependency>
        
        <!-- Jackson for JSON -->
        <dependency>
            <groupId>com.fasterxml.jackson.core</groupId>
            <artifactId>jackson-databind</artifactId>
            <version>2.15.2</version>
        </dependency>
    </dependencies>
    
    <build>
        <plugins>
            <!-- Shade plugin for fat JAR -->
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-shade-plugin</artifactId>
                <version>3.5.1</version>
                <executions>
                    <execution>
                        <phase>package</phase>
                        <goals><goal>shade</goal></goals>
                        <configuration>
                            <transformers>
                                <transformer implementation="org.apache.maven.plugins.shade.resource.ManifestResourceTransformer">
                                    <mainClass>com.streaming.flink.WebEventsFlinkJob</mainClass>
                                </transformer>
                            </transformers>
                        </configuration>
                    </execution>
                </executions>
            </plugin>
        </plugins>
    </build>
</project>
```

### Build Command

```bash
cd flink_job
mvn clean package -DskipTests
```

Output: `target/web-events-flink-1.0.jar`

## Deploying to Flink

### Docker Compose (Included)

```bash
# Flink services already running from docker-compose
# Copy JAR to container
docker cp target/web-events-flink-1.0.jar flink-jobmanager:/opt/flink/usrlib/

# Submit job
docker exec flink-jobmanager flink run \
  -d /opt/flink/usrlib/web-events-flink-1.0.jar \
  --kafka.bootstrap.servers kafka:29092 \
  --input.topic web-events \
  --output.topic web-events-aggregated \
  --group.id flink-web-events-consumer
```

### CLI Commands

```bash
# List jobs
docker exec flink-jobmanager flink list

# Job details
docker exec flink-jobmanager flink info <job-id>

# Stop job
docker exec flink-jobmanager flink cancel <job-id>

# Stop with savepoint
docker exec flink-jobmanager flink cancel -s [savepointPath] <job-id>

# Resume from savepoint
docker exec flink-jobmanager flink run \
  -s <savepoint-path> \
  -d /opt/flink/usrlib/web-events-flink-1.0.jar \
  --kafka.bootstrap.servers kafka:29092 \
  --input.topic web-events \
  --output.topic web-events-aggregated
```

### ParameterTool Configuration

```java
ParameterTool params = ParameterTool.fromArgs(args);

String kafkaBootstrapServers = params.get("kafka.bootstrap.servers", "kafka:29092");
String inputTopic = params.get("input.topic", "web-events");
String outputTopic = params.get("output.topic", "web-events-aggregated");
String groupId = params.get("group.id", "flink-web-events-consumer");
```

## Flink Web UI

Access at http://localhost:8081

### Key Pages

| Page | Purpose |
|------|---------|
| **Overview** | Cluster status, running jobs |
| **Job** | Job graph, metrics, checkpoints |
| **Task Managers** | Slot allocation, resource usage |
| **Checkpoints** | Checkpoint history, duration, size |
| **Backpressure** | Real-time backpressure monitoring |

### Job Graph

```
Kafka Source → JSON Parser → Watermark → KeyBy → Window → Kafka Sink
     │              │           │          │        │        │
     ▼              ▼           ▼          ▼        ▼        ▼
  Parallelism    Parallelism  Parallelism 4     4        4
    1              1            1
```

## Monitoring

### Flink Metrics (Prometheus)

```yaml
# Add to flink-conf.yaml
metrics.reporter.prom.class: org.apache.flink.metrics.prometheus.PrometheusReporter
metrics.reporter.prom.port: 9250
```

Available at `http://flink-jobmanager:9250/metrics`

| Metric | Description |
|--------|-------------|
| `flink_jobmanager_job_last_checkpoint_duration` | Last checkpoint time |
| `flink_jobmanager_job_last_checkpoint_size` | Last checkpoint size |
| `flink_jobmanager_job_number_of_completed_checkpoints` | Completed checkpoints |
| `flink_taskmanager_job_task_numRecordsOutPerSecond` | Output throughput |
| `flink_taskmanager_job_task_backpressure_ratio` | Backpressure indicator |
| `flink_taskmanager_job_task_busyTimeMsPerSecond` | Task busy time |

### Key Alerts

| Alert | Expression | Threshold |
|-------|------------|-----------|
| Checkpoint failing | `flink_jobmanager_job_last_checkpoint_duration > 60000` | > 60s |
| Backpressure high | `flink_taskmanager_job_task_backpressure_ratio > 0.5` | > 50% |
| Throughput drop | `rate(flink_taskmanager_job_task_numRecordsOutPerSecond[5m]) < 100` | < 100/s |

## State Backend

### RocksDB (Production)

```java
// In flink-conf.yaml or code
env.setStateBackend(new EmbeddedRocksDBStateBackend());
env.getCheckpointConfig().setCheckpointStorage("s3a://metrics/checkpoints/flink/");
```

Configuration:
```yaml
state.backend: rocksdb
state.backend.incremental: true
state.checkpoints.dir: s3a://metrics/checkpoints/flink/
```

### Memory State (Development)

```java
env.setStateBackend(new HashMapStateBackend());
```

## Scaling

### Horizontal Scaling

```yaml
# docker-compose.yml
flink-taskmanager:
  scale: 4  # 4 task managers
```

```java
// Each task manager has 4 slots = 16 total
// Parallelism can be up to 16
env.setParallelism(16);
```

### Vertical Scaling

```yaml
flink-taskmanager:
  environment:
    - FLINK_PROPERTIES=
      taskmanager.memory.process.size: 4g
      taskmanager.memory.managed.fraction: 0.4
      taskmanager.numberOfTaskSlots: 8
```

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| `ClassNotFoundException` | Ensure fat JAR built with maven-shade-plugin |
| `Kafka connection failed` | Check network, bootstrap servers |
| `Checkpoint timeout` | Increase `checkpoint.timeout`, check state backend |
| `OutOfMemoryError` | Increase taskmanager memory, use RocksDB |
| `Backpressure` | Increase parallelism, optimize processing |

### Debugging

```bash
# Check job logs
docker compose logs -f flink-jobmanager
docker compose logs -f flink-taskmanager

# Flink UI
open http://localhost:8081

# Check checkpoints
docker exec minio mc ls minio/metrics/checkpoints/flink/
```

### Savepoints

```bash
# Trigger savepoint
docker exec flink-jobmanager flink savepoint <job-id> s3a://metrics/savepoints/

# List savepoints
docker exec minio mc ls minio/metrics/savepoints/

# Resume from savepoint
docker exec flink-jobmanager flink run -s s3a://metrics/savepoints/savepoint-xxx <jar>
```

## Performance Tuning

### Checkpoint Tuning

```java
Configuration config = new Configuration();
config.setString("execution.checkpointing.interval", "30s");
config.setString("execution.checkpointing.mode", "EXACTLY_ONCE");
config.setString("execution.checkpointing.timeout", "1min");
config.setString("execution.checkpointing.min-pause", "10s");
config.setString("execution.checkpointing.max-concurrent-checkpoints", "1");
config.setString("execution.checkpointing.tolerable-failed-checkpoints", "3");
```

### Network Buffers

```yaml
# flink-conf.yaml
taskmanager.memory.network.fraction: 0.1
taskmanager.memory.network.min: 64mb
taskmanager.memory.network.max: 1gb
```

### Kafka Consumer

```java
// In KafkaSource builder
.setProperty("fetch.min.bytes", "1")
.setProperty("fetch.max.wait.ms", "500")
.setProperty("max.poll.records", "500")
```

## Extending the Job

### Add Custom Window Logic

```java
public class CustomWindowFunction 
    extends ProcessWindowFunction<WebEvent, AggregatedMetrics, String, TimeWindow> {
    
    @Override
    public void process(String key, Context context, 
                        Iterable<WebEvent> elements, Collector<AggregatedMetrics> out) {
        // Custom aggregation logic
        // Access window metadata: context.window()
        // Access state: context.windowState()
        // Emit multiple results: out.collect(...)
    }
}
```

### Add Side Outputs (Late Events)

```java
OutputTag<WebEvent> lateEventsTag = new OutputTag<>("late-events"){};

SingleOutputStreamOperator<AggregatedMetrics> result = watermarkedEvents
    .keyBy(...)
    .window(...)
    .sideOutputLateData(lateEventsTag)
    .process(...);

// Access late events
DataStream<WebEvent> lateEvents = result.getSideOutput(lateEventsTag);
lateEvents.addSink(new LateEventsSink());
```

### Add Async I/O (External Lookup)

```java
AsyncFunction<WebEvent, EnrichedEvent> asyncFunction = 
    new AsyncFunction<WebEvent, EnrichedEvent>() {
        @Override
        public void asyncInvoke(WebEvent input, ResultFuture<EnrichedEvent> resultFuture) {
            // Async database lookup
            CompletableFuture.supplyAsync(() -> {
                return enrichWithUserProfile(input);
            }).thenAccept(resultFuture::complete);
        }
    };

DataStream<EnrichedEvent> enriched = AsyncDataStream.unorderedWait(
    events, asyncFunction, 3000, TimeUnit.MILLISECONDS, 100
);
```

## Comparison: Flink vs Spark Streaming

| Aspect | Flink | Spark Structured Streaming |
|--------|-------|---------------------------|
| **Processing Model** | Native streaming | Micro-batch |
| **Latency** | ~100ms | ~1-30s |
| **Event Time** | First-class | Supported |
| **Watermarks** | Flexible | Fixed delay |
| **State Backend** | RocksDB (incremental) | RocksDB (full) |
| **Checkpointing** | Distributed snapshots | Offset-based |
| **Exactly-Once** | Native | Via idempotent sinks |
| **Windowing** | Rich (session, global) | Tumbling, sliding |
| **Backpressure** | Native credit-based | Rate limiting |
| **SQL Support** | Flink SQL | Spark SQL |

## Dependencies

```xml
<!-- Flink -->
<dependency>
    <groupId>org.apache.flink</groupId>
    <artifactId>flink-streaming-java</artifactId>
    <version>1.18.1</version>
    <scope>provided</scope>
</dependency>

<!-- Kafka Connector -->
<dependency>
    <groupId>org.apache.flink</groupId>
    <artifactId>flink-connector-kafka</artifactId>
    <version>1.18.1</version>
</dependency>

<!-- JSON -->
<dependency>
    <groupId>com.fasterxml.jackson.core</groupId>
    <artifactId>jackson-databind</artifactId>
    <version>2.15.2</version>
</dependency>
```