"""Tests for the homepage messaging bubble feature."""

from pathlib import Path

from app.app import _messaging_bubbles
from app.state import AppStateManager


def test_messaging_bubbles_empty():
    """No bubbles when no handles are configured."""
    assert _messaging_bubbles({}) == []


def test_messaging_bubbles_sms():
    bubbles = _messaging_bubbles({"phone": "+15551234567"})
    assert len(bubbles) == 1
    assert bubbles[0][1]["href"] == "sms:+15551234567"
    assert bubbles[0][2] == "SMS"


def test_messaging_bubbles_telegram():
    bubbles = _messaging_bubbles({"telegram": "mybot"})
    assert len(bubbles) == 1
    assert bubbles[0][1]["href"] == "https://t.me/mybot"


def test_messaging_bubbles_signal():
    bubbles = _messaging_bubbles({"signal": "+15559876543"})
    assert len(bubbles) == 1
    assert "signal.me" in bubbles[0][1]["href"]
    assert "+15559876543" in bubbles[0][1]["href"]


def test_messaging_bubbles_matrix():
    bubbles = _messaging_bubbles({"matrix": "@alice:example.org"})
    assert len(bubbles) == 1
    assert "matrix.to" in bubbles[0][1]["href"]
    assert "@alice:example.org" in bubbles[0][1]["href"]


def test_messaging_bubbles_all_platforms():
    handles = {
        "phone": "+15550000001",
        "telegram": "tguser",
        "signal": "+15550000002",
        "matrix": "@user:server.org",
    }
    bubbles = _messaging_bubbles(handles)
    assert len(bubbles) == 4


def test_get_messaging_defaults(tmp_path):
    """get_messaging returns empty strings when nothing is configured."""
    log_path = tmp_path / "app.jsonl"
    manager = AppStateManager(log_path)
    messaging = manager.get_messaging("some-being")
    assert messaging == {"phone": "", "telegram": "", "signal": "", "matrix": ""}


def test_get_messaging_after_set_config(tmp_path):
    """get_messaging reflects values stored via set_config."""
    log_path = tmp_path / "app.jsonl"
    manager = AppStateManager(log_path)
    manager.set_config("being1", "telegram", "tommy_bot")
    manager.set_config("being1", "signal", "+15550000099")
    messaging = manager.get_messaging("being1")
    assert messaging["telegram"] == "tommy_bot"
    assert messaging["signal"] == "+15550000099"
    assert messaging["phone"] == ""
    assert messaging["matrix"] == ""
