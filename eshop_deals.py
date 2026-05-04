#!/usr/bin/env python3
"""Fetch Nintendo eShop deals via Algolia API and display discount info."""

import argparse
import csv
import sys

from eshop_api import fetch_pages

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
