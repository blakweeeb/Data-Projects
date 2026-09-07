#!/usr/bin/env python3
"""Ingest Olist dataset from Kaggle → Parquet partitioned by date."""
import os
import sys
from pathlib import Path

import kagglehub
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from tqdm import tqdm


def load_config():
    with open("config/settings.yaml", "r") as f:
        return yaml.safe_load(f)


def ensure_dirs(config):
    Path(config["paths"]["landing"]).mkdir(parents=True, exist_ok=True)
    Path(config["paths"]["raw"]).mkdir(parents=True, exist_ok=True)
    Path(config["paths"]["catalog"]).mkdir(parents=True, exist_ok=True)


def download_olist():
    print("Downloading Olist dataset from Kaggle...")
    path = kagglehub.dataset_download("olistbr/brazilian-ecommerce")
    print(f"Downloaded to: {path}")
    return Path(path)


def convert_to_partitioned_parquet(csv_path, entity, config):
    raw_dir = Path(config["paths"]["raw"])
    catalog_dir = Path(config["paths"]["catalog"])
    print(f"Processing {entity}...")
    df = pd.read_csv(csv_path)
    partition_cols = []
    date_col = config["partitioning"]["date_columns"].get(entity)
    if date_col and date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df["year"] = df[date_col].dt.year
        df["month"] = df[date_col].dt.month
        partition_cols = ["year", "month"]
    entity_dir = raw_dir / entity
    entity_dir.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df)
    pq.write_to_dataset(table, root_path=str(entity_dir), partition_cols=partition_cols, compression="snappy")
    schema = pa.schema([(f.name, f.type) for f in table.schema])
    schema_path = catalog_dir / f"{entity}.json"
    with open(schema_path, "w") as f:
        import json
        schema_dict = {"fields": [{"name": field.name, "type": str(field.type), "nullable": field.nullable} for field in schema]}
        json.dump(schema_dict, f, indent=2)
    print(f"  -> Written to {entity_dir} (partitions: {partition_cols})")
    print(f"  -> Schema saved to {schema_path}")
    return len(df)


def main():
    config = load_config()
    ensure_dirs(config)
    download_path = download_olist()
    total_rows = 0
    for csv_file in tqdm(list(download_path.glob("*.csv")), desc="Converting tables"):
        entity = csv_file.stem.replace("olist_", "").replace("_dataset", "")
        if entity in config["olist_tables"]:
            rows = convert_to_partitioned_parquet(csv_file, entity, config)
            total_rows += rows
    print(f"\nIngestion complete. Total rows processed: {total_rows:,}")
    print(f"Raw data location: {config['paths']['raw']}")
    print(f"Schemas location: {config['paths']['catalog']}")


if __name__ == "__main__":
    main()