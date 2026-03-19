"""Tests for vote caching behavior in adam.vote."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from adam import Being, vote
from schema import Declaration, Thought


def test_vote_uses_cache_when_present(monkeypatch):
    """If a cached score exists, llm should not be called and score should reuse sign."""
    calls = {"llm": 0}

    def fake_llm(*args, **kwargs):
        calls["llm"] += 1
        return "0"

    monkeypatch.setattr("adam.llm", fake_llm)

    being = Being(path=Path("/dev/null"), model="m", capacity=5, vote_model="vote-m")
    being.declaration = Declaration(1, "Keep important memories.", "decl-id")
    a = Thought(1, "A", "a")
    b = Thought(2, "B", "b")

    # Cache a positive score for {a,b}
    being.votes[("a", "b")] = 15

    def _run_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return (
                loop.run_until_complete(vote(being, a, b)),
                loop.run_until_complete(vote(being, b, a)),
            )
        finally:
            loop.close()

    # pytest-asyncio may keep a loop running on the main thread
    with ThreadPoolExecutor(max_workers=1) as pool:
        score_ab, score_ba = pool.submit(_run_in_thread).result()

    # Cache should be reused; llm should not run
    assert calls["llm"] == 0
    assert score_ab == 15
    assert score_ba == -15

