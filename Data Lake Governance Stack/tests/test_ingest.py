#!/usr/bin/env python3
"""
Tests for ingestion script.
"""
import pytest
from pathlib import Path
import pyarrow.parquet as pq
import json


@pytest.fixture
def config():
    import yaml
    with open("config/settings.yaml", "r") as f:
        return yaml.safe_load(f)


@pytest.fixture
def raw_dir(config):
    return Path(config["paths"]["raw"])


@pytest.fixture
def catalog_dir(config):
    return Path(config["paths"]["catalog"])


def test_raw_directory_exists(raw_dir):
    assert raw_dir.exists(), "Raw directory should exist after ingestion"


def test_all_entities_present(raw_dir, config):
    for entity in config["olist_tables"]:
        entity_dir = raw_dir / entity
        assert entity_dir.exists(), f"Entity directory {entity} should exist"


def test_partitioned_structure(raw_dir, config):
    for entity in config["olist_tables"]:
        entity_dir = raw_dir / entity
        if not entity_dir.exists():
            continue

        date_col = config["partitioning"]["date_columns"].get(entity)
        if date_col:
            # Should have year/month partitions
            year_dirs = list(entity_dir.glob("year=*"))
            assert len(year_dirs) > 0, f"{entity} should have year partitions"
            
            for year_dir in year_dirs:
                month_dirs = list(year_dir.glob("month=*"))
                assert len(month_dirs) > 0, f"{entity}/{year_dir.name} should have month partitions"
                
                for month_dir in month_dirs:
                    parquet_files = list(month_dir.glob("*.parquet"))
                    assert len(parquet_files) > 0, f"{entity}/{year_dir.name}/{month_dir.name} should have parquet files"
        else:
            # Non-partitioned entity
            parquet_files = list(entity_dir.glob("*.parquet"))
            assert len(parquet_files) > 0, f"{entity} should have parquet files"


def test_schema_files_exist(catalog_dir, config):
    for entity in config["olist_tables"]:
        schema_path = catalog_dir / f"{entity}.json"
        assert schema_path.exists(), f"Schema for {entity} should exist"
        
        with open(schema_path, "r") as f:
            schema = json.load(f)
        assert "fields" in schema, "Schema should have fields"
        assert len(schema["fields"]) > 0, "Schema should have at least one field"


def test_parquet_readable(raw_dir, config):
    for entity in config["olist_tables"]:
        entity_dir = raw_dir / entity
        if not entity_dir.exists():
            continue
            
        parquet_files = list(entity_dir.rglob("*.parquet"))
        assert len(parquet_files) > 0, f"{entity} should have parquet files"
        
        for pf in parquet_files[:1]:  # Test first file only
            table = pq.read_table(pf)
            assert table.num_rows > 0, f"{entity} parquet should have rows"
            assert table.num_columns > 0, f"{entity} parquet should have columns"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])