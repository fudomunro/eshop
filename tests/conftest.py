import socket
import threading
import time

import pytest

import db
from db import init_db, upsert_game, upsert_listing, maybe_insert_price


def _wait_for_port(host, port, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"Server did not start on {host}:{port}")


def seed_db(path):
    init_db(path)
    games = [
        {
            "title": "The Legend of Zelda: Tears of the Kingdom",
            "developer": "Nintendo",
            "publisher": "Nintendo",
            "genres": ["Action", "Adventure"],
            "release_date": "2023-05-12",
            "description": "Explore the vast lands of Hyrule.",
            "image_url": "https://placehold.co/400x400/2d5a27/fff?text=Zelda",
            "nsuid": "70010000012345",
            "object_id": "zelda-totk",
            "url": "https://www.nintendo.com/us/store/products/zelda-totk",
            "platform": "Nintendo Switch",
            "content_rating": "Everyone 10+",
            "reg_price": 59.99,
            "sale_price": 41.99,
            "discounted": True,
        },
        {
            "title": "Super Mario Odyssey",
            "developer": "Nintendo",
            "publisher": "Nintendo",
            "genres": ["Platformer", "Adventure"],
            "release_date": "2017-10-27",
            "description": "Join Mario on a massive, globe-trotting 3D adventure.",
            "image_url": "https://placehold.co/400x400/cc0000/fff?text=Mario",
            "nsuid": "70010000012346",
            "object_id": "mario-odyssey",
            "url": "https://www.nintendo.com/us/store/products/mario-odyssey",
            "platform": "Nintendo Switch",
            "content_rating": "Everyone",
            "reg_price": 59.99,
            "sale_price": 47.99,
            "discounted": True,
        },
        {
            "title": "Pikmin 4",
            "developer": "Nintendo",
            "publisher": "Nintendo",
            "genres": ["Strategy", "Adventure"],
            "release_date": "2023-07-21",
            "description": "Lead a team of tiny creatures to solve puzzles.",
            "image_url": "https://placehold.co/400x400/ff6600/fff?text=Pikmin",
            "nsuid": "70010000012347",
            "object_id": "pikmin-4",
            "url": "https://www.nintendo.com/us/store/products/pikmin-4",
            "platform": "Nintendo Switch",
            "content_rating": "Everyone",
            "reg_price": 59.99,
            "sale_price": 59.99,
            "discounted": False,
        },
        {
            "title": "Kirby's Return to Dream Land Deluxe",
            "developer": "HAL Laboratory",
            "publisher": "Nintendo",
            "genres": ["Platformer", "Action"],
            "release_date": "2023-02-24",
            "description": "Join Kirby and friends for a multiplayer adventure.",
            "image_url": "https://placehold.co/400x400/ff69b4/fff?text=Kirby",
            "nsuid": "70010000012348",
            "object_id": "kirby-rtdd",
            "url": "https://www.nintendo.com/us/store/products/kirby-rtdd",
            "platform": "Nintendo Switch",
            "content_rating": "Everyone",
            "reg_price": 59.99,
            "sale_price": 59.99,
            "discounted": False,
        },
        {
            "title": "Metroid Dread",
            "developer": "MercurySteam",
            "publisher": "Nintendo",
            "genres": ["Action", "Adventure"],
            "release_date": "2021-10-08",
            "description": "Samus returns in a tense side-scrolling adventure.",
            "image_url": "https://placehold.co/400x400/333399/fff?text=Metroid",
            "nsuid": "70010000012349",
            "object_id": "metroid-dread",
            "url": "https://www.nintendo.com/us/store/products/metroid-dread",
            "platform": "Nintendo Switch",
            "content_rating": "Everyone 10+",
            "reg_price": 59.99,
            "sale_price": 29.99,
            "discounted": True,
        },
    ]

    with db.get_db(path) as conn:
        for game_data in games:
            game_id = upsert_game(conn, game_data)
            listing_id = upsert_listing(conn, game_id, game_data)
            maybe_insert_price(conn, listing_id, game_data)

        # Add Metacritic scores for test games
        conn.execute(
            "UPDATE games SET metacritic_score=96, metacritic_url='https://www.metacritic.com/game/switch/the-legend-of-zelda-tears-of-the-kingdom' WHERE canonical_key LIKE ?",
            ("%zeldatearsofthekingdom%",)
        )
        conn.execute(
            "UPDATE games SET metacritic_score=97, metacritic_url='https://www.metacritic.com/game/switch/super-mario-odyssey' WHERE canonical_key LIKE ?",
            ("%supermarioodyssey%",)
        )
        conn.execute(
            "UPDATE games SET metacritic_score=85, metacritic_url='https://www.metacritic.com/game/switch/metroid-dread' WHERE canonical_key LIKE ?",
            ("%metroiddread%",)
        )

        # Add price history snapshots for dealt games
        history = [
            ("zelda-totk", [
                (59.99, 59.99, 0, "2024-01-01 00:00:00"),
                (59.99, 49.99, 1, "2024-06-01 00:00:00"),
                (59.99, 41.99, 1, "2024-12-01 00:00:00"),
            ]),
            ("mario-odyssey", [
                (59.99, 59.99, 0, "2024-01-01 00:00:00"),
                (59.99, 47.99, 1, "2024-09-01 00:00:00"),
            ]),
            ("metroid-dread", [
                (59.99, 39.99, 1, "2024-03-01 00:00:00"),
                (59.99, 29.99, 1, "2024-11-01 00:00:00"),
            ]),
        ]
        for object_id, snapshots in history:
            listing = conn.execute(
                "SELECT id FROM eshop_listings WHERE object_id = ?", (object_id,)
            ).fetchone()
            for reg, sale, disc, ts in snapshots:
                conn.execute(
                    "INSERT INTO price_snapshots (listing_id, reg_price, sale_price, discounted, captured_at) VALUES (?, ?, ?, ?, ?)",
                    (listing["id"], reg, sale, disc, ts),
                )

        # Add external links for Zelda
        zelda = conn.execute("SELECT id FROM games WHERE canonical_key LIKE ?", ("%zeldatearsofthekingdom%",)).fetchone()
        if zelda:
            conn.execute(
                "INSERT OR IGNORE INTO external_links (game_id, site, url) VALUES (?, ?, ?)",
                (zelda["id"], "Wikipedia", "https://en.wikipedia.org/wiki/The_Legend_of_Zelda:_Tears_of_the_Kingdom"),
            )
            conn.execute(
                "INSERT OR IGNORE INTO external_links (game_id, site, url) VALUES (?, ?, ?)",
                (zelda["id"], "Metacritic", "https://www.metacritic.com/game/switch/the-legend-of-zelda-tears-of-the-kingdom"),
            )


@pytest.fixture(scope="session")
def db_path(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("test") / "test.db")
    seed_db(path)
    yield path


@pytest.fixture(scope="session")
def live_server(db_path):
    from web import app

    app.config["DB_PATH"] = db_path
    host, port = "127.0.0.1", 15555
    thread = threading.Thread(
        target=lambda: app.run(host=host, port=port, use_reloader=False),
        daemon=True,
    )
    thread.start()
    _wait_for_port(host, port)
    yield f"http://{host}:{port}"


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser
        browser.close()
