# Load Testing

## Overview

This guide covers load testing the streaming pipeline to validate performance, identify bottlenecks, and ensure the system meets throughput and latency requirements under various load conditions.

## Load Testing Strategy

### Test Types

| Test Type | Purpose | Duration | Load Pattern |
|-----------|---------|----------|--------------|
| **Baseline** | Establish normal performance | 10 min | Steady 5 eps |
| **Stress** | Find breaking point | 30 min | Ramp to max |
| **Soak** | Stability over time | 4-24 hours | Steady 80% max |
| **Spike** | Burst handling | 15 min | Sudden 10x |
| **Recovery** | Failure recovery | 20 min | Kill/restore |

### Key Metrics to Monitor

| Category | Metrics |
|----------|---------|
| **Throughput** | Events/sec produced, consumed, processed |
| **Latency** | End-to-end, batch processing, queue time |
| **Resources** | CPU, memory, disk, network per component |
| **Errors** | Failed batches, dropped events, retries |
| **Backpressure** | Queue depths, lag, processing delays |

## Load Test Tools

### 1. Producer-Based Load Generator

```python
# load_test_producer.py
import time
import json
import random
import argparse
import threading
from datetime import datetime
from confluent_kafka import Producer
from collections import defaultdict

class LoadTestProducer:
    def __init__(self, bootstrap_servers, topic, num_producers=1):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.num_producers = num_producers
        self.producers = []
        self.stats = defaultdict(lambda: {"sent": 0, "errors": 0, "latencies": []})
        self.running = True
        
        # Create multiple producers for parallelism
        for i in range(num_producers):
            p = Producer({
                'bootstrap.servers': bootstrap_servers,
                'client.id': f'load-test-producer-{i}',
                'acks': 'all',
                'linger.ms': 1,
                'batch.size': 16384,
                'compression.type': 'snappy',
                'enable.idempotence': True,
            })
            self.producers.append(p)
    
    def generate_event(self, producer_id, sequence):
        return {
            "event_id": f"load_{producer_id}_{sequence}_{int(time.time()*1000)}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_id": f"user_{random.randint(1, 100000)}",
            "session_id": f"session_{random.randint(1, 500000)}",
            "page": random.choice([
                "/home", "/products", "/cart", "/checkout", "/profile",
                "/search", "/category/electronics", "/category/clothing",
                "/product/12345", "/product/67890", "/login", "/register"
            ]),
            "event_type": random.choices(
                ["page_view", "click", "scroll", "add_to_cart", "purchase", "search", "error"],
                weights=[40, 15, 10, 5, 2, 5, 3]
            )[0],
            "device_type": random.choice(["desktop", "mobile", "tablet"]),
            "browser": random.choice(["Chrome", "Firefox", "Safari", "Edge"]),
            "os": random.choice(["Windows 10", "Windows 11", "macOS", "Linux", "iOS", "Android"]),
            "country": random.choice(["US", "CA", "GB", "DE", "FR", "JP", "BR", "IN"]),
            "load_test": True,
            "producer_id": producer_id,
            "sequence": sequence,
            "produce_ns": time.time_ns()
        }
    
    def produce_worker(self, producer_id, target_eps, duration_sec):
        """Worker function for a single producer."""
        producer = self.producers[producer_id]
        interval = 1.0 / target_eps if target_eps > 0 else 0
        start_time = time.time()
        sequence = 0
        
        def delivery_report(err, msg):
            if err:
                self.stats[producer_id]["errors"] += 1
            else:
                self.stats[producer_id]["sent"] += 1
                # Calculate produce latency
                key = msg.key().decode('utf-8')
                # Note: would need to track send time per message for accurate latency
        
        while self.running and (time.time() - start_time) < duration_sec:
            event = self.generate_event(producer_id, sequence)
            
            send_time = time.time_ns()
            producer.produce(
                self.topic,
                key=event["user_id"].encode('utf-8'),
                value=json.dumps(event).encode('utf-8'),
                callback=delivery_report
            )
            producer.poll(0)
            
            self.stats[producer_id]["latencies"].append(time.time_ns() - send_time)
            sequence += 1
            
            if interval > 0:
                time.sleep(interval)
        
        producer.flush()
    
    def run_load_test(self, target_eps_per_producer, duration_sec, ramp_up_sec=0):
        """Run load test with optional ramp-up."""
        print(f"Starting load test: {self.num_producers} producers, "
              f"{target_eps_per_producer} eps each, {duration_sec}s duration")
        
        if ramp_up_sec > 0:
            print(f"Ramp-up: {ramp_up_sec}s")
        
        threads = []
        for i in range(self.num_producers):
            # Stagger start for ramp-up
            if ramp_up_sec > 0:
                delay = (i / self.num_producers) * ramp_up_sec
            else:
                delay = 0
            
            def delayed_start(pid, delay):
                if delay > 0:
                    time.sleep(delay)
                self.produce_worker(pid, target_eps_per_producer, duration_sec)
            
            t = threading.Thread(target=delayed_start, args=(i, delay))
            t.start()
            threads.append(t)
        
        # Monitor progress
        monitor_thread = threading.Thread(target=self.monitor_progress, args=(duration_sec + ramp_up_sec,))
        monitor_thread.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        self.running = False
        monitor_thread.join()
        
        self.print_summary()
    
    def monitor_progress(self, total_duration):
        """Print progress every 10 seconds."""
        start = time.time()
        while self.running and (time.time() - start) < total_duration:
            time.sleep(10)
            total_sent = sum(s["sent"] for s in self.stats.values())
            total_errors = sum(s["errors"] for s in self.stats.values())
            elapsed = time.time() - start
            print(f"[{elapsed:.0f}s] Sent: {total_sent}, Errors: {total_errors}, "
                  f"Rate: {total_sent/elapsed:.1f} eps")
    
    def print_summary(self):
        total_sent = sum(s["sent"] for s in self.stats.values())
        total_errors = sum(s["errors"] for s in self.stats.values())
        all_latencies = []
        for s in self.stats.values():
            all_latencies.extend(s["latencies"])
        
        print("\n=== Load Test Summary ===")
        print(f"Total events sent: {total_sent}")
        print(f"Total errors: {total_errors}")
        print(f"Error rate: {total_errors/max(total_sent,1)*100:.2f}%")
        
        if all_latencies:
            latencies_ms = [l/1e6 for l in all_latencies]
            print(f"Produce latency (ms): "
                  f"avg={sum(latencies_ms)/len(latencies_ms):.2f}, "
                  f"p50={sorted(latencies_ms)[len(latencies_ms)//2]:.2f}, "
                  f"p99={sorted(latencies_ms)[int(len(latencies_ms)*0.99)]:.2f}, "
                  f"max={max(latencies_ms):.2f}")

def main():
    parser = argparse.ArgumentParser(description="Kafka Load Test Producer")
    parser.add_argument("--bootstrap-servers", default="localhost:9092")
    parser.add_argument("--topic", default="web-events")
    parser.add_argument("--producers", type=int, default=1, help="Number of parallel producers")
    parser.add_argument("--eps", type=int, default=1000, help="Events per second per producer")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds")
    parser.add_argument("--ramp-up", type=int, default=0, help="Ramp-up time in seconds")
    
    args = parser.parse_args()
    
    tester = LoadTestProducer(args.bootstrap_servers, args.topic, args.producers)
    tester.run_load_test(args.eps, args.duration, args.ramp_up)

if __name__ == "__main__":
    main()
```

