from pathlib import Path

import pytest

SCREENSHOT_DIR = Path(__file__).resolve().parent.parent / "screenshots"


@pytest.fixture(autouse=True)
def ensure_screenshot_dir():
    SCREENSHOT_DIR.mkdir(exist_ok=True)


def test_index_page(browser, live_server):
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.goto(f"{live_server}/")
    page.wait_for_load_state("networkidle")
    page.screenshot(path=str(SCREENSHOT_DIR / "index.png"), full_page=True)
    page.close()


def test_deals_page(browser, live_server):
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.goto(f"{live_server}/deals")
    page.wait_for_load_state("networkidle")
    page.screenshot(path=str(SCREENSHOT_DIR / "deals.png"), full_page=True)
    page.close()


def test_games_page(browser, live_server):
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.goto(f"{live_server}/games")
    page.wait_for_load_state("networkidle")
    page.screenshot(path=str(SCREENSHOT_DIR / "games.png"), full_page=True)
    page.close()


def test_game_detail_page(browser, live_server):
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.goto(f"{live_server}/games/1")
    page.wait_for_load_state("networkidle")
    page.screenshot(path=str(SCREENSHOT_DIR / "game_detail.png"), full_page=True)
    page.close()
