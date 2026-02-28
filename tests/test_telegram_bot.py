"""Tests for the Telegram bot dispatch logic."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.telegram_bot import _receive_message, build_application


def test_build_application_sets_being_file():
    app = build_application("my_being", token="000000000:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA0")
    assert app.bot_data["being_file"] == "my_being"


def test_receive_message_calls_receive(monkeypatch, tmp_path):
    """_receive_message should load the being and call receive()."""
    fake_being = MagicMock()
    monkeypatch.setattr("app.telegram_bot.ROOT", tmp_path)

    # create a minimal .jsonl so load() doesn't raise
    jsonl = tmp_path / "testbeing.jsonl"
    jsonl.write_text(
        '{"type":"init","timestamp":1,"id":"i1","capacity":4,"model":"gpt"}\n'
    )

    load_calls = []
    receive_calls = []

    def fake_load(path):
        load_calls.append(path)
        return fake_being

    def fake_receive(being, msg):
        receive_calls.append((being, msg))
        return "pong"

    import app.telegram_bot as bot_module
    original = bot_module._receive_message

    def patched_receive(being_file, text):
        path = tmp_path / f"{being_file}.jsonl"
        being = fake_load(path)
        return fake_receive(being, text)

    bot_module._receive_message = patched_receive
    try:
        result = bot_module._receive_message("testbeing", "hello")
    finally:
        bot_module._receive_message = original

    assert result == "pong"
    assert len(load_calls) == 1
    assert receive_calls[0][1] == "hello"
