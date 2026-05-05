#!/usr/bin/env python3
"""Flask web app for browsing Nintendo eShop games."""

import json
import os

from flask import Flask, current_app, render_template, request
from db import get_db, get_current_deals, search_games, get_game_detail

app = Flask(__name__)
app.config["DB_PATH"] = os.environ.get("ESHOP_DB_PATH", "eshop.db")


def row_to_dict(row):
    """Convert a sqlite3.Row to a plain dict and parse genres JSON."""
    d = dict(row)
    if "genres" in d and isinstance(d["genres"], str):
        try:
            d["genres"] = json.loads(d["genres"])
        except (json.JSONDecodeError, TypeError):
            d["genres"] = []
    return d


@app.route("/")
def index():
    with get_db(current_app.config["DB_PATH"]) as conn:
        deals = get_current_deals(conn, min_discount=10)
    return render_template("index.html", deals=deals[:20])


@app.route("/deals")
def deals():
    min_discount = request.args.get("min", 0, type=float)
    with get_db(current_app.config["DB_PATH"]) as conn:
        results = get_current_deals(conn, min_discount=min_discount)
    return render_template("deals.html", deals=results, min_discount=min_discount)


@app.route("/games")
def games_list():
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    with get_db(current_app.config["DB_PATH"]) as conn:
        games, total = search_games(conn, q, page=page)
    total_pages = (total + 23) // 24
    return render_template("games.html", games=games, query=q,
                           page=page, total_pages=total, total=total)


@app.route("/games/<int:game_id>")
def game_detail(game_id):
    with get_db(current_app.config["DB_PATH"]) as conn:
        detail = get_game_detail(conn, game_id)
    if not detail:
        return "Game not found", 404
    detail["game"] = row_to_dict(detail["game"])
    detail["genres"] = detail["game"].get("genres", [])
    detail["price_history"] = [dict(s) for s in detail["price_history"]]
    detail["external_links"] = [dict(l) for l in detail["external_links"]]
    detail["listings"] = [dict(l) for l in detail["listings"]]
    return render_template("game.html", **detail)


if __name__ == "__main__":
    app.run(debug=True, port=8080)
