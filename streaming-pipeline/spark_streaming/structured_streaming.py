#!/usr/bin/env python3
"""
Spark Structured Streaming Job for Web Events Processing
Reads from Kafka topic 'web-events', applies sliding window aggregations,
and writes results to MinIO (Parquet) and PostgreSQL
"""

import os
import signal
import sys
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    from_json, to_json, col, window, count, countDistinct,
    sum as spark_sum, avg, min as spark_min, max as spark_max,
    current_timestamp, expr, from_unixtime, unix_timestamp,
    date_format, year, month, dayofmonth, hour, minute, when
)
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType, DoubleType,
    TimestampType, IntegerType, BooleanType
)
import psycopg2
from psycopg2.extras import execute_values


# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "web-events")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "metrics")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "streaming_metrics")
POSTGRES_USER = os.getenv("POSTGRES_USER", "streaming_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "streaming_pass")
CHECKPOINT_DIR = os.getenv("CHECKPOINT_DIR", "s3a://metrics/checkpoints")
WINDOW_DURATION = "1 minute"
SLIDE_DURATION = "30 seconds"
WATERMARK_DELAY = "2 minutes"


# Event schema
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


def create_spark_session():
    """Create and configure Spark session with all necessary dependencies"""
    spark = SparkSession.builder \
        .appName("WebEventsStreaming") \
        .config("spark.sql.streaming.checkpointLocation", CHECKPOINT_DIR) \
        .config("spark.sql.shuffle.partitions", "4") \
        .config("spark.default.parallelism", "4") \
        .config("spark.streaming.stopGracefullyOnShutdown", "true") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT) \
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY) \
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY) \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
        .config("spark.jars.packages", 
                "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,"
                "org.apache.hadoop:hadoop-aws:3.3.4,"
                "com.amazonaws:aws-java-sdk-bundle:1.12.262,"
                "org.postgresql:postgresql:42.7.3") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    return spark


def read_kafka_stream(spark):
    """Read streaming data from Kafka"""
    return spark \
        .readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("subscribe", KAFKA_TOPIC) \
        .option("startingOffsets", "latest") \
        .option("failOnDataLoss", "false") \
        .load()


def parse_events(kafka_df):
    """Parse JSON events from Kafka"""
    # Extract value and parse JSON
    parsed = kafka_df.select(
        from_json(col("value").cast("string"), EVENT_SCHEMA).alias("data"),
        col("timestamp").alias("kafka_timestamp"),
        col("partition"),
        col("offset")
    ).select("data.*", "kafka_timestamp", "partition", "offset")
    
    # Convert timestamp string to timestamp type
    parsed = parsed.withColumn(
        "event_timestamp",
        from_unixtime(unix_timestamp(col("timestamp"), "yyyy-MM-dd'T'HH:mm:ss'Z'")).cast(TimestampType())
    )
    
    return parsed


