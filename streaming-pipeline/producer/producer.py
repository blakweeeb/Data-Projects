#!/usr/bin/env python3
"""
Kafka Producer for Web Events Streaming Pipeline
Generates realistic web clickstream events and sends them to Kafka topic 'web-events'
"""

import json
import time
import random
import signal
import sys
from datetime import datetime
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic


# Configuration
KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
TOPIC_NAME = "web-events"
PRODUCE_INTERVAL_MS = 200  # 200ms = 5 events per second
BATCH_SIZE = 100

# Realistic web pages and event types
PAGES = [
    "/home",
    "/products",
    "/products/electronics",
    "/products/clothing",
    "/products/books",
    "/cart",
    "/checkout",
    "/profile",
    "/settings",
    "/search",
    "/category/electronics",
    "/category/clothing",
    "/category/books",
    "/product/12345",
    "/product/67890",
    "/product/abcde",
    "/login",
    "/register",
    "/logout",
    "/about",
    "/contact",
    "/blog",
    "/blog/article-1",
    "/blog/article-2",
    "/help",
    "/faq",
]

EVENT_TYPES = [
    "page_view",
    "click",
    "scroll",
    "add_to_cart",
    "remove_from_cart",
    "begin_checkout",
    "purchase",
    "search",
    "filter",
    "sort",
    "share",
    "like",
    "comment",
    "download",
    "video_play",
    "video_pause",
    "video_complete",
    "form_submit",
    "form_abandon",
    "error",
]

# User agents for realism
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
]

# Referrers
REFERRERS = [
    "https://www.google.com/",
    "https://www.bing.com/",
    "https://duckduckgo.com/",
    "https://www.facebook.com/",
    "https://twitter.com/",
    "https://www.linkedin.com/",
    "https://www.reddit.com/",
    "direct",
    "https://newsletter.example.com/",
    "https://partner.example.com/",
]

# Countries for geo simulation
COUNTRIES = [
    "US", "CA", "GB", "DE", "FR", "ES", "IT", "NL", "BE", "CH",
    "AU", "JP", "KR", "BR", "MX", "AR", "IN", "SG", "HK", "AE"
]

DEVICES = ["desktop", "mobile", "tablet"]
BROWSERS = ["Chrome", "Firefox", "Safari", "Edge", "Opera"]
OS_LIST = ["Windows 10", "Windows 11", "macOS 14", "macOS 13", "Linux", "iOS 17", "Android 14", "iPadOS 17"]


