"""Integration-ish tests that exercise the current adam.py flow without hitting an LLM."""

import asyncio
from pathlib import Path

from adam import Being, append, compact, load
from schema import Init, Perception, Thought


def test_round_trip_load_and_replay(tmp_path):
    """Events written with append should be replayed by load."""
    path = tmp_path / "being.jsonl"
    being = Being(path=path, model="gpt", capacity=4)

    append(being, Init(1, "init-id", capacity=4, model="gpt"))
    append(being, Thought(2, "first", "t1"))
    append(being, Thought(3, "second", "t2"))

    reloaded = load(path)
    assert reloaded.model == "gpt"
    assert reloaded.capacity == 4
    assert set(reloaded.current.keys()) == {"init-id", "t1", "t2"}


def test_compact_with_stubbed_vote(monkeypatch, tmp_path):
    """Compact reduces current memories to half capacity using stubbed votes."""
    import random as pyrandom

    def build_being(name):
        path = tmp_path / f"{name}.jsonl"
        being = Being(path=path, model="gpt", capacity=4)
        append(being, Init(1, "init", capacity=4, model="gpt"))
        for i in range(6):
            append(being, Thought(10 + i, f"t{i}", str(i)))
            append(being, Perception(20 + i, f"p{i}", f"p{i}"))
        return being

    async def fake_vote(_being, a, b):
        return 50 if a.id > b.id else -50

    monkeypatch.setattr("adam.vote", fake_vote)

    async def run_compact(being):
        async for _ in compact(being):
            pass

    pyrandom.seed(0)
    being1 = build_being("a")
    asyncio.run(run_compact(being1))
    kept_ids_1 = set(being1.current.keys())

    pyrandom.seed(0)
    being2 = build_being("b")
    asyncio.run(run_compact(being2))
    kept_ids_2 = set(being2.current.keys())

    # Capacity=4 -> budget=2 after compaction, plus Init (immune)
    assert len(being1.current) == 3  # 2 kept + Init
    assert len(being2.current) == 3
    # Deterministic outcome across runs with same seed
    assert kept_ids_1 == kept_ids_2