Run:
```bash
# Baseline test
python load_test_producer.py --producers 1 --eps 5 --duration 600

# Stress test (ramp to 10,000 eps)
python load_test_producer.py --producers 4 --eps 2500 --duration 1800 --ramp-up 300

# Spike test
python load_test_producer.py --producers 2 --eps 50000 --duration 60
```

### 2. Kafka Producer Performance Test

```bash
# Built-in Kafka producer performance test
docker exec kafka kafka-producer-perf-test \
  --topic web-events \
  --num-records 1000000 \
  --record-size 1024 \
  --throughput 10000 \
  --producer-props bootstrap.servers=localhost:9092 acks=all

# Consumer performance test
docker exec kafka kafka-consumer-perf-test \
  --topic web-events \
  --messages 1000000 \
  --bootstrap-server localhost:9092 \
  --group load-test-consumer
```

### 3. Spark Load Test

Submit job with higher load:

```bash
# Increase Spark parallelism for load test
docker exec -it spark-master spark-submit \
  --master spark://spark-master:7077 \
  --conf spark.sql.shuffle.partitions=16 \
  --conf spark.default.parallelism=16 \
  --conf spark.executor.memory=4g \
  --conf spark.executor.cores=2 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,\
org.apache.hadoop:hadoop-aws:3.3.4,\
com.amazonaws:aws-java-sdk-bundle:1.12.262,\
org.postgresql:postgresql:42.7.3 \
  /opt/spark-apps/structured_streaming.py
```