def apply_watermark_and_window(events_df):
    """Apply watermark and sliding window aggregation"""
    # Apply watermark for late event handling
    watermarked = events_df \
        .withWatermark("event_timestamp", WATERMARK_DELAY)
    
    # Sliding window aggregation by page and event_type
    windowed = watermarked \
        .groupBy(
            window(col("event_timestamp"), WINDOW_DURATION, SLIDE_DURATION),
            col("page"),
            col("event_type")
        ) \
        .agg(
            count("*").alias("event_count"),
            countDistinct("user_id").alias("unique_users"),
            countDistinct("session_id").alias("unique_sessions"),
            spark_sum(when(col("event_type") == "purchase", col("total_amount")).otherwise(0)).alias("revenue"),
            count(when(col("event_type") == "purchase", True)).alias("purchase_count"),
            count(when(col("event_type") == "add_to_cart", True)).alias("add_to_cart_count"),
            count(when(col("event_type") == "error", True)).alias("error_count")
        ) \
        .select(
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
    
    return windowed


def write_to_minio(batch_df, batch_id):
    """Write batch to MinIO as Parquet partitioned by minute"""
    if batch_df.isEmpty():
        return
    
    try:
        # Add partition columns
        batch_with_partitions = batch_df \
            .withColumn("year", year(col("window_start"))) \
            .withColumn("month", month(col("window_start"))) \
            .withColumn("day", dayofmonth(col("window_start"))) \
            .withColumn("hour", hour(col("window_start"))) \
            .withColumn("minute", minute(col("window_start")))
        
        # Write to MinIO
        batch_with_partitions.write \
            .mode("append") \
            .partitionBy("year", "month", "day", "hour", "minute") \
            .parquet(f"s3a://{MINIO_BUCKET}/web-events-metrics/")
        
        print(f"Batch {batch_id}: Written {batch_df.count()} records to MinIO")
    except Exception as e:
        print(f"Error writing to MinIO: {e}")
        raise


def write_to_postgres(batch_df, batch_id):
    """Write batch to PostgreSQL using foreachBatch"""
    if batch_df.isEmpty():
        return
    
    try:
        # Collect data to driver (for small batches)
        rows = batch_df.collect()
        if not rows:
            return
        
        # Prepare data for bulk insert
        data = [
            (
                row.window_start,
                row.window_end,
                row.page,
                row.event_type,
                row.event_count,
                row.unique_users,
                row.unique_sessions,
                float(row.revenue) if row.revenue else 0.0,
                row.purchase_count,
                row.add_to_cart_count,
                row.error_count,
                row.processed_at
            )
            for row in rows
        ]
        
        # Bulk insert to PostgreSQL
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            database=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD
        )
        cursor = conn.cursor()
        
        insert_query = """
            INSERT INTO realtime_metrics 
            (window_start, window_end, page, event_type, event_count, unique_users, 
             unique_sessions, revenue, purchase_count, add_to_cart_count, error_count, processed_at)
            VALUES %s
            ON CONFLICT DO NOTHING
        """
        
        execute_values(cursor, insert_query, data)
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"Batch {batch_id}: Written {len(data)} records to PostgreSQL")
    except Exception as e:
        print(f"Error writing to PostgreSQL: {e}")
        # Don't raise - let streaming continue


def write_to_console(batch_df, batch_id):
    """Write batch to console for debugging"""
    if batch_df.isEmpty():
        return
    
    print(f"\n=== Batch {batch_id} ===")
    batch_df.show(truncate=False)
    print(f"Count: {batch_df.count()}")


def main():
    print("Starting Spark Structured Streaming Job...")
    print(f"Kafka: {KAFKA_BOOTSTRAP_SERVERS}")
    print(f"Topic: {KAFKA_TOPIC}")
    print(f"MinIO: {MINIO_ENDPOINT}")
    print(f"PostgreSQL: {POSTGRES_HOST}:{POSTGRES_PORT}")
    print(f"Window: {WINDOW_DURATION}, Slide: {SLIDE_DURATION}")
    print(f"Watermark: {WATERMARK_DELAY}")
    
    # Create Spark session
    spark = create_spark_session()
    
    # Read from Kafka
    kafka_df = read_kafka_stream(spark)
    
    # Parse events
    events_df = parse_events(kafka_df)
    
    # Apply window aggregation
    windowed_df = apply_watermark_and_window(events_df)
    
    # Write to multiple sinks using foreachBatch
    query = windowed_df \
        .writeStream \
        .foreachBatch(lambda batch_df, batch_id: (
            write_to_minio(batch_df, batch_id),
            write_to_postgres(batch_df, batch_id),
            write_to_console(batch_df, batch_id)
        )) \
        .option("checkpointLocation", CHECKPOINT_DIR) \
        .trigger(processingTime="30 seconds") \
        .start()
    
    print("Streaming query started. Waiting for termination...")
    
    # Handle graceful shutdown
    def signal_handler(signum, frame):
        print("\nShutting down...")
        query.stop()
        spark.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Wait for termination
    query.awaitTermination()


if __name__ == "__main__":
    main()