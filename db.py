"""SQLite database for eShop game and price tracking."""

import json
import os
import re
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get("ESHOP_DB_PATH", "eshop.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_key TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    developer TEXT DEFAULT '',
    publisher TEXT DEFAULT '',
    genres TEXT DEFAULT '[]',
    release_date TEXT DEFAULT '',
    description TEXT DEFAULT '',
    image_url TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS eshop_listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    nsuid TEXT UNIQUE,
    object_id TEXT UNIQUE,
    url TEXT DEFAULT '',
    platform TEXT DEFAULT '',
    content_rating TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS price_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER NOT NULL REFERENCES eshop_listings(id) ON DELETE CASCADE,
    reg_price REAL DEFAULT 0.0,
    sale_price REAL DEFAULT 0.0,
    discounted INTEGER DEFAULT 0,
    captured_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS external_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    site TEXT NOT NULL,
    url TEXT NOT NULL,
    UNIQUE(game_id, site)
);

CREATE INDEX IF NOT EXISTS idx_games_canonical_key ON games(canonical_key);
CREATE INDEX IF NOT EXISTS idx_games_title ON games(title);
CREATE INDEX IF NOT EXISTS idx_eshop_listings_game_id ON eshop_listings(game_id);
CREATE INDEX IF NOT EXISTS idx_eshop_listings_nsuid ON eshop_listings(nsuid);
CREATE INDEX IF NOT EXISTS idx_price_snapshots_listing_id ON price_snapshots(listing_id);
CREATE INDEX IF NOT EXISTS idx_price_snapshots_captured_at ON price_snapshots(captured_at);
"""


def make_canonical_key(title, developer="", publisher=""):
    """Create a platform-agnostic canonical key for a game."""
    def normalize(s):
        return re.sub(r'[^a-z0-9]', '', (s or "").lower())
    key = normalize(title)
    source = developer or publisher
    if source:
        key += ":" + normalize(source)
    return key


@contextmanager
def get_db(path=DB_PATH):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path=DB_PATH):
    with get_db(path) as conn:
        conn.executescript(SCHEMA_SQL)


def upsert_game(conn, game):
    key = make_canonical_key(game["title"], game["developer"], game["publisher"])
    row = conn.execute("SELECT id FROM games WHERE canonical_key = ?", (key,)).fetchone()
    if row:
        game_id = row["id"]
        conn.execute("""
            UPDATE games SET title=?, developer=?, publisher=?, genres=?,
                release_date=?, description=?, image_url=?, updated_at=datetime('now')
            WHERE id=?
        """, (game["title"], game["developer"], game["publisher"],
              json.dumps(game["genres"]), game["release_date"],
              game["description"], game["image_url"], game_id))
    else:
        cur = conn.execute("""
            INSERT INTO games (canonical_key, title, developer, publisher,
                genres, release_date, description, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (key, game["title"], game["developer"], game["publisher"],
              json.dumps(game["genres"]), game["release_date"],
              game["description"], game["image_url"]))
        game_id = cur.lastrowid
    return game_id


def upsert_listing(conn, game_id, game):
    row = conn.execute("SELECT id FROM eshop_listings WHERE nsuid = ?",
                       (game["nsuid"],)).fetchone()
    if row:
        listing_id = row["id"]
        conn.execute("""
            UPDATE eshop_listings SET url=?, platform=?, content_rating=?,
                object_id=?, updated_at=datetime('now')
            WHERE id=?
        """, (game["url"], game["platform"], game["content_rating"],
              game["object_id"], listing_id))
    else:
        cur = conn.execute("""
            INSERT INTO eshop_listings (game_id, nsuid, object_id, url, platform, content_rating)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (game_id, game["nsuid"], game["object_id"], game["url"],
              game["platform"], game["content_rating"]))
        listing_id = cur.lastrowid
    return listing_id


def maybe_insert_price(conn, listing_id, game):
    """Insert a price snapshot only if the price changed since the last snapshot."""
    last = conn.execute("""
        SELECT reg_price, sale_price, discounted FROM price_snapshots
        WHERE listing_id = ? ORDER BY captured_at DESC LIMIT 1
    """, (listing_id,)).fetchone()
    if last and (last["reg_price"] == game["reg_price"] and
                 last["sale_price"] == game["sale_price"] and
                 bool(last["discounted"]) == game["discounted"]):
        return False
    conn.execute("""
        INSERT INTO price_snapshots (listing_id, reg_price, sale_price, discounted)
        VALUES (?, ?, ?, ?)
    """, (listing_id, game["reg_price"], game["sale_price"], int(game["discounted"])))
    return True


def get_current_deals(conn, min_discount=0):
    return conn.execute("""
        SELECT g.id, g.title, g.developer, g.publisher, g.genres, g.image_url,
               el.url, el.nsuid,
               ps.reg_price, ps.sale_price,
               ROUND((ps.reg_price - ps.sale_price) / ps.reg_price * 100, 1) as discount_pct
        FROM games g
        JOIN eshop_listings el ON el.game_id = g.id
        JOIN price_snapshots ps ON ps.listing_id = el.id
        WHERE ps.discounted = 1
          AND ps.captured_at = (SELECT MAX(ps2.captured_at) FROM price_snapshots ps2
                                WHERE ps2.listing_id = el.id)
          AND ((ps.reg_price - ps.sale_price) / ps.reg_price * 100) >= ?
        ORDER BY discount_pct DESC
    """, (min_discount,)).fetchall()


def search_games(conn, query, page=1, per_page=24):
    offset = (page - 1) * per_page
    like = f"%{query}%"
    rows = conn.execute("""
        SELECT g.*,
               (SELECT 1 FROM price_snapshots ps
                JOIN eshop_listings el2 ON ps.listing_id = el2.id
                WHERE el2.game_id = g.id AND ps.discounted = 1
                  AND ps.captured_at = (SELECT MAX(captured_at) FROM price_snapshots ps3
                                        WHERE ps3.listing_id = el2.id)
                LIMIT 1) as is_deal
        FROM games g
        WHERE g.title LIKE ? OR g.developer LIKE ? OR g.publisher LIKE ?
        ORDER BY g.title
        LIMIT ? OFFSET ?
    """, (like, like, like, per_page, offset)).fetchall()
    total = conn.execute("""
        SELECT COUNT(*) FROM games
        WHERE title LIKE ? OR developer LIKE ? OR publisher LIKE ?
    """, (like, like, like)).fetchone()[0]
    return rows, total


def get_game_detail(conn, game_id):
    game = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    if not game:
        return None
    listings = conn.execute(
        "SELECT * FROM eshop_listings WHERE game_id = ?", (game_id,)
    ).fetchall()
    history = []
    for listing in listings:
        snapshots = conn.execute(
            "SELECT * FROM price_snapshots WHERE listing_id = ? ORDER BY captured_at",
            (listing["id"],)
        ).fetchall()
        history.extend(snapshots)
    external = conn.execute(
        "SELECT * FROM external_links WHERE game_id = ?", (game_id,)
    ).fetchall()
    return {"game": game, "listings": listings, "price_history": history, "external_links": external}