## Load Test Scenarios

### Scenario 1: Baseline (Development)

```bash
#!/bin/bash
# baseline_test.sh

echo "=== BASELINE LOAD TEST ==="
echo "Target: 5 eps, 10 minutes"

# Start producer
cd producer
python load_test_producer.py \
  --producers 1 \
  --eps 5 \
  --duration 600 \
  --bootstrap-servers localhost:9092 &

PRODUCER_PID=$!

# Monitor Kafka lag
echo "Monitoring consumer lag..."
for i in {1..60}; do
  sleep 10
  LAG=$(docker exec kafka kafka-consumer-groups \
    --bootstrap-server localhost:9092 \
    --describe --group spark-streaming-consumer 2>/dev/null | \
    awk '/web-events/ {sum+=$6} END {print sum}')
  echo "[$(($i*10))s] Consumer lag: ${LAG:-0}"
done

wait $PRODUCER_PID
echo "Baseline test complete"
```

### Scenario 2: Stress Test (Find Limits)

```bash
#!/bin/bash
# stress_test.sh

echo "=== STRESS TEST ==="
echo "Ramping from 100 to 50,000 eps over 30 minutes"

# Phase 1: Warm-up (100 eps for 5 min)
echo "Phase 1: Warm-up (100 eps)"
python load_test_producer.py --producers 1 --eps 100 --duration 300 &

sleep 300

# Phase 2: Ramp up
for eps in 500 1000 2500 5000 10000 25000 50000; do
  echo "Phase: $eps eps"
  python load_test_producer.py --producers 4 --eps $((eps/4)) --duration 180 &
  sleep 180
  
  # Check lag
  LAG=$(docker exec kafka kafka-consumer-groups \
    --bootstrap-server localhost:9092 \
    --describe --group spark-streaming-consumer 2>/dev/null | \
    awk '/web-events/ {sum+=$6} END {print sum}')
  
  echo "  Lag at $eps eps: ${LAG:-0}"
  
  if [ ${LAG:-0} -gt 100000 ]; then
    echo "  ⚠️  Lag exceeded 100k, stopping stress test"
    break
  fi
done

echo "Stress test complete"
```

### Scenario 3: Soak Test (Stability)

