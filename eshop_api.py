"""Nintendo eShop Algolia API client."""

import hashlib
import json
import os
import random
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


def normalize_hit(hit):
    """Map a raw Algolia hit to a clean dict for storage."""
    price = hit.get("price", {})
    reg = price.get("regPrice", 0)
    sale = price.get("salePrice", 0)
    reg = float(reg) if reg else 0.0
    sale = float(sale) if sale else 0.0
    return {
        "title": hit.get("title", "Unknown"),
        "nsuid": hit.get("nsuid"),
        "object_id": hit.get("objectID"),
        "developer": hit.get("softwareDeveloper", ""),
        "publisher": hit.get("softwarePublisher", ""),
        "platform": hit.get("platform", ""),
        "genres": hit.get("gameGenreLabels", []),
        "release_date": hit.get("releaseDate", ""),
        "url": hit.get("url", ""),
        "image_url": hit.get("productImageSquare", ""),
        "description": hit.get("description", ""),
        "content_rating": hit.get("contentRatingCode", ""),
        "reg_price": reg,
        "sale_price": sale,
        "discounted": bool(price.get("discounted")),
    }


def fetch_all_games(hits_per_page=40, use_cache=False):
    """Fetch the eShop catalog (up to 1000 results), yielding individual hits."""
    for hits, page, total_pages in fetch_pages("", hits_per_page=hits_per_page, use_cache=use_cache):
        yield from hits