class WebEventProducer:
    def __init__(self, bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS, topic=TOPIC_NAME):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.running = True
        self.events_sent = 0
        self.errors = 0
        
        # Producer configuration for reliability and performance
        self.producer_config = {
            'bootstrap.servers': bootstrap_servers,
            'client.id': 'web-events-producer',
            'acks': 'all',  # Wait for all replicas
            'retries': 3,
            'retry.backoff.ms': 100,
            'batch.size': 16384,
            'linger.ms': 10,
            'buffer.memory': 33554432,
            'compression.type': 'snappy',
            'max.in.flight.requests.per.connection': 5,
            'enable.idempotence': True,
        }
        
        self.producer = Producer(self.producer_config)
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Handle graceful shutdown"""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        print(f"\nReceived signal {signum}, shutting down gracefully...")
        self.running = False
    
    def _delivery_report(self, err, msg):
        """Callback for message delivery reports"""
        if err is not None:
            self.errors += 1
            print(f"Message delivery failed: {err}")
        else:
            self.events_sent += 1
            if self.events_sent % 1000 == 0:
                print(f"Sent {self.events_sent} events (errors: {self.errors})")
    
    def generate_event(self):
        """Generate a realistic web event"""
        now = datetime.utcnow()
        user_id = f"user_{random.randint(1, 10000)}"
        session_id = f"session_{random.randint(1, 50000)}"
        page = random.choice(PAGES)
        event_type = random.choice(EVENT_TYPES)
        
        # Weight event types - page views most common
        if random.random() < 0.4:
            event_type = "page_view"
        elif random.random() < 0.15:
            event_type = "click"
        elif random.random() < 0.1:
            event_type = "scroll"
        
        event = {
            "event_id": f"evt_{int(now.timestamp() * 1000)}_{random.randint(1000, 9999)}",
            "timestamp": now.isoformat() + "Z",
            "user_id": user_id,
            "session_id": session_id,
            "page": page,
            "event_type": event_type,
            "device_type": random.choice(DEVICES),
            "browser": random.choice(BROWSERS),
            "os": random.choice(OS_LIST),
            "country": random.choice(COUNTRIES),
            "referrer": random.choice(REFERRERS),
            "user_agent": random.choice(USER_AGENTS),
            "screen_resolution": f"{random.choice([1920, 1366, 1440, 1536, 390, 414, 820])}x{random.choice([1080, 768, 900, 864, 844, 896, 1180])}",
            "language": random.choice(["en-US", "en-GB", "es-ES", "fr-FR", "de-DE", "it-IT", "pt-BR", "ja-JP", "ko-KR", "zh-CN"]),
            "utm_source": random.choice(["google", "facebook", "twitter", "newsletter", "direct", "referral", "paid_search", None]) or None,
            "utm_medium": random.choice(["cpc", "organic", "social", "email", "referral", None]) or None,
            "utm_campaign": random.choice(["summer_sale", "black_friday", "new_arrivals", "brand_awareness", None]) or None,
        }
        
        # Add event-specific properties
        if event_type == "add_to_cart":
            event["product_id"] = f"prod_{random.randint(1000, 9999)}"
            event["quantity"] = random.randint(1, 5)
            event["price"] = round(random.uniform(10.0, 500.0), 2)
        elif event_type == "purchase":
            event["order_id"] = f"order_{random.randint(100000, 999999)}"
            event["total_amount"] = round(random.uniform(20.0, 2000.0), 2)
            event["currency"] = "USD"
            event["items_count"] = random.randint(1, 10)
        elif event_type == "search":
            event["search_query"] = random.choice(["laptop", "phone", "headphones", "shoes", "book", "watch", "tablet", "camera"])
            event["results_count"] = random.randint(0, 100)
        elif event_type == "video_play":
            event["video_id"] = f"vid_{random.randint(1000, 9999)}"
            event["video_duration"] = random.randint(30, 3600)
        elif event_type == "error":
            event["error_code"] = random.choice(["404", "500", "503", "timeout", "network_error"])
            event["error_message"] = random.choice(["Page not found", "Internal server error", "Service unavailable", "Request timeout", "Network error"])
        
        return event
    
    def produce_events(self, interval_ms=PRODUCE_INTERVAL_MS, max_events=None):
        """Main production loop"""
        print(f"Starting producer for topic '{self.topic}' on {self.bootstrap_servers}")
        print(f"Producing events every {interval_ms}ms...")
        print("Press Ctrl+C to stop\n")
        
        interval_sec = interval_ms / 1000.0
        event_count = 0
        
        try:
            while self.running:
                if max_events and event_count >= max_events:
                    break
                
                event = self.generate_event()
                
                # Produce message with key for partitioning
                self.producer.produce(
                    self.topic,
                    key=event["user_id"].encode('utf-8'),
                    value=json.dumps(event).encode('utf-8'),
                    callback=self._delivery_report
                )
                
                # Poll for delivery reports
                self.producer.poll(0)
                
                event_count += 1
                time.sleep(interval_sec)
                
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Flush and close producer"""
        print(f"\nFlushing remaining messages... (sent: {self.events_sent}, errors: {self.errors})")
        self.producer.flush(timeout=10)
        print("Producer shutdown complete")


def create_topic_if_not_exists(bootstrap_servers, topic_name):
    """Create Kafka topic if it doesn't exist"""
    admin_client = AdminClient({'bootstrap.servers': bootstrap_servers})
    
    # Check if topic exists
    metadata = admin_client.list_topics(timeout=10)
    if topic_name in metadata.topics:
        print(f"Topic '{topic_name}' already exists")
        return
    
    # Create topic
    new_topic = NewTopic(
        topic=topic_name,
        num_partitions=3,
        replication_factor=1,
        config={
            'cleanup.policy': 'delete',
            'retention.ms': '604800000',  # 7 days
            'segment.bytes': '1073741824',  # 1GB
        }
    )
    
    futures = admin_client.create_topics([new_topic])
    for topic, future in futures.items():
        try:
            future.result()
            print(f"Topic '{topic}' created successfully")
        except Exception as e:
            print(f"Failed to create topic '{topic}': {e}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Web Events Kafka Producer")
    parser.add_argument("--bootstrap-servers", default=KAFKA_BOOTSTRAP_SERVERS, help="Kafka bootstrap servers")
    parser.add_argument("--topic", default=TOPIC_NAME, help="Kafka topic name")
    parser.add_argument("--interval", type=int, default=PRODUCE_INTERVAL_MS, help="Interval between events in ms")
    parser.add_argument("--max-events", type=int, default=None, help="Maximum number of events to produce")
    parser.add_argument("--create-topic", action="store_true", help="Create topic before producing")
    
    args = parser.parse_args()
    
    if args.create_topic:
        create_topic_if_not_exists(args.bootstrap_servers, args.topic)
    
    producer = WebEventProducer(args.bootstrap_servers, args.topic)
    producer.produce_events(args.interval, args.max_events)