```bash
#!/bin/bash
# soak_test.sh

echo "=== SOAK TEST ==="
echo "Running at 80% capacity for 4 hours"

TARGET_EPS=4000  # 80% of observed max
DURATION=14400   # 4 hours

python load_test_producer.py \
  --producers 4 \
  --eps $((TARGET_EPS/4)) \
  --duration $DURATION \
  --bootstrap-servers localhost:9092 &

TEST_PID=$!

# Monitor every 5 minutes
echo "Monitoring stability..."
for i in {1..48}; do
  sleep 300
  
  # Check all components healthy
  docker compose ps --format "table {{.Name}}\t{{.Status}}"
  
  # Check lag
  LAG=$(docker exec kafka kafka-consumer-groups \
    --bootstrap-server localhost:9092 \
    --describe --group spark-streaming-consumer 2>/dev/null | \
    awk '/web-events/ {sum+=$6} END {print sum}')
  
  # Check Spark executors
  EXECUTORS=$(curl -s http://localhost:8080/api/v1/applications | \
    jq '.[] | select(.name=="WebEventsStreaming") | .attempts[0].sparkUser')
  
  echo "[$(($i*5))min] Lag: ${LAG:-0} | Executors: $EXECUTORS"
  
  # Alert if issues
  if [ ${LAG:-0} -gt 50000 ]; then
    echo "  ⚠️  HIGH LAG DETECTED"
  fi
done

wait $TEST_PID
echo "Soak test complete"
```

### Scenario 4: Spike Test

```bash
#!/bin/bash
# spike_test.sh

echo "=== SPIKE TEST ==="
echo "Normal load (100 eps) + 10x spike for 1 minute"

# Start baseline
python load_test_producer.py --producers 1 --eps 100 --duration 600 &
BASELINE_PID=$!

sleep 60

# Spike!
echo "🚀 SPIKE: 10,000 eps for 60 seconds"
python load_test_producer.py --producers 4 --eps 2500 --duration 60 &
SPIKE_PID=$!

wait $SPIKE_PID

# Continue baseline
echo "Returning to baseline..."
wait $BASELINE_PID

echo "Spike test complete - check recovery time"
```

## Monitoring During Load Tests

### Key Dashboards to Watch

1. **Grafana - Web Events Overview**
   - Kafka Throughput (should match producer rate)
   - Consumer Lag (should stay low)
   - Events per Page/Type (distribution)

2. **Grafana - Processing Metrics**
   - Spark Batch Latency (should stay < trigger interval)
   - Spark Batch Records (input ≈ output)
   - Flink Checkpoint Duration (if running)

3. **Prometheus Direct Queries**

```bash
# Watch in real-time
watch -n 5 'curl -s "http://localhost:9090/api/v1/query?query=kafka_consumergroup_lag{topic=\"web-events\"}" | jq ".data.result[] | {partition: .metric.partition, lag: .value[1]}"'

# Spark batch processing time
watch -n 5 'curl -s "http://localhost:9090/api/v1/query?query=rate(spark_streaming_batch_processing_latency_sum[1m])/rate(spark_streaming_batch_processing_latency_count[1m])" | jq ".data.result[0].value[1]"'

# System resources
watch -n 5 'curl -s "http://localhost:9090/api/v1/query?query=(1-(node_memory_MemAvailable_bytes/node_memory_MemTotal_bytes))*100" | jq ".data.result[0].value[1]"'
```

### Resource Monitoring Commands

```bash
# Docker stats for all containers
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"

# Kafka broker metrics
docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092

# Spark executor metrics (via UI)
# http://localhost:8080 → Application → Executors tab

# Flink task manager metrics
# http://localhost:8081 → Task Managers
```

## Analyzing Results

### Throughput Analysis

