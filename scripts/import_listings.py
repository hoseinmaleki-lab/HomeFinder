#!/usr/bin/env python3
"""Import permitted, verified listing records from a local CSV into the public dashboard.

This is not an MLS scraper. Do not publish private/off-market leads without permission.
"""
import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

FIELDS = ("address", "city", "price", "sqft", "beds", "baths", "url", "source", "status", "checked_at")

def load_csv(path):
    results = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                sqft = int(float(row.get("sqft") or 0))
                price = int(float(row.get("price") or 0)) or None
            except ValueError:
                continue
            if sqft <= 3000:
                continue
            url = (row.get("url") or "").strip()
            if urlparse(url).scheme != "https":
                continue
            item = {key: (row.get(key) or "").strip() for key in FIELDS}
            item["sqft"], item["price"] = sqft, price
            item["checked_at"] = item["checked_at"] or datetime.now(timezone.utc).date().isoformat()
            results.append(item)
    return list({(x["url"], x["address"].lower()): x for x in results}.values())

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path, help="Authorized public listings CSV")
    parser.add_argument("--output", type=Path, default=Path("docs/data/listings.json"))
    args = parser.parse_args()
    data = load_csv(args.csv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Imported {len(data)} listings to {args.output}")
