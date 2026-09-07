# Architecture Overview

## System Architecture

The streaming pipeline follows a modern **Lambda-inspired architecture** with real-time processing at its core:

```
┌─────────────┐     ┌──────────────┐     ┌────────────────────────┐
│   Producer  │────▶│    Kafka     │────▶│  Stream Processors     │
│  (Python)   │     │  (3 partitions)  │  │  ┌────────┐ ┌────────┐ │
└─────────────┘     └──────────────┘     │  │ Spark  │ │ Flink  │ │
                                          │  │Struct. │ │        │ │
                                          │  │Stream. │ │        │ │
                                          │  └────┬───┘ └────┬───┘ │
                                          └───────┼─────────┼─────┘
                                                  ▼         ▼
                                    ┌─────────────────────────────┐
                                    │      Storage Layer          │
                                    │  ┌──────────┐ ┌──────────┐  │
                                    │  │  MinIO   │ │PostgreSQL│  │
                                    │  │ (Parquet)│ │(Metrics) │  │
                                    │  └──────────┘ └──────────┘  │
                                    └─────────────────────────────┘
                                                  ▼         ▼
                                    ┌─────────────────────────────┐
                                    │    Observability            │
                                    │  ┌──────────┐ ┌──────────┐  │
                                    │  │Prometheus│ │ Grafana  │  │
                                    │  │          │ │          │  │
                                    │  └──────────┘ └──────────┘  │
                                    └─────────────────────────────┘
```

## Design Principles

### 1. **Event-Driven & Decoupled**
- Kafka acts as the central nervous system
- Producers and consumers are completely independent
- Easy to add new consumers without affecting existing ones

### 2. **Exactly-Once Processing**
- Kafka transactions for producer idempotency
- Spark checkpointing to S3/MinIO
- Flink checkpointing with Kafka transactions
- PostgreSQL upserts with conflict handling

### 3. **Scalable & Resilient**
- Horizontal scaling via Kafka partitions
- Spark/Flink parallelism matches partition count
- Automatic failover with Zookeeper/Kubernetes (production)

### 4. **Multi-Format Storage**
- **MinIO/Parquet**: Data lake for historical analysis, ML training
- **PostgreSQL**: Real-time dashboards, ad-hoc queries

### 5. **Observable by Default**
- Every component exports Prometheus metrics
- Pre-built Grafana dashboards
- Structured logging throughout

## Component Responsibilities

| Component | Responsibility | Scaling Strategy |
|-----------|---------------|------------------|
| **Producer** | Generate realistic events | Run multiple instances |
| **Kafka** | Durable event log, buffering | Add partitions/brokers |
| **Spark** | Windowed aggregations, ETL | Add workers, increase cores |
| **Flink** | Alternative processor, exactly-once | Add task managers/slots |
| **MinIO** | Object storage for Parquet | Add nodes, erasure coding |
| **PostgreSQL** | Fast metric queries | Read replicas, partitioning |
| **Prometheus** | Metrics collection | Federation for scale |
| **Grafana** | Visualization | Stateless, horizontally scalable |

## Data Guarantees

| Guarantee | Implementation |
|-----------|----------------|
| **At-least-once** | Default Kafka producer (acks=1) |
| **Exactly-once** | Idempotent producer + transactional sinks |
| **No data loss** | Kafka replication factor 3 (production) |
| **Ordering** | Per-partition ordering by user_id key |
| **Late events** | 2-minute watermark in Spark/Flink |

## Failure Scenarios & Handling

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Producer crash | Prometheus up metric | Restart producer, Kafka buffers |
| Kafka broker down | ISR shrink alerts | ISR reassignment, replica promotion |
| Spark executor OOM | Executor lost alerts | Dynamic allocation, memory tuning |
| Flink checkpoint fail | Checkpoint duration alert | Increase timeout, fix state backend |
| MinIO disk full | Disk usage alert | Add capacity, lifecycle policies |
| PostgreSQL overload | Connection pool exhaustion | Read replicas, query optimization |

## Network Topology

All services communicate via Docker network `streaming-network`:

```
Service              | Internal Port | External Port | Purpose
---------------------|---------------|---------------|--------
Kafka                | 29092         | 9092          | Client access
Zookeeper            | 2181          | 2181          | Coordination
Spark Master         | 7077          | 7077          | Job submission
Spark Master UI      | 8080          | 8080          | Monitoring
Flink JobManager     | 8081          | 8081          | Job management
MinIO API            | 9000          | 9000          | S3 API
MinIO Console        | 9001          | 9001          | Admin UI
PostgreSQL           | 5432          | 5432          | SQL access
Prometheus           | 9090          | 9090          | Metrics UI
Grafana              | 3000          | 3000          | Dashboards
Kafka Exporter       | 9308          | 9308          | Kafka metrics
Node Exporter        | 9100          | 9100          | Host metrics
```

## Security Considerations (Production)

> ⚠️ **Current configuration is for development only**

For production deployment:
- Enable SASL/SSL for Kafka
- Use Kerberos or OAuth for authentication
- Enable TLS for all service communication
- Use secrets management (HashiCorp Vault, AWS Secrets Manager)
- Restrict network with security groups/firewalls
- Enable MinIO encryption at rest
- Use PostgreSQL SSL certificates
- Configure Grafana with SSO (OAuth, SAML, LDAP)

## Capacity Planning

| Metric | Development | Production (Small) | Production (Large) |
|--------|-------------|-------------------|-------------------|
| Events/sec | ~5 | 10,000 | 1,000,000+ |
| Kafka partitions | 3 | 50 | 500+ |
| Spark executors | 2 | 10 | 100+ |
| Flink task slots | 4 | 40 | 400+ |
| MinIO storage | 10 GB | 10 TB | 1 PB+ |
| PostgreSQL | 1 GB | 500 GB | 10 TB+ |
| Retention | 7 days | 90 days | 365+ days |