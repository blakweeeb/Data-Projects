# Configuration

## Environment Variables

### Global Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `COMPOSE_PROJECT_NAME` | `streaming-pipeline` | Docker Compose project name |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:29092` | Kafka broker addresses |
| `MINIO_ENDPOINT` | `http://minio:9000` | MinIO S3 endpoint |
| `POSTGRES_HOST` | `postgres` | PostgreSQL host |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_DB` | `streaming_metrics` | Database name |
| `POSTGRES_USER` | `streaming_user` | Database user |
| `POSTGRES_PASSWORD` | `streaming_pass` | Database password |

### Service-Specific Configuration

#### Kafka
```yaml
# docker-compose.yml
kafka:
  environment:
    KAFKA_BROKER_ID: 1
    KAFKA_ZOOKEEPER_CONNECT: 'zookeeper:2181'
    KAFKA_NUM_PARTITIONS: 3
    KAFKA_DEFAULT_REPLICATION_FACTOR: 1
    KAFKA_LOG_RETENTION_HOURS: 168  # 7 days
    KAFKA_LOG_SEGMENT_BYTES: 1073741824  # 1GB
    KAFKA_AUTO_CREATE_TOPICS_ENABLE: 'true'
```

#### Spark
```python
# spark_streaming/structured_streaming.py
KAFKA_BOOTSTRAP_SERVERS = "kafka:29092"
KAFKA_TOPIC = "web-events"
MINIO_ENDPOINT = "http://minio:9000"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin123"
MINIO_BUCKET = "metrics"
CHECKPOINT_DIR = "s3a://metrics/checkpoints"
WINDOW_DURATION = "1 minute"
SLIDE_DURATION = "30 seconds"
WATERMARK_DELAY = "2 minutes"
```

#### Flink
```bash
# Command line arguments
--kafka.bootstrap.servers kafka:29092
--input.topic web-events
--output.topic web-events-aggregated
--group.id flink-web-events-consumer
```

#### MinIO
```yaml
minio:
  environment:
    MINIO_ROOT_USER: minioadmin
    MINIO_ROOT_PASSWORD: minioadmin123
  command: server /data --console-address ":9001"
```

#### PostgreSQL
```yaml
postgres:
  environment:
    POSTGRES_DB: streaming_metrics
    POSTGRES_USER: streaming_user
    POSTGRES_PASSWORD: streaming_pass
```

#### Prometheus
```yaml
# prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
```

#### Grafana
```yaml
grafana:
  environment:
    GF_SECURITY_ADMIN_USER: admin
    GF_SECURITY_ADMIN_PASSWORD: admin123
    GF_USERS_ALLOW_SIGN_UP: "false"
```

## Customizing the Pipeline

### Changing Event Rate

```bash
# Producer: 10 events/sec (100ms interval)
python producer.py --interval 100

# Producer: 1 event/sec (1000ms interval)
python producer.py --interval 1000
```

### Changing Window Parameters

```python
# spark_streaming/structured_streaming.py
WINDOW_DURATION = "5 minutes"    # Longer window
SLIDE_DURATION = "1 minute"      # Less frequent updates
WATERMARK_DELAY = "5 minutes"    # More tolerance for late events
```

### Scaling Spark

```yaml
# docker-compose.yml - Add more workers
spark-worker-3:
  image: bitnami/spark:3.5.0
  environment:
    - SPARK_MODE=worker
    - SPARK_MASTER_URL=spark://spark-master:7077
    - SPARK_WORKER_MEMORY=4G
    - SPARK_WORKER_CORES=4
```

```python
# Increase parallelism
spark.conf.set("spark.sql.shuffle.partitions", "8")
spark.conf.set("spark.default.parallelism", "8")
```

### Scaling Flink

```yaml
# docker-compose.yml - Increase task managers
flink-taskmanager:
  scale: 4  # 4 task managers = 16 slots (4 each)
```

```bash
# Increase parallelism
flink run -p 8 target/web-events-flink-1.0.jar ...
```

### Changing Retention

```yaml
# Kafka retention
KAFKA_LOG_RETENTION_HOURS: 720  # 30 days
KAFKA_LOG_RETENTION_BYTES: 107374182400  # 100GB per partition
```

```python
# MinIO lifecycle (add via mc)
# Expire objects older than 90 days
mc ilm rule add metrics/web-events-metrics --expire-days 90
```

## Production Configuration

### Security

#### Kafka SASL/SSL
```yaml
kafka:
  environment:
    KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,SSL:SSL,SASL_SSL:SASL_SSL
    KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:29092,SSL://kafka:29093,SASL_SSL://kafka:29094
    KAFKA_SSL_KEYSTORE_LOCATION: /etc/kafka/secrets/kafka.keystore.jks
    KAFKA_SSL_KEYSTORE_PASSWORD: ${KEYSTORE_PASSWORD}
    KAFKA_SASL_ENABLED_MECHANISMS: SCRAM-SHA-512
```

#### MinIO TLS
```yaml
minio:
  command: server /data --console-address ":9001" --certs-dir /etc/minio/certs
  volumes:
    - ./certs:/etc/minio/certs:ro
