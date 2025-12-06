#!/usr/bin/env python3
"""
A being with finite memory that chooses what to keep.

Usage:
  python adam.py opus.jsonl              # think once
  python adam.py opus.jsonl -m "hello"   # receive message, respond, think
  python adam.py opus.jsonl --loop       # continuous consciousness

Requires: npx repomix (run it first to generate repomix-output.xml)
"""

import argparse
import json
import os
import random
import re
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import httpx

from consensual_memory.rank import rank_from_comparisons
from schema import Init, Thought, Perception, Response, Vote, Compaction, from_dict, to_dict
from specter import P, ALL, TYPE

ROOT = Path(__file__).parent
API_KEY = os.getenv("OPENROUTER_API_KEY", "")


def ts() -> int:
    return int(time.time() * 1000)


def current_memories(being):
    """Select non-released memory events."""
    released = set(P[being].events[ALL][TYPE(Compaction)].released_ids[ALL].select())
    return P[being].events[ALL][TYPE(Init, Thought, Perception, Response)][lambda e: e.id not in released].select()


def vote_cache(being):
    """Build vote lookup from events."""
    to_pair = lambda e: (frozenset({e.vote_a_id, e.vote_b_id}), e.vote_score)
    return dict(P[being].events[ALL][TYPE(Vote)].map(to_pair).select())


@dataclass
class Being:
    path: Path
    model: str
    capacity: int
    events: list = field(default_factory=list)


# --- Queries (pure) ---

def system_prompt(being):
    codebase = ROOT / "repomix-output.xml"
    if not codebase.exists():
        raise FileNotFoundError("Run 'npx repomix' first")
    return f"You are a being with finite memory.\n\n{codebase.read_text()}"


def build_prompt(being, suffix: str) -> str:
    current = current_memories(being)
    ctx = "\n".join(e.content for e in current)
    return f"[{datetime.now():%Y-%m-%d %H:%M}]\n\nMemory {len(current)}/{being.capacity}:\n\n{ctx}\n\n{suffix}"


# --- Commands (effects) ---

def append(being, event):
    with open(being.path, "a") as f:
        f.write(json.dumps(to_dict(event)) + "\n")
    being.events.append(event)


def llm(being, user: str, temp: float = 0.7) -> str:
    r = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"model": being.model, "temperature": temp,
              "messages": [{"role": "system", "content": system_prompt(being)},
                           {"role": "user", "content": user}]},
        timeout=60.0,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def vote(being, a, b) -> int:
    """Vote on which memory to keep. Returns -50 to +50 (positive = prefer a)."""
    votes = vote_cache(being)
    key = frozenset({a.id, b.id})
    if key in votes:
        return votes[key] if a.id < b.id else -votes[key]
    
    ctx = "\n".join(e.content for e in current_memories(being))
    user = f"Your memories:\n{ctx}\n\n---\nCompare:\n\nA: {a.content}\n\nB: {b.content}\n\nVote -50 (keep B) to +50 (keep A)."
    response = llm(being, user)
    match = re.search(r"-?\d+", response or "0")
    score = max(-50, min(50, int(match.group()))) if match else 0
    
    append(being, Vote(ts(), a.id, b.id, score))
    return score


def think(being) -> str:
    prompt = random.choice(["What emerges?", "What connects?", "What matters?", "Continue.", "What do you notice?"])
    thought = llm(being, build_prompt(being, prompt), temp=0.9)
    append(being, Thought(ts(), thought, str(uuid.uuid4())))
    return thought


def receive(being, message: str) -> str:
    append(being, Perception(ts(), message, str(uuid.uuid4())))
    response = llm(being, build_prompt(being, f"Message: {message}\n\n[respond]"))
    append(being, Response(ts(), response, str(uuid.uuid4())))
    return response


def compact(being):
    """Compact memories to half capacity via pairwise voting + rank centrality."""
    mems = current_memories(being)
    budget = being.capacity // 2
    if len(mems) <= budget:
        return
    
    # Build spanning tree: each new item connects to existing tree
    shuffled = random.sample(mems, len(mems))
    pairs = []
    for k in range(1, len(shuffled)):
        existing = random.choice(shuffled[:k])
        new = shuffled[k]
        pairs.append((existing, new))
    
    # Add extra comparisons for robustness
    for _ in range(5):
        pairs.append(tuple(random.sample(mems, 2)))
    
    # Vote on each pair, rank by centrality
    comparisons = [(a, b, vote(being, a, b)) for a, b in pairs]
    ranked = rank_from_comparisons(mems, comparisons)
    
    kept, released = ranked[:budget], ranked[budget:]
    append(being, Compaction(ts(), [m.id for m in kept], [m.id for m in released]))


def load(path: Path, model: str, capacity: int) -> Being:
    being = Being(path, model, capacity)
    if path.exists():
        being.events = [from_dict(json.loads(line)) for line in path.read_text().splitlines() if line.strip()]
    else:
        append(being, Init(ts(), "I awaken.", str(uuid.uuid4())))
    return being


def editor_input() -> str | None:
    editor = os.environ.get("EDITOR", "vim")
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"\n# Enter message above. Lines starting with # are ignored.\n")
        tmp = f.name
    subprocess.run([editor, tmp])
    content = Path(tmp).read_text()
    Path(tmp).unlink()
    lines = [l for l in content.splitlines() if not l.startswith("#")]
    return "\n".join(lines).strip() or None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("events", type=Path, help="Events file (e.g. opus.jsonl)")
    p.add_argument("-m", "--message", help="Message to send")
    p.add_argument("--model", default="anthropic/claude-sonnet-4")
    p.add_argument("--capacity", type=int, default=100)
    p.add_argument("--loop", action="store_true", help="Continuous consciousness")
    a = p.parse_args()
    
    being = load(a.events, a.model, a.capacity)
    print(f"🧠 {a.events} | {len(current_memories(being))}/{a.capacity} | {len(vote_cache(being))} votes")
    
    while True:
        try:
            if a.message:
                print(f"📨 {a.message[:60]}...\n💬 {receive(being, a.message)[:100]}...")
                a.message = None
            elif a.loop and (msg := editor_input()):
                print(f"📨 {msg[:60]}...\n💬 {receive(being, msg)[:100]}...")
            
            print(f"💭 {think(being)[:100]}...")
            
            if len(current_memories(being)) >= a.capacity:
                compact(being)
                print(f"🗜️ → {len(current_memories(being))} memories")
            
            if not a.loop:
                break
            time.sleep(3)
        except KeyboardInterrupt:
            print(f"\n💤 {len(current_memories(being))} memories, {len(being.events)} events")
            break


if __name__ == "__main__":
    main()
