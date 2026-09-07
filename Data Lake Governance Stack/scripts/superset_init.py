#!/usr/bin/env python3
"""Initialize Superset with DuckDB connection and create base dashboard."""
import json
import sys
import time
from pathlib import Path

import requests
import yaml


def load_config():
    with open("config/settings.yaml", "r") as f:
        return yaml.safe_load(f)


class SupersetClient:
    def __init__(self, host, port, username, password):
        self.base_url = f"http://{host}:{port}/api/v1"
        self.session = requests.Session()
        self.token = None
        self._login(username, password)

    def _login(self, username, password):
        resp = self.session.post(f"{self.base_url}/security/login",
                                 json={"username": username, "password": password, "provider": "db", "refresh": True})
        resp.raise_for_status()
        self.token = resp.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        print("Logged in to Superset")

    def _get_csrf_token(self):
        resp = self.session.get(f"{self.base_url}/security/csrf_token/")
        resp.raise_for_status()
        return resp.json()["result"]

    def create_database(self, name, sqlalchemy_uri):
        csrf_token = self._get_csrf_token()
        headers = {"X-CSRFToken": csrf_token, "Referer": f"{self.base_url}/database/add/"}
        payload = {"database_name": name, "sqlalchemy_uri": sqlalchemy_uri,
                   "expose_in_sqllab": True, "allow_ctas": True, "allow_cvas": True, "allow_dml": True}
        resp = self.session.post(f"{self.base_url}/database/", json=payload, headers=headers)
        if resp.status_code == 409:
            resp = self.session.get(f"{self.base_url}/database/?q={{'filters':[{'col':'database_name','opr':'eq','value':{name}}]}}")
            databases = resp.json()["result"]
            if databases:
                return databases[0]["id"]
        resp.raise_for_status()
        db_id = resp.json()["id"]
        print(f"Created database '{name}' with ID: {db_id}")
        return db_id

    def get_datasets(self, database_id):
        resp = self.session.get(f"{self.base_url}/dataset/?q={{'filters':[{'col':'database','opr':'rel_o2m','value':{database_id}}]}}")
        resp.raise_for_status()
        return {ds["table_name"]: ds["id"] for ds in resp.json()["result"]}

    def create_dataset(self, database_id, table_name, schema="main"):
        csrf_token = self._get_csrf_token()
        headers = {"X-CSRFToken": csrf_token}
        payload = {"database": database_id, "table_name": table_name, "schema": schema, "owners": []}
        resp = self.session.post(f"{self.base_url}/dataset/", json=payload, headers=headers)
        if resp.status_code == 409:
            return self.get_datasets(database_id).get(table_name)
        resp.raise_for_status()
        return resp.json()["id"]

    def create_chart(self, dataset_id, chart_type, params, name):
        csrf_token = self._get_csrf_token()
        headers = {"X-CSRFToken": csrf_token}
        payload = {"datasource_id": dataset_id, "datasource_type": "table", "viz_type": chart_type,
                   "params": json.dumps(params), "slice_name": name, "owners": []}
        resp = self.session.post(f"{self.base_url}/chart/", json=payload, headers=headers)
        if resp.status_code == 409:
            print(f"Chart '{name}' already exists")
            return None
        resp.raise_for_status()
        chart_id = resp.json()["id"]
        print(f"Created chart '{name}' (ID: {chart_id})")
        return chart_id

    def create_dashboard(self, title, charts, position_json):
        csrf_token = self._get_csrf_token()
        headers = {"X-CSRFToken": csrf_token}
        payload = {"dashboard_title": title, "slug": title.lower().replace(" ", "-"),
                   "position_json": json.dumps(position_json), "css": "", "published": True, "owners": []}
        resp = self.session.post(f"{self.base_url}/dashboard/", json=payload, headers=headers)
        if resp.status_code == 409:
            print(f"Dashboard '{title}' already exists")
            return None
        resp.raise_for_status()
        dash_id = resp.json()["id"]
        print(f"Created dashboard '{title}' (ID: {dash_id})")
        for chart_id in charts:
            if chart_id:
                self.session.post(f"{self.base_url}/dashboard/{dash_id}/charts/",
                                  json={"chart_id": chart_id}, headers=headers)
        return dash_id


def wait_for_superset(host, port, max_wait=120):
    url = f"http://{host}:{port}/health"
    start = time.time()
    while time.time() - start < max_wait:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                print("Superset is ready!")
                return True
        except Exception:
            pass
        time.sleep(3)
    return False


def main():
    config = load_config()
    superset_cfg = config["superset"]
    print("Waiting for Superset to be ready...")
    if not wait_for_superset(superset_cfg["host"], superset_cfg["port"]):
        print("ERROR: Superset did not become ready in time")
        sys.exit(1)
    client = SupersetClient(superset_cfg["host"], superset_cfg["port"],
                            superset_cfg["username"], superset_cfg["password"])
    db_id = client.create_database(superset_cfg["database_name"], superset_cfg["sqlalchemy_uri"])
    tables = ["fact_orders", "fact_order_items", "dim_customers", "dim_sellers", "dim_products",
              "dim_geolocation", "dim_date"]
    print("\nCreating datasets...")
    dataset_ids = {}
    for table in tables:
        ds_id = client.create_dataset(db_id, table)
        if ds_id:
            dataset_ids[table] = ds_id
            print(f"  Dataset {table}: ID {ds_id}")
    print("\nCreating charts...")
    chart_ids = []
    if "fact_orders" in dataset_ids:
        chart_ids.append(client.create_chart(dataset_ids["fact_orders"], "line",
               {"x_axis": "order_purchase_timestamp", "metrics": ["SUM(total_payment_value)"],
                "time_grain_sqla": "P1D", "row_limit": 10000}, "GMV Diario"))
        chart_ids.append(client.create_chart(dataset_ids["fact_orders"], "line",
               {"x_axis": "order_purchase_timestamp", "metrics": ["COUNT(*)"],
                "time_grain_sqla": "P1D", "row_limit": 10000}, "Pedidos por Día"))
    if "dim_products" in dataset_ids and "fact_order_items" in dataset_ids:
        chart_ids.append(client.create_chart(dataset_ids["fact_order_items"], "table",
               {"columns": ["product_category_name_english", "SUM(price)"],
                "order_by_cols": [{"column": "SUM(price)", "ascending": False}], "row_limit": 10},
               "Top 10 Categorías por Revenue"))
    if "fact_orders" in dataset_ids:
        chart_ids.append(client.create_chart(dataset_ids["fact_orders"], "table",
               {"columns": ["order_status", "AVG(avg_review_score)", "COUNT(*)"], "row_limit": 20},
               "Review Score por Estado de Pedido"))
    position_json = {"ROOT_ID": {"type": "ROOT", "id": "ROOT_ID",
                    "children": [f"CHART-{c}" for c in chart_ids if c], "parents": []}}
    for i, cid in enumerate(filter(None, chart_ids)):
        position_json["ROOT_ID"]["children"] = [f"CHART-{c}" for c in chart_ids if c]
    client.create_dashboard("Olist E-commerce - Data Lake Governance",
            list(filter(None, chart_ids)),
            position_json)
    print("\nSuperset initialization complete!")
    print(f"Access at: http://{superset_cfg['host']}:{superset_cfg['port']}")


if __name__ == "__main__":
    main()