```python
# analyze_throughput.py
import json

def analyze_test_results(results_file):
    with open(results_file) as f:
        data = json.load(f)
    
    print("=== Throughput Analysis ===")
    for phase in data["phases"]:
        target = phase["target_eps"]
        actual = phase["actual_eps"]
        lag = phase["max_lag"]
        latency = phase["p99_latency"]
        errors = phase["error_rate"]
        
        efficiency = actual / target * 100
        print(f"Target: {target:>6} eps | Actual: {actual:>6.1f} eps | "
              f"Efficiency: {efficiency:>5.1f}% | "
              f"Max Lag: {lag:>6} | P99 Latency: {latency:.1f}s | Errors: {errors:.2f}%")
        
        if efficiency < 95:
            print("  ⚠️  Throughput below target")
        if lag > 10000:
            print("  ⚠️  High consumer lag")
        if latency > 90:
            print("  ⚠️  Latency SLO violation")

# Example results structure
results = {
    "phases": [
        {"target_eps": 100, "actual_eps": 99.5, "max_lag": 5, "p99_latency": 45, "error_rate": 0.0},
        {"target_eps": 1000, "actual_eps": 998.2, "max_lag": 12, "p99_latency": 52, "error_rate": 0.0},
        {"target_eps": 10000, "actual_eps": 9850.1, "max_lag": 150, "p99_latency": 68, "error_rate": 0.01},
        {"target_eps": 25000, "actual_eps": 22000.0, "max_lag": 5000, "p99_latency": 120, "error_rate": 0.05},
    ]
}
```

### Bottleneck Identification

| Symptom | Likely Bottleneck | Investigation |
|---------|-------------------|---------------|
| Lag grows linearly | Consumer slower than producer | Check Spark/Flink processing time |
| Lag spikes periodically | GC pauses | Check JVM heap, GC logs |
| Batch processing > trigger | Processing too slow | Optimize queries, add partitions |
| High CPU on Spark executors | CPU-bound processing | Add executors, optimize code |
| High memory on Spark | Memory pressure | Increase memory, reduce shuffle |
| Kafka disk I/O high | Disk bottleneck | Faster disks, more partitions |
| MinIO write latency high | Storage bottleneck | SSD, more nodes |
| PostgreSQL connections maxed | Connection pool | Add PgBouncer |

## Capacity Planning

### Scaling Rules

| Component | Scaling Trigger | Action |
|-----------|-----------------|--------|
| **Kafka** | Lag > 10k sustained | Add partitions, add brokers |
| **Spark** | Batch time > 50% trigger | Add executors, increase cores |
| **Flink** | Backpressure > 50% | Add task managers, increase slots |
| **MinIO** | Disk > 70% | Add nodes, enable tiering |
| **PostgreSQL** | Connections > 80% | Add PgBouncer, read replicas |

### Capacity Calculator

```python
def calculate_capacity(target_eps, event_size_kb=1):
    """
    Estimate resource requirements for target throughput.
    """
    # Kafka
    kafka_partitions = max(6, target_eps // 5000)
    kafka_brokers = max(3, kafka_partitions // 10)
    kafka_disk_gb_per_broker = target_eps * event_size_kb * 86400 * 7 / 1024 / 1024  # 7 days
    
    # Spark
    spark_executors = max(4, target_eps // 10000)
    spark_cores_per_executor = 4
    spark_memory_gb_per_executor = 8
    
    # Flink
    flink_task_slots = max(8, target_eps // 5000)
    flink_task_managers = max(2, flink_task_slots // 8)
    flink_memory_gb_per_tm = 8
    
    # MinIO
    minio_nodes = max(4, target_eps // 50000)
    minio_disk_tb_per_node = target_eps * event_size_kb * 86400 * 90 / 1024 / 1024 / 1024  # 90 days
    
    # PostgreSQL
    pg_max_connections = max(200, target_eps // 100)
    pg_shared_buffers_gb = 4
    
    return {
        "kafka": {
            "partitions": kafka_partitions,
            "brokers": kafka_brokers,
            "disk_gb_per_broker": round(kafka_disk_gb_per_broker, 1)
        },
        "spark": {
            "executors": spark_executors,
            "cores_per_executor": spark_cores_per_executor,
            "memory_gb_per_executor": spark_memory_gb_per_executor
        },
        "flink": {
            "task_slots": flink_task_slots,
            "task_managers": flink_task_managers,
            "memory_gb_per_tm": flink_memory_gb_per_tm
        },
        "minio": {
            "nodes": minio_nodes,
            "disk_tb_per_node": round(minio_disk_tb_per_node, 1)
        },
        "postgresql": {
            "max_connections": pg_max_connections,
            "shared_buffers_gb": pg_shared_buffers_gb
        }
    }

# Example: 100,000 eps
capacity = calculate_capacity(100000)
import json
print(json.dumps(capacity, indent=2))
```

