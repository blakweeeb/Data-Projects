# Prerequisites

## System Requirements

### Minimum Hardware
| Resource | Development | Production (Small) |
|----------|-------------|-------------------|
| CPU | 4 cores | 16 cores |
| RAM | 8 GB | 64 GB |
| Disk | 20 GB SSD | 500 GB NVMe |
| Network | 1 Gbps | 10 Gbps |

### Required Software
- **Docker Engine** 24.0+
- **Docker Compose** v2.20+
- **Git** 2.40+
- **Python** 3.11+ (for producer)
- **Java** 11+ (for Flink build)
- **Maven** 3.9+ (for Flink build)

## Installation

### Docker & Docker Compose

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker

# macOS (with Homebrew)
brew install docker docker-compose

# Windows
# Download Docker Desktop from https://docker.com/products/docker-desktop
```

Verify installation:
```bash
docker --version
docker compose version
docker run --rm hello-world
```

### Python (Producer)

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y python3.11 python3.11-venv

# macOS
brew install python@3.11

# Windows
# Download from https://python.org/downloads
```

Create virtual environment:
```bash
cd producer
python3.11 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

### Java & Maven (Flink)

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y openjdk-11-jdk maven

# macOS
brew install openjdk@11 maven

# Windows
# Download from https://adoptium.net/ and https://maven.apache.org/
```

Verify:
```bash
java -version
mvn -version
```

## Port Requirements

Ensure these ports are available on the host:

| Port | Service | Purpose |
|------|---------|---------|
| 3000 | Grafana | Web UI |
| 5432 | PostgreSQL | Database |
| 7077 | Spark Master | Job submission |
| 8080 | Spark Master UI | Monitoring |
| 8081 | Flink JobManager UI | Monitoring |
| 9000 | MinIO API | S3 API |
| 9001 | MinIO Console | Admin UI |
| 9090 | Prometheus | Metrics UI |
| 9092 | Kafka | Client access |
| 9100 | Node Exporter | Host metrics |
| 9101 | Kafka JMX | Kafka metrics |
| 9308 | Kafka Exporter | Consumer lag metrics |
| 2181 | Zookeeper | Coordination |

Check port availability:
```bash
# Linux/macOS
for port in 3000 5432 7077 8080 8081 9000 9001 9090 9092 9100 9101 9308 2181; do
  if lsof -i :$port > /dev/null; then
    echo "Port $port is in use"
  else
    echo "Port $port is free"
  fi
done

# Windows (PowerShell)
3000,5432,7077,8080,8081,9000,9001,9090,9092,9100,9101,9308,2181 | ForEach-Object {
  if (Get-NetTCPConnection -LocalPort $_ -ErrorAction SilentlyContinue) {
    Write-Host "Port $_ is in use"
  } else {
    Write-Host "Port $_ is free"
  }
}
```

## Network Configuration

### Docker Network
The stack uses a custom bridge network `streaming-network`. All services communicate via service names.

### Firewall Rules (Production)
```bash
# Allow internal communication
# Allow external access to:
# - Grafana (3000)
# - Prometheus (9090) - restrict to monitoring network
# - Kafka (9092) - restrict to producer/consumer networks
# - MinIO (9000/9001) - restrict to application network
```

## Resource Allocation

### Docker Desktop (Mac/Windows)
Increase resources in Docker Desktop settings:
- **CPUs**: 4+ (8 for production)
- **Memory**: 8 GB+ (16 GB for production)
- **Disk**: 64 GB+ (200 GB for production)

### Linux (Systemd)
```bash
# /etc/docker/daemon.json
{
  "default-ulimits": {
    "nofile": { "Name": "nofile", "Hard": 65536, "Soft": 65536 }
  }
}
sudo systemctl restart docker
```

### Kernel Parameters (Production)
```bash
# /etc/sysctl.d/99-streaming.conf
vm.max_map_count=262144
fs.file-max=1000000
net.core.somaxconn=65535
net.ipv4.tcp_max_syn_backlog=65535

sudo sysctl --system
```

## Environment Variables

Create `.env` file in project root (optional):
```bash
# .env
COMPOSE_PROJECT_NAME=streaming-pipeline
KAFKA_BOOTSTRAP_SERVERS=kafka:29092
MINIO_ENDPOINT=http://minio:9000
POSTGRES_PASSWORD=your-secure-password
GRAFANA_ADMIN_PASSWORD=your-secure-password
```

## Verification Checklist

Before starting, verify:
- [ ] Docker and Docker Compose installed
- [ ] Python 3.11+ with venv
- [ ] Java 11+ and Maven (for Flink)
- [ ] All required ports available
- [ ] Sufficient disk space (20 GB+)
- [ ] Sufficient memory (8 GB+ allocated to Docker)
- [ ] Network connectivity (for image pulls)
- [ ] Git configured

## Next Steps

Proceed to [Quick Start](quick-start.md) to deploy the pipeline.