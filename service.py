#!/usr/bin/env python3
"""Background service that periodically collects eShop price data."""

import logging
import time

from eshop_api import fetch_all_games, normalize_hit
from db import get_db, init_db, upsert_game, upsert_listing, maybe_insert_price, make_canonical_key

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)


def collect_prices():
    """Fetch full catalog and record any price changes."""
    with get_db() as conn:
        count = 0
        new_games = 0
        price_changes = 0
        for hit in fetch_all_games(hits_per_page=40, use_cache=False):
            game = normalize_hit(hit)
            key = make_canonical_key(game["title"], game["developer"], game["publisher"])
            existing = conn.execute(
                "SELECT id FROM games WHERE canonical_key = ?", (key,)
            ).fetchone()
            game_id = upsert_game(conn, game)
            if not existing:
                new_games += 1
            listing_id = upsert_listing(conn, game_id, game)
            if maybe_insert_price(conn, listing_id, game):
                price_changes += 1
            count += 1
        conn.commit()
    log.info("Processed %d games, %d new, %d price changes",
             count, new_games, price_changes)


def main():
    init_db()
    interval = 6 * 3600  # every 6 hours
    log.info("Starting eShop price collector (interval=%ds)", interval)
    while True:
        try:
            collect_prices()
        except Exception:
            log.exception("Error during collection")
        time.sleep(interval)


if __name__ == "__main__":
    main()
