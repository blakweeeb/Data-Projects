#!/usr/bin/env python3
"""
Integration test for Great Expectations checkpoints.
Tests verify configuration files exist and are valid.
"""
import pytest
import json
from pathlib import Path


def test_gx_config_exists():
    """Verify GX configuration directory exists."""
    gx_dir = Path("great_expectations")
    assert gx_dir.exists(), "Great Expectations directory should exist"
    assert (gx_dir / "great_expectations.yml").exists(), "GX config should exist"


def test_expectation_suites_exist():
    """Verify all expectation suite files exist and are valid JSON."""
    suite_dir = Path("great_expectations/expectation_suites")
    expected_suites = [
        "olist_customers.json",
        "olist_geolocation.json",
        "olist_orders.json",
        "olist_order_items.json",
        "olist_order_payments.json",
        "olist_order_reviews.json",
        "olist_products.json",
        "olist_sellers.json",
    ]
    
    for suite in expected_suites:
        path = suite_dir / suite
        assert path.exists(), f"Expectation suite {suite} should exist"
        
        # Validate JSON structure
        with open(path, "r") as f:
            data = json.load(f)
        assert "expectation_suite_name" in data
        assert "expectations" in data
        assert len(data["expectations"]) > 0


def test_checkpoints_exist():
    """Verify checkpoint configurations exist and are valid YAML."""
    cp_dir = Path("great_expectations/checkpoints")
    assert (cp_dir / "raw_checkpoint.yml").exists(), "raw_checkpoint should exist"
    assert (cp_dir / "curated_checkpoint.yml").exists(), "curated_checkpoint should exist"
    
    # Validate YAML structure
    import yaml
    for cp_file in ["raw_checkpoint.yml", "curated_checkpoint.yml"]:
        path = cp_dir / cp_file
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        assert data is not None
        assert "name" in data
        assert "action_list" in data


def test_expectation_suite_content():
    """Verify key expectations are present in suites."""
    suite_dir = Path("great_expectations/expectation_suites")
    
    # Check orders suite has key expectations
    with open(suite_dir / "olist_orders.json", "r") as f:
        orders_suite = json.load(f)
    exp_types = {e["expectation_type"] for e in orders_suite["expectations"]}
    assert "expect_column_values_to_be_in_set" in exp_types
    assert "expect_column_values_to_be_between" in exp_types
    assert "expect_column_values_to_be_unique" in exp_types
    
    # Check customers suite
    with open(suite_dir / "olist_customers.json", "r") as f:
        customers_suite = json.load(f)
    exp_types = {e["expectation_type"] for e in customers_suite["expectations"]}
    assert "expect_column_values_to_match_regex" in exp_types
    assert "expect_column_values_to_be_in_set" in exp_types


def test_datasources_config():
    """Verify datasources configuration exists."""
    gx_dir = Path("great_expectations")
    # Config file should exist
    assert (gx_dir / "great_expectations.yml").exists()


def test_data_docs_generated():
    """Verify Data Docs directory structure exists."""
    docs_dir = Path("great_expectations/uncommitted/data_docs/local_site")
    # May not exist until checkpoints run
    if docs_dir.exists():
        index = docs_dir / "index.html"
        assert index.exists(), "Data Docs index.html should exist"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])