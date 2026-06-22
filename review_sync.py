#!/usr/bin/env python3
"""Sync Metacritic review scores from RAWG API into the local database."""

import json
import logging
import os
import re
import sys
import time
from difflib import SequenceMatcher
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from db import (
    get_db,
    get_games_needing_review_sync,
    init_db,
    update_game_review,
)

RAWG_API_URL = "https://api.rawg.io/api"
RAWG_API_KEY = os.environ.get("RAWG_API_KEY", "")
MATCH_THRESHOLD = 0.75  # minimum title similarity to accept a match

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)


def normalize_title(title):
    """Strip suffixes and special chars for fuzzy matching."""
    t = title.lower()
    for suffix in [
        "for nintendo switch", "nintendo switch edition",
        "switch edition", "™", "®", "©", ":", "-", "–", "—",
    ]:
        t = t.replace(suffix, " ")
    # collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t


def title_similarity(a, b):
    """Compare two titles after normalization."""
    na, nb = normalize_title(a), normalize_title(b)
    seq_score = SequenceMatcher(None, na, nb).ratio()
    # Also check word containment — the shorter title's words should mostly
    # appear in the longer title to avoid "Super Hoops 2" matching "Super Mario Bros. 2"
    words_a = set(na.split())
    words_b = set(nb.split())
    shorter, longer = (words_a, words_b) if len(words_a) <= len(words_b) else (words_b, words_a)
    if shorter:
        overlap = len(shorter & longer) / len(shorter)
    else:
        overlap = 0
    # Blend: require both sequence similarity and word overlap
    return seq_score * 0.5 + overlap * 0.5


def search_rawg(title, api_key):
    """Search RAWG for a game by title. Returns the top result or None."""
    params = urlencode({"search": title, "key": api_key, "page_size": 5, "search_exact": "false"})
    url = f"{RAWG_API_URL}/games?{params}"
    req = Request(url)
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except HTTPError as e:
        if e.code == 429:
            log.warning("Rate limited by RAWG, sleeping 60s")
            time.sleep(60)
            return None
        raise
    results = data.get("results", [])
    if not results:
        return None
    # Pick the best match, preferring results with a metacritic score
    best = None
    best_score = 0
    for r in results:
        score = title_similarity(title, r["name"])
        has_score = r.get("metacritic") is not None
        # Prefer a result with a metacritic score if similarity is close
        if score >= MATCH_THRESHOLD:
            if best is None or score > best_score + 0.05 or (score >= best_score - 0.05 and has_score and not (best.get("metacritic") is not None)):
                best_score = score
                best = r
    if best is None or best_score < MATCH_THRESHOLD:
        log.debug("No good match for %r (best: %r at %.2f)", title, best["name"] if best else None, best_score)
        return None
    return best


def sync_reviews(batch_size=200, dry_run=False, by_price=True):
    """Sync review scores for games that need it."""
    if not RAWG_API_KEY:
        log.error("RAWG_API_KEY environment variable not set")
        sys.exit(1)

    init_db()
    with get_db() as conn:
        games = get_games_needing_review_sync(conn, by_price=by_price)
        if not games:
            log.info("All games have up-to-date reviews")
            return

        log.info("Found %d games needing review sync", len(games))
        synced = 0
        matched = 0
        skipped = 0

        for game in games[:batch_size]:
            # Check for manual override first
            override = conn.execute(
                "SELECT rawg_id FROM review_overrides WHERE game_id = ?",
                (game["id"],)
            ).fetchone()

            if override:
                # Fetch the specific game by ID
                params = urlencode({"key": RAWG_API_KEY})
                url = f"{RAWG_API_URL}/games/{override['rawg_id']}?{params}"
                try:
                    with urlopen(url, timeout=15) as resp:
                        result = json.loads(resp.read())
                except HTTPError:
                    log.warning("Override RAWG ID %d not found for game %s",
                                override["rawg_id"], game["title"])
                    time.sleep(1)
                    continue
            else:
                result = search_rawg(game["title"], RAWG_API_KEY)
                if not result:
                    skipped += 1
                    # Still mark as synced so we don't retry every run
                    if not dry_run:
                        conn.execute(
                            "UPDATE games SET review_synced_at=datetime('now') WHERE id=?",
                            (game["id"],)
                        )
                    time.sleep(1)
                    continue

            rawg_id = result["id"]
            metacritic = result.get("metacritic")
            metacritic_url = result.get("metacritic_url", "")
            rawg_name = result.get("name", "")

            if not dry_run:
                update_game_review(conn, game["id"], rawg_id, metacritic, metacritic_url, rawg_name)
                conn.commit()

            matched += 1
            if metacritic:
                log.info("  %s -> %s (Metacritic: %d)", game["title"], rawg_name, metacritic)
            else:
                log.info("  %s -> %s (no Metacritic score)", game["title"], rawg_name)

            synced += 1
            time.sleep(1)  # rate limit

    log.info("Sync complete: %d matched, %d skipped (no match), %d total processed", matched, skipped, synced)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sync Metacritic review scores from RAWG API")
    parser.add_argument("--batch-size", type=int, default=200, help="Max games to process per run")
    parser.add_argument("--dry-run", action="store_true", help="Search but don't write to DB")
    parser.add_argument("--by-price", action=argparse.BooleanOptionalAction, default=True,
                        help="Prioritize expensive games first (more likely to have reviews)")
    args = parser.parse_args()

    sync_reviews(batch_size=args.batch_size, dry_run=args.dry_run, by_price=args.by_price)
