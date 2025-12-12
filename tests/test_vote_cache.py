"""Tests for vote caching behavior in adam.vote."""

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

    score_ab = vote(being, a, b)
    score_ba = vote(being, b, a)

    # Cache should be reused; llm should not run
    assert calls["llm"] == 0
    assert score_ab == 15
    assert score_ba == -15

