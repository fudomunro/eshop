#!/usr/bin/env python3
"""Fetch Nintendo eShop deals via Algolia API and display discount info."""

import argparse
import csv
import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

API_URL = "https://u3b6gr4ua3-dsn.algolia.net/1/indexes/store_game_en_ca_price_asc/query"
HEADERS = {
    "x-algolia-api-key": "a29c6927638bfd8cee23993e51e721c9",
    "x-algolia-application-id": "U3B6GR4UA3",
    "content-type": "application/x-www-form-urlencoded",
    "Origin": "https://www.nintendo.com",
    "Referer": "https://www.nintendo.com/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
}

PRICE_RANGES = [
    "Free",
    "$0.01 - $4.99",
    "$5 - $9.99",
    "$10 - $19.99",
    "$20 - $29.99",
    "$30 - $39.99",
    "$40 - $49.99",
    "$50 - $59.99",
    "$60 - $69.99",
    "$70 - $79.99",
    "$80 - $89.99",
    "$90 - $99.99",
    "$100+",
]

CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "eshop_deals"
CACHE_MAX_AGE = 3600  # 1 hour in seconds


def _cache_path(key):
    return CACHE_DIR / f"{key}.json"


def _cache_get(key):
    path = _cache_path(key)
    if not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if age > CACHE_MAX_AGE:
        return None
    return json.loads(path.read_text())


def _cache_set(key, data):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(key).write_text(json.dumps(data))


def fetch_pages(filters, hits_per_page=40, use_cache=True):
    """Yield batches of hits from the API, fetching more pages on demand.

    Yields (hits, page_num, total_pages) tuples so callers can track progress.
    """
    page = 0
    while True:
        payload = {
            "filters": filters,
            "hitsPerPage": hits_per_page,
            "page": page,
            "analytics": True,
            "facetingAfterDistinct": True,
        }
        cache_key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]

        data = None
        if use_cache:
            data = _cache_get(cache_key)

        if data is None:
            if page > 0:
                time.sleep(random.uniform(0.2, 0.6))
            req = Request(API_URL, json.dumps(payload).encode(), headers=HEADERS, method="POST")
            with urlopen(req) as resp:
                data = json.loads(resp.read())
            if use_cache:
                _cache_set(cache_key, data)

        hits = data.get("hits", [])
        total_pages = data.get("nbPages", 0)
        if not hits:
            return
        yield hits, page, total_pages

        page += 1
        if page >= total_pages:
            return


def extract_discounts(hits):
    """Extract discount info from each hit."""
    results = []
    for hit in hits:
        price = hit.get("price", {})
        if not price.get("discounted"):
            continue
        msrp = float(price.get("regPrice", 0))
        sale = float(price.get("salePrice", 0))
        if msrp <= 0:
            continue
        discount_pct = ((msrp - sale) / msrp) * 100
        results.append({
            "title": hit.get("title", "Unknown"),
            "publisher": hit.get("softwarePublisher", ""),
            "msrp": f"${msrp:.2f}",
            "sale_price": f"${sale:.2f}",
            "discount_pct": round(discount_pct, 1),
        })
    results.sort(key=lambda x: x["discount_pct"], reverse=True)
    return results


def print_table(results):
    """Print a formatted table to stdout."""
    if not results:
        print("No deals found.")
        return

    headers = ["Title", "Publisher", "MSRP", "Sale", "Discount"]
    rows = [[r["title"], r["publisher"], r["msrp"], r["sale_price"], f"{r['discount_pct']}%"] for r in results]

    col_widths = [max(len(h), max(len(row[i]) for row in rows)) for i, h in enumerate(headers)]
    fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)

    print(fmt.format(*headers))
    print(fmt.format(*["-" * w for w in col_widths]))
    for row in rows:
        print(fmt.format(*row))


def write_csv(results, path):
    """Write results to a CSV file."""
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "publisher", "msrp", "sale_price", "discount_pct"])
        writer.writeheader()
        writer.writerows(results)
    print(f"Saved {len(results)} deals to {path}")


def main():
    parser = argparse.ArgumentParser(description="Fetch Nintendo eShop deals and filter by discount percentage.")
    parser.add_argument("--min-discount", "-d", type=float, default=0, help="Minimum discount percentage to show (default: 0)")
    parser.add_argument("--price-range", "-p", choices=PRICE_RANGES, default=None, help="Filter by price range")
    parser.add_argument("--csv", "-o", type=str, default=None, help="Save results to a CSV file")
    parser.add_argument("--limit", "-n", type=int, default=40, help="Max number of results to show (default: 40)")
    parser.add_argument("--no-cache", action="store_true", help="Skip the local cache and fetch fresh data")
    args = parser.parse_args()

    filters = 'topLevelFilters:"Deals"'
    if args.price_range:
        filters += f' AND (priceRange:"{args.price_range}")'

    try:
        results = []
        for hits, page, total_pages in fetch_pages(filters, use_cache=not args.no_cache):
            results.extend(extract_discounts(hits))
            results = [r for r in results if r["discount_pct"] >= args.min_discount]
            sys.stderr.write(f"\rFetching page {page + 1}/{total_pages}...")
            sys.stderr.flush()
            if len(results) >= args.limit:
                break
        sys.stderr.write("\r" + " " * 40 + "\r")
        sys.stderr.flush()
        results = results[:args.limit]
    except Exception as e:
        print(f"Error fetching deals: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(results)} deals with >= {args.min_discount}% discount\n")
    print_table(results)

    if args.csv:
        write_csv(results, args.csv)


if __name__ == "__main__":
    main()
