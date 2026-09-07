# Kafka Producer

## Overview

The Python producer generates realistic web clickstream events and sends them to the Kafka `web-events` topic. It simulates a real-world web application with various event types, user contexts, and metadata.

## File Location

```
producer/
├── producer.py          # Main producer script
└── requirements.txt     # Python dependencies
```

## Event Schema

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
  "utm_campaign": "summer_sale"
}
```

### Event Types & Probabilities

| Event Type | Probability | Description |
|------------|-------------|-------------|
| `page_view` | 40% | User views a page |
| `click` | 15% | User clicks an element |
| `scroll` | 10% | User scrolls page |
| `add_to_cart` | 5% | Product added to cart |
| `remove_from_cart` | 2% | Product removed from cart |
| `begin_checkout` | 3% | Checkout initiated |
| `purchase` | 2% | Purchase completed |
| `search` | 5% | Search performed |
| `filter` | 3% | Filter applied |
| `sort` | 2% | Results sorted |
| `share` | 1% | Content shared |
| `like` | 1% | Content liked |
| `comment` | 1% | Comment posted |
| `download` | 1% | File downloaded |
| `video_play` | 2% | Video started |
| `video_pause` | 1% | Video paused |
| `video_complete` | 1% | Video finished |
| `form_submit` | 2% | Form submitted |
| `form_abandon` | 1% | Form abandoned |
| `error` | 3% | Error occurred |

### Event-Specific Fields

| Event Type | Additional Fields |
|------------|-------------------|
| `add_to_cart` | `product_id`, `quantity`, `price` |
| `purchase` | `order_id`, `total_amount`, `currency`, `items_count` |
| `search` | `search_query`, `results_count` |
| `video_play` | `video_id`, `video_duration` |
| `error` | `error_code`, `error_message` |

## Producer Configuration

```python
producer_config = {
    'bootstrap.servers': 'localhost:9092',
    'client.id': 'web-events-producer',
    'acks': 'all',                      # Wait for all replicas
    'retries': 3,
    'retry.backoff.ms': 100,
    'batch.size': 16384,                # 16KB batches
    'linger.ms': 10,                    # Wait up to 10ms to batch
    'buffer.memory': 33554432,          # 32MB buffer
    'compression.type': 'snappy',       # Fast compression
    'max.in.flight.requests.per.connection': 5,
    'enable.idempotence': True,         # Exactly-once semantics
}
```

### Key Settings Explained

| Setting | Value | Reason |
|---------|-------|--------|
| `acks=all` | Wait for all in-sync replicas | Durability |
| `enable.idempotence=true` | Enable idempotent producer | Exactly-once |
| `compression.type=snappy` | Snappy compression | Speed + ratio |
| `linger.ms=10` | Batch wait time | Throughput |
| `batch.size=16384` | Batch size | Balance latency/throughput |

## Running the Producer

### Basic Usage

```bash
cd producer
python producer.py --create-topic
```

### Options

```bash
python producer.py --help

Options:
  --bootstrap-servers    Kafka bootstrap servers (default: localhost:9092)
  --topic                Topic name (default: web-events)
  --interval             Interval between events in ms (default: 200)
  --max-events           Maximum events to produce (default: unlimited)
  --create-topic         Create topic before producing
```

### Examples

```bash
# High throughput (50 events/sec)
python producer.py --interval 20 --max-events 100000

# Low throughput (1 event/sec) for testing
python producer.py --interval 1000 --max-events 100

# Custom Kafka cluster
python producer.py --bootstrap-servers kafka1:9092,kafka2:9092,kafka3:9092

# Different topic
python producer.py --topic my-web-events --create-topic
```

## Code Structure

### Main Classes

```python
class WebEventProducer:
    def __init__(self, bootstrap_servers, topic):
        # Initialize producer with config
        # Setup signal handlers for graceful shutdown
    
    def generate_event(self) -> dict:
        # Generate realistic event with all fields
        # Weighted event type selection
        # Event-specific enrichment
    
    def produce_events(self, interval_ms, max_events):
        # Main production loop
        # Calls generate_event()
        # Produces to Kafka with delivery callback
        # Handles shutdown signals
    
    def shutdown(self):
        # Flush pending messages
        # Close producer
```

### Event Generation

```python
def generate_event(self):
    # 1. Base fields (timestamp, IDs)
    # 2. Page selection (weighted by popularity)
    # 3. Event type selection (weighted probabilities)
    # 4. User context (device, browser, OS, country)
    # 5. Marketing attribution (UTM parameters)
    # 6. Event-specific enrichment
    return event