## CI/CD Integration

### Automated Performance Tests

```yaml
# .github/workflows/load-test.yml
name: Load Test

on:
  workflow_dispatch:
    inputs:
      test_type:
        description: 'Test type'
        required: true
        type: choice
        options: [baseline, stress, soak, spike]

jobs:
  load-test:
    runs-on: [self-hosted, linux, x64]  # Needs Docker
    timeout-minutes: 300
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Start stack
        run: docker compose up -d --build
        
      - name: Wait for ready
        run: |
          sleep 60
          ./scripts/wait_for_ready.sh
      
      - name: Run load test
        run: |
          cd producer
          pip install -r requirements.txt
          python load_test_producer.py \
            --producers 4 \
            --eps ${{ github.event.inputs.eps }} \
            --duration ${{ github.event.inputs.duration }} \
            --ramp-up ${{ github.event.inputs.ramp_up }} \
            --output results.json
            
      - name: Collect metrics
        run: |
          ./scripts/collect_metrics.sh > metrics.json
          
      - name: Analyze results
        run: |
          python analyze_results.py results.json metrics.json
          
      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: load-test-results
          path: |
            results.json
            metrics.json
            
      - name: Cleanup
        if: always()
        run: docker compose down -v
```

## Reporting

### Load Test Report Template

```markdown
# Load Test Report: {{ Test Type }}

## Executive Summary
- **Date**: {{ Date }}
- **Duration**: {{ Duration }}
- **Target Throughput**: {{ Target EPS }} eps
- **Achieved Throughput**: {{ Actual EPS }} eps ({{ Efficiency }}%)
- **Max Latency (p99)**: {{ P99 Latency }}s
- **Max Consumer Lag**: {{ Max Lag }}
- **Error Rate**: {{ Error Rate }}%

## Test Configuration
- Producers: {{ Num Producers }}
- Kafka Partitions: {{ Partitions }}
- Spark Executors: {{ Executors }}
- Flink Task Slots: {{ Slots }}

## Results by Phase

| Phase | Target EPS | Actual EPS | Efficiency | Max Lag | P99 Latency | Errors |
|-------|------------|------------|------------|---------|-------------|--------|
| Warm-up | 100 | 99.5 | 99.5% | 5 | 45s | 0% |
| Load 1K | 1,000 | 998 | 99.8% | 12 | 52s | 0% |
| Load 10K | 10,000 | 9,850 | 98.5% | 150 | 68s | 0.01% |
| Load 25K | 25,000 | 22,000 | 88% | 5,000 | 120s | 0.05% |

## Bottlenecks Identified
1. **Spark batch processing** exceeds trigger interval at 25K eps
2. **Consumer lag** grows exponentially beyond 20K eps
3. **Memory pressure** on Spark executors at high load

## Recommendations
1. Increase Spark executors from 4 to 8 for >20K eps
2. Reduce window slide from 30s to 10s for lower latency
3. Add Kafka partitions (3 → 12) for better parallelism
4. Enable Spark adaptive query execution

## Graphs
![Throughput vs Lag](throughput_vs_lag.png)
![Latency Percentiles](latency_percentiles.png)
![Resource Utilization](resource_utilization.png)
```

## Best Practices

1. **Isolate test environment** - Don't test on production
2. **Warm up** - Run 5-10 minutes before measuring
3. **Monitor all layers** - Infrastructure → Platform → Application
4. **Test failure scenarios** - Kill broker, executor, task manager
5. **Document everything** - Reproducible results
6. **Compare baselines** - Track performance over time
7. **Automate** - CI/CD integration for regression detection