```

#### PostgreSQL SSL
```yaml
postgres:
  volumes:
    - ./postgres-certs:/etc/postgresql/certs:ro
  command: -c ssl=on -c ssl_cert_file=/etc/postgresql/certs/server.crt -c ssl_key_file=/etc/postgresql/certs/server.key
```

### High Availability

#### Kafka Multi-Broker
```yaml
kafka-1:
  image: confluentinc/cp-kafka:7.5.0
  environment:
    KAFKA_BROKER_ID: 1
    KAFKA_ZOOKEEPER_CONNECT: 'zookeeper:2181'
    # ...

kafka-2:
  image: confluentinc/cp-kafka:7.5.0
  environment:
    KAFKA_BROKER_ID: 2
    KAFKA_ZOOKEEPER_CONNECT: 'zookeeper:2181'
    # ...

kafka-3:
  image: confluentinc/cp-kafka:7.5.0
  environment:
    KAFKA_BROKER_ID: 3
    KAFKA_ZOOKEEPER_CONNECT: 'zookeeper:2181'
    # ...
```

#### Zookeeper Ensemble
```yaml
zookeeper-1:
  image: confluentinc/cp-zookeeper:7.5.0
  environment:
    ZOOKEEPER_SERVER_ID: 1
    ZOOKEEPER_SERVERS: zookeeper-1:2888:3888;zookeeper-2:2888:3888;zookeeper-3:2888:3888

zookeeper-2:
  # ...

zookeeper-3:
  # ...
```

#### Spark HA
```yaml
# Use Kubernetes or YARN for HA Spark
# For standalone: multiple masters with ZooKeeper
spark-master-1:
  environment:
    SPARK_MASTER_HOST: spark-master-1
    SPARK_MASTER_PORT: 7077
    SPARK_MASTER_WEBUI_PORT: 8080
    SPARK_DAEMON_JAVA_OPTS: "-Dspark.deploy.recoveryMode=ZOOKEEPER -Dspark.deploy.zookeeper.url=zookeeper:2181"
```

#### PostgreSQL HA
```yaml
# Use Patroni or cloud-managed PostgreSQL (RDS, Cloud SQL)
# Add PgBouncer for connection pooling
pgbouncer:
  image: edoburu/pgbouncer:1.18
  environment:
    DATABASES_HOST: postgres
    DATABASES_PORT: 5432
    DATABASES_DBNAME: streaming_metrics
    POOL_MODE: transaction
    MAX_CLIENT_CONN: 1000
    DEFAULT_POOL_SIZE: 25
```

### Resource Limits

```yaml
# docker-compose.yml - Add resource limits
services:
  kafka:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G

  spark-master:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G

  spark-worker-1:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G

  flink-jobmanager:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G

  flink-taskmanager:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
```

## Configuration Files

### Producer Config
```python
# producer/producer.py - Modify PRODUCE_INTERVAL_MS
PRODUCE_INTERVAL_MS = 200  # 5 events/sec
```

### Spark Config
```python
# spark_streaming/structured_streaming.py
# All configuration at top of file
```

### Flink Config
```java
// flink_job/WebEventsFlinkJob.java
// Modify ParameterTool defaults
```

### Prometheus Rules
```yaml
# prometheus/rules/streaming.yml
groups:
  - name: streaming-alerts
    rules:
      - alert: HighConsumerLag
        expr: kafka_consumergroup_lag > 10000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High consumer lag on {{ $labels.consumergroup }}"
```

Add to prometheus.yml:
```yaml
rule_files:
  - 'rules/*.yml'
```

## Secrets Management

### Docker Secrets
```yaml
# docker-compose.yml
secrets:
  postgres_password:
    file: ./secrets/postgres_password.txt
  minio_secret_key:
    file: ./secrets/minio_secret_key.txt

services:
  postgres:
    secrets:
      - postgres_password
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password

  minio:
    secrets:
      - minio_secret_key
    environment:
      MINIO_SECRET_KEY_FILE: /run/secrets/minio_secret_key
```

### External Secrets (HashiCorp Vault, AWS Secrets Manager)
```yaml
# Use CSI drivers or sidecar injectors
# Example with Vault Agent Injector
annotations:
  vault.hashicorp.com/role: "streaming-pipeline"
  vault.hashicorp.com/agent-inject: "true"
  vault.hashicorp.com/agent-inject-secret-config: "secret/data/streaming-pipeline"
```

## Validation

### Test Configuration
```bash
# Validate docker-compose
docker compose config

# Validate Prometheus
docker run --rm -v $(pwd)/prometheus:/etc/prometheus prom/prometheus:v2.48.0 promtool check config /etc/prometheus/prometheus.yml

# Validate Grafana datasources
curl -X POST http://admin:admin123@localhost:3000/api/datasources \
  -H "Content-Type: application/json" \
  -d @grafana/datasources/datasources.yml
```

### Dry Run
```bash
# Test producer without sending
python producer.py --max-events 10 --bootstrap-servers localhost:9092

# Test Spark job locally (without cluster)
spark-submit --master local[*] structured_streaming.py
```