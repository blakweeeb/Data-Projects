#!/usr/bin/env python
"""Genera un dataset de ventas sintetico con el mismo esquema del dataset publico
de Olist (Kaggle) para poder ejecutar el proyecto sin descargar datos con licencia.

Salida: data/raw/*.csv   (un archivo por tabla del OLTP de origen)

Si quieres usar el dataset real:
  1. Descarga los CSV de https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
  2. Dejalos en data/raw/ con estos nombres:
     customers.csv, geolocation.csv, order_items.csv, order_payments.csv,
     order_reviews.csv, orders.csv, products.csv, sellers.csv
  3. Ejecuta `make seed` (no hace falta volver a generar nada).
"""

from __future__ import annotations

import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

SEED = 42

CATEGORIES = [
    "beleza_saude", "informatica_acessorios", "automotivo", "cama_mesa_banho",
    "moveis_decoracao", "esporte_lazer", "perfumaria", "utilidades_domesticas",
    "telefonia", "relogios_presentes", "alimentos_bebidas", "bebes", "papelaria",
    "brinquedos", "ferramentas_jardim", "eletroportateis", "consoles_games",
    "instrumentos_musicais", "eletrodomesticos", "livros_interesse_geral",
    "cool_stuff", "malas_acessorios", "moveis_escritorio", "eletronicos", "pcs",
    "pet_shop", "fashion_calcados", "flores", "artigos_de_natal", "audio",
]

STATES = ["SP", "RJ", "MG", "RS", "PR", "SC", "BA", "DF", "GO", "PE", "CE", "PA", "ES"]
CITIES_BY_STATE = {
    "SP": ["sao paulo", "campinas", "santos", "sao jose do rio preto"],
    "RJ": ["rio de janeiro", "niteroi", "petropolis"],
    "MG": ["belo horizonte", "uberlandia", "juiz de fora"],
    "RS": ["porto alegre", "caxias do sul", "santa maria"],
    "PR": ["curitiba", "londrina", "maringa"],
    "SC": ["florianopolis", "joinville", "blumenau"],
    "BA": ["salvador", "feira de santana"],
    "DF": ["brasilia"],
    "GO": ["goiania", "anapolis"],
    "PE": ["recife", "caruaru"],
    "CE": ["fortaleza", "juazeiro do norte"],
    "PA": ["belem", "santarem"],
    "ES": ["vitoria", "vila velha"],
}

PAYMENT_TYPES = ["credit_card", "boleto", "voucher", "debit_card"]
ORDER_STATUS = (
    ["delivered"] * 90
    + ["shipped"] * 3
    + ["canceled"] * 2
    + ["unavailable"] * 1
    + ["invoiced"] * 1
    + ["processing"] * 1
    + ["created"] * 1
    + ["approved"] * 1
)


def _id(prefix: str, size: int, rng: random.Random) -> str:
    return prefix + "".join(rng.choice("0123456789abcdef") for _ in range(size))


def _zip(rng: random.Random) -> str:
    return f"{rng.randint(1000, 99999):05d}"


def _ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def write_csv(path: Path, header: List[str], rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  {path.name:<28} {len(rows):>8,} filas")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Genera datos de muestra tipo Olist")
    parser.add_argument("--out-dir", default="data/raw", help="Directorio de salida")
    parser.add_argument("--orders", type=int, default=18000, help="Numero de pedidos")
    parser.add_argument("--products", type=int, default=2000, help="Numero de productos")
    parser.add_argument("--customers", type=int, default=12000, help="Numero de clientes")
    parser.add_argument("--sellers", type=int, default=300, help="Numero de vendedores")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args(argv)

    rng = random.Random(args.seed)
    out = Path(args.out_dir)
    print(f"Generando dataset sintetico en {out.resolve()} ...")

    start = datetime(2016, 9, 1)
    end = datetime(2018, 8, 31)
    span_days = (end - start).days

    # ------------------------------------------------------------------ geolocation
    geo_rows = []
    for _ in range(3000):
        state = rng.choice(STATES)
        geo_rows.append({
            "geolocation_zip_code_prefix": _zip(rng),
            "geolocation_lat": round(rng.uniform(-33.0, 5.0), 6),
            "geolocation_lng": round(rng.uniform(-74.0, -35.0), 6),
            "geolocation_city": rng.choice(CITIES_BY_STATE[state]),
            "geolocation_state": state,
        })
    write_csv(out / "geolocation.csv",
              ["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng",
               "geolocation_city", "geolocation_state"], geo_rows)

    # ------------------------------------------------------------------- customers
    customers, customer_unique = [], []
    for i in range(args.customers):
        state = rng.choice(STATES)
        unique = _id("cu", 26, rng)
        customer_unique.append(unique)
        customers.append({
            "customer_id": _id("cid", 26, rng),
            "customer_unique_id": unique,
            "customer_zip_code_prefix": _zip(rng),
            "customer_city": rng.choice(CITIES_BY_STATE[state]),
            "customer_state": state,
        })
    write_csv(out / "customers.csv",
              ["customer_id", "customer_unique_id", "customer_zip_code_prefix",
               "customer_city", "customer_state"], customers)

    # -------------------------------------------------------------------- sellers
    sellers = []
    for _ in range(args.sellers):
        state = rng.choice(STATES)
        sellers.append({
            "seller_id": _id("sel", 26, rng),
            "seller_zip_code_prefix": _zip(rng),
            "seller_city": rng.choice(CITIES_BY_STATE[state]),
            "seller_state": state,
        })
    write_csv(out / "sellers.csv",
              ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"], sellers)

    # ------------------------------------------------------------------- products
    products = []
    for _ in range(args.products):
        products.append({
            "product_id": _id("prd", 26, rng),
            "product_category_name": rng.choice(CATEGORIES),
            "product_name_lenght": rng.randint(20, 70),
            "product_description_lenght": rng.randint(50, 3000),
            "product_photos_qty": rng.randint(1, 8),
            "product_weight_g": rng.randint(50, 20000),
            "product_length_cm": rng.randint(10, 100),
            "product_height_cm": rng.randint(2, 60),
            "product_width_cm": rng.randint(5, 80),
        })
    write_csv(out / "products.csv",
              ["product_id", "product_category_name", "product_name_lenght",
               "product_description_lenght", "product_photos_qty", "product_weight_g",
               "product_length_cm", "product_height_cm", "product_width_cm"], products)

    # --------------------------------------------------------------------- orders
    orders, order_items, payments, reviews = [], [], [], []
    for _ in range(args.orders):
        order_id = _id("ord", 26, rng)
        customer = customers[rng.randrange(len(customers))]
        status = rng.choice(ORDER_STATUS)
        purchase = start + timedelta(
            days=rng.randint(0, span_days),
            hours=rng.randint(0, 23),
            minutes=rng.randint(0, 59),
        )
        approved = purchase + timedelta(hours=rng.randint(1, 48))
        carrier = approved + timedelta(days=rng.randint(1, 4))
        delivered = carrier + timedelta(days=rng.randint(2, 25))
        estimated = purchase + timedelta(days=rng.randint(7, 40))

        if status == "delivered":
            pass
        elif status in ("canceled", "unavailable", "created", "processing", "approved"):
            carrier, delivered = "", ""
            if status in ("created", "processing", "approved"):
                estimated = purchase + timedelta(days=rng.randint(7, 40))
        else:  # shipped / invoiced
            delivered = ""

        orders.append({
            "order_id": order_id,
            "customer_id": customer["customer_id"],
            "order_status": status,
            "order_purchase_timestamp": _ts(purchase),
            "order_approved_at": _ts(approved),
            "order_delivered_carrier_date": _ts(carrier) if carrier else "",
            "order_delivered_customer_date": _ts(delivered) if delivered else "",
            "order_estimated_delivery_date": _ts(estimated),
        })

        # lineas de pedido
        total = 0.0
        for item_seq in range(1, rng.randint(1, 4) + 1):
            product = products[rng.randrange(len(products))]
            seller = sellers[rng.randrange(len(sellers))]
            price = round(rng.uniform(9.9, 890.0), 2)
            freight = round(rng.uniform(5.0, 60.0), 2)
            total += price + freight
            order_items.append({
                "order_id": order_id,
                "order_item_id": item_seq,
                "product_id": product["product_id"],
                "seller_id": seller["seller_id"],
                "shipping_limit_date": _ts(purchase + timedelta(days=rng.randint(3, 15))),
                "price": price,
                "freight_value": freight,
            })

        # pagos (1 o 2 metodos). Las partes SIEMPRE suman el total del pedido
        # (como en el Olist real): la ultima cuota es el resto exacto.
        total = round(total, 2)
        if rng.choice([1, 1, 1, 2]) == 1:
            splits = [total]
        else:
            first = round(total * rng.uniform(0.2, 0.8), 2)
            splits = [first, round(total - first, 2)]
        for seq, value in enumerate(splits, start=1):
            payments.append({
                "order_id": order_id,
                "payment_sequential": seq,
                "payment_type": rng.choice(PAYMENT_TYPES),
                "payment_installments": rng.randint(1, 12),
                "payment_value": value,
            })

        # reseñas (solo algunos pedidos entregados)
        if status == "delivered" and rng.random() < 0.65:
            score = rng.choices([1, 2, 3, 4, 5], weights=[12, 8, 14, 25, 41])[0]
            reviews.append({
                "review_id": _id("rev", 26, rng),
                "order_id": order_id,
                "review_score": score,
                "review_comment_title": rng.choice(["", "excelente", "regular", "muy bueno"]),
                "review_comment_message": rng.choice(
                    ["", "Llego antes de lo previsto", "Producto acorde a la descripcion",
                     "La caja venia golpeada", "Recomendado"]
                ),
                "review_creation_date": _ts(delivered + timedelta(days=rng.randint(0, 6))),
                "review_answer_timestamp": _ts(delivered + timedelta(days=rng.randint(1, 10))),
            })

    write_csv(out / "orders.csv",
              ["order_id", "customer_id", "order_status", "order_purchase_timestamp",
               "order_approved_at", "order_delivered_carrier_date",
               "order_delivered_customer_date", "order_estimated_delivery_date"], orders)
    write_csv(out / "order_items.csv",
              ["order_id", "order_item_id", "product_id", "seller_id",
               "shipping_limit_date", "price", "freight_value"], order_items)
    write_csv(out / "order_payments.csv",
              ["order_id", "payment_sequential", "payment_type", "payment_installments",
               "payment_value"], payments)
    write_csv(out / "order_reviews.csv",
              ["review_id", "order_id", "review_score", "review_comment_title",
               "review_comment_message", "review_creation_date",
               "review_answer_timestamp"], reviews)

    print("\nDataset listo. Siguiente paso:  make seed   (carga los CSV en PostgreSQL)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