```

## Monitoring & Metrics

### Delivery Reports

The producer tracks:
- `events_sent`: Successfully delivered messages
- `errors`: Failed deliveries

```python
def _delivery_report(self, err, msg):
    if err is not None:
        self.errors += 1
        print(f"Message delivery failed: {err}")
    else:
        self.events_sent += 1
        if self.events_sent % 1000 == 0:
            print(f"Sent {self.events_sent} events (errors: {self.errors})")
```

### Prometheus Metrics (Optional)

Add to producer for metrics export:

```python
from prometheus_client import Counter, Histogram, start_http_server

EVENTS_SENT = Counter('producer_events_sent_total', 'Total events sent')
EVENTS_FAILED = Counter('producer_events_failed_total', 'Total events failed')
PRODUCE_LATENCY = Histogram('producer_produce_latency_seconds', 'Produce latency')

# In delivery callback
EVENTS_SENT.inc()  # or EVENTS_FAILED.inc()

# Start metrics server
start_http_server(8000)
```

## Performance Tuning

### High Throughput

```python
producer_config = {
    'bootstrap.servers': 'kafka:29092',
    'acks': '1',              # Faster, less durable
    'batch.size': 65536,      # 64KB batches
    'linger.ms': 50,          # Longer batching
    'buffer.memory': 67108864, # 64MB buffer
    'compression.type': 'zstd', # Better compression
    'enable.idempotence': False, # Higher throughput
}
```

### Low Latency

```python
producer_config = {
    'bootstrap.servers': 'kafka:29092',
    'acks': 'all',
    'batch.size': 1024,       # Small batches
    'linger.ms': 1,           # Minimal batching
    'enable.idempotence': True,
}
```

### Producer Scaling

Run multiple producer instances:

```bash
# Terminal 1
python producer.py --interval 100 --max-events 100000 &

# Terminal 2
python producer.py --interval 100 --max-events 100000 &

# Terminal 3
python producer.py --interval 100 --max-events 100000 &
```

Each instance gets its own client ID and partitions data by `user_id` key.

## Testing

### Unit Tests

```python
# test_producer.py
import pytest
from producer import WebEventProducer

def test_generate_event():
    producer = WebEventProducer("localhost:9092", "test-topic")
    event = producer.generate_event()
    
    assert "event_id" in event
    assert "timestamp" in event
    assert "user_id" in event
    assert event["event_type"] in EVENT_TYPES
    assert event["page"] in PAGES

def test_event_schema():
    producer = WebEventProducer("localhost:9092", "test-topic")
    event = producer.generate_event()
    
    # Required fields
    required = ["event_id", "timestamp", "user_id", "session_id", "page", "event_type"]
    for field in required:
        assert field in event
        assert event[field] is not None
```

### Integration Test

```bash
# Produce test events
python producer.py --max-events 100 --bootstrap-servers localhost:9092

# Verify in Kafka
docker exec kafka kafka-console-consumer \
  --topic web-events \
  --from-beginning \
  --max-messages 100 \
  --bootstrap-server localhost:9092
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `Connection refused` | Check Kafka is running: `docker compose ps kafka` |
| `Topic not found` | Run with `--create-topic` flag |
| High error rate | Check Kafka logs, increase retries |
| Slow production | Reduce `linger.ms`, check network |
| Memory growth | Ensure `flush()` called on shutdown |

## Extending the Producer

### Add New Event Types

```python
# In producer.py
EVENT_TYPES = [
    # ... existing types
    "wishlist_add",
    "wishlist_remove",
    "review_submit",
]

# Add weights in generate_event()
if random.random() < 0.02:
    event_type = "wishlist_add"
```

### Add New Fields

```python
def generate_event(self):
    event = {
        # ... existing fields
        "custom_field": "custom_value",
        "ab_test_variant": random.choice(["A", "B", "control"]),
    }
```

### Custom Partitioning

```python
# Partition by session for session ordering
key = event["session_id"].encode('utf-8')

# Or custom partitioner
def custom_partitioner(key, all_partitions, available):
    # Consistent hashing
    return hash(key) % len(available)
```

## Dependencies

```
confluent-kafka==2.4.0   # High-performance Kafka client
python-dotenv==1.0.0     # Environment variable loading
```

Install:
```bash
pip install -r requirements.txt
```