#!/usr/bin/env python3
"""Validate Great Expectations expectation suites and checkpoints (file-based)."""
import sys
import json
from pathlib import Path


def validate_expectation_suites():
    suite_dir = Path("great_expectations/expectation_suites")
    expected_suites = ["olist_customers.json", "olist_geolocation.json", "olist_orders.json",
                       "olist_order_items.json", "olist_order_payments.json", "olist_order_reviews.json",
                       "olist_products.json", "olist_sellers.json"]
    all_valid = True
    for suite_name in expected_suites:
        path = suite_dir / suite_name
        if not path.exists():
            print(f"MISSING: {suite_name}")
            all_valid = False
            continue
        try:
            with open(path, "r") as f:
                data = json.load(f)
            assert "expectation_suite_name" in data and "expectations" in data and len(data["expectations"]) > 0
            print(f"VALID: {suite_name} ({len(data['expectations'])} expectations)")
        except Exception as e:
            print(f"INVALID: {suite_name} - {e}")
            all_valid = False
    return all_valid


def validate_checkpoints():
    cp_dir = Path("great_expectations/checkpoints")
    for cp_name in ["raw_checkpoint.yml", "curated_checkpoint.yml"]:
        path = cp_dir / cp_name
        if not path.exists():
            print(f"MISSING CHECKPOINT: {cp_name}")
            all_valid = False
            continue
        try:
            import yaml
            with open(path, "r") as f:
                data = yaml.safe_load(f)
            assert data is not None and "name" in data and "action_list" in data
            print(f"VALID CHECKPOINT: {cp_name}")
        except Exception as e:
            print(f"INVALID CHECKPOINT: {cp_name} - {e}")
            all_valid = False
    return all_valid


def main():
    print("=" * 60)
    print("Great Expectations Validation (File-based)")
    print("=" * 60)
    print("\n[1/3] Validating expectation suites...")
    suites_ok = validate_expectation_suites()
    print("\n[2/3] Validating checkpoints...")
    checkpoints_ok = validate_checkpoints()
    print("\n[3/3] All checks complete.")
    if suites_ok and checkpoints_ok:
        print("SUCCESS: All expectation suites and checkpoints are valid!")
    else:
        print("FAILURE: Some validation checks failed!")
    return 0 if suites_ok and checkpoints_ok else 1


if __name__ == "__main__":
    sys.exit(main())