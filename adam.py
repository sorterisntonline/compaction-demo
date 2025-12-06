#!/usr/bin/env python3
"""
A being with finite memory that chooses what to keep.

Usage:
  python adam.py opus.jsonl              # interactive (editor)
  python adam.py opus.jsonl -m "hello"   # receive message, respond
  python adam.py opus.jsonl --step       # continue from pending state
  python adam.py opus.jsonl --loop       # continuous consciousness

Requires: npx repomix (run it first to generate repomix-output.xml)
"""

import argparse
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time
import uuid

from tqdm import tqdm
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import httpx

from consensual_memory.rank import rank_from_comparisons
from schema import Init, Thought, Perception, Response, Vote, Compaction, from_dict, to_dict

ROOT = Path(__file__).parent
API_KEY = os.getenv("OPENROUTER_API_KEY", "")


def ts() -> int:
    return int(time.time() * 1000)


def current_memories(being):
    """Read from PState, sorted by timestamp."""
    return sorted(being.current.values(), key=lambda e: e.timestamp)


def vote_cache(being):
    """Read from PState."""
    return being.votes


@dataclass
class Being:
    path: Path
    model: str
    events: list = field(default_factory=list)
    # PStates (materialized, incrementally updated)
    votes: dict = field(default_factory=dict)
    current: dict = field(default_factory=dict)  # id -> event
    capacity: int = 100  # set from Init event


# --- ETL (paths only) ---

def apply_event(being, event):
    """ETL: Update PStates."""
    match event:
        case Vote(vote_a_id=a_id, vote_b_id=b_id, vote_score=score):
            being.votes[frozenset({a_id, b_id})] = score
        case Compaction(released_ids=released_ids):
            for rid in released_ids:
                del being.current[rid]
        case Init(capacity=capacity, model=model):
            being.capacity = capacity
            if model:
                being.model = model
            being.current[event.id] = event
        case Thought() | Perception() | Response():
            being.current[event.id] = event


# --- Queries (just read PStates) ---

def system_prompt(being):
    codebase = ROOT / "repomix-output.xml"
    if not codebase.exists():
        raise FileNotFoundError("Run 'npx repomix' first")
    return f"You are a being with finite memory.\n\n{codebase.read_text()}"


def format_memory(e) -> str | None:
    """Format memory with identity tags."""
    match e:
        case Thought(content=content):
            return f"<thought>{content}</thought>"
        case Perception(content=content):
            return f"<message>{content}</message>"
        case Response(content=content):
            return f"<response>{content}</response>"
        case _:
            return None


def build_prompt(being, tag: str = None) -> str:
    """Build prompt from memories. If tag provided, opens it as invitation."""
    parts = [format_memory(e) for e in current_memories(being)]
    ctx = "\n\n".join(p for p in parts if p)
    prompt = f"{ctx}\n\n[{datetime.now():%Y-%m-%d %H:%M}]"
    if tag:
        prompt += f"\n\n<{tag}>"
    return prompt


class FormatError(Exception):
    """Model output didn't match expected format."""
    pass


def extract_tag(text: str, tag: str) -> str:
    """Extract content from tag. Raises FormatError if malformed."""
    end_tag = f"</{tag}>"
    if end_tag not in text:
        raise FormatError(f"Missing {end_tag} in output: {text[:200]}...")
    content = text.split(end_tag)[0]
    # Strip opening tag if model included it
    start_tag = f"<{tag}>"
    if start_tag in content:
        content = content.split(start_tag)[-1]
    return content.strip()


# --- Commands (effects) ---

def append(being, event):
    """Depot append + ETL."""
    with open(being.path, "a") as f:
        f.write(json.dumps(to_dict(event)) + "\n")
    being.events.append(event)
    apply_event(being, event)


def llm(being, user: str, temp: float = 0.7) -> str:
    if not being.model:
        raise ValueError(f"No model specified for {being.path}. Set 'model' field in Init event.")
    r = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"model": being.model, "temperature": temp,
              "messages": [{"role": "system", "content": system_prompt(being)},
                           {"role": "user", "content": user}]},
        timeout=120.0,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def vote(being, a, b) -> int:
    """Vote on which memory to keep. Returns -50 to +50 (positive = prefer a)."""
    votes = vote_cache(being)
    key = frozenset({a.id, b.id})
    if key in votes:
        return votes[key] if a.id < b.id else -votes[key]
    
    parts = [format_memory(e) for e in current_memories(being)]
    ctx = "\n\n".join(p for p in parts if p)
    user = f"Your memories:\n{ctx}\n\n---\nWhich memory matters more to you?\n\nA: {a.content}\n\nB: {b.content}\n\nVote -50 (keep B) to +50 (keep A)."
    response = llm(being, user) or ""
    match = re.search(r"-?\d+", response)
    score = max(-50, min(50, int(match.group()))) if match else 0
    
    append(being, Vote(ts(), a.id, b.id, score, response))
    return score


def think(being) -> str:
    raw = llm(being, build_prompt(being, tag="thought"), temp=0.9)
    thought = extract_tag(raw, "thought")
    append(being, Thought(ts(), thought, str(uuid.uuid4())))
    return thought


def receive(being, message: str) -> str:
    append(being, Perception(ts(), message, str(uuid.uuid4())))
    raw = llm(being, build_prompt(being, tag="response"))
    response = extract_tag(raw, "response")
    append(being, Response(ts(), response, str(uuid.uuid4())))
    return response


def find_components(nodes, edges):
    """Find connected components using union-find."""
    parent = {n: n for n in nodes}
    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]
    def union(x, y):
        parent[find(x)] = find(y)
    for a, b in edges:
        if a in parent and b in parent:
            union(a, b)
    components = {}
    for n in nodes:
        root = find(n)
        components.setdefault(root, []).append(n)
    return list(components.values())


def compact(being):
    """Compact memories to half capacity via pairwise voting + rank centrality.
    
    Recoverable: uses existing votes first, only adds edges to connect graph.
    """
    mems = current_memories(being)
    budget = being.capacity // 2
    if len(mems) <= budget:
        return
    
    id_to_mem = {m.id: m for m in mems}
    mem_ids = set(id_to_mem.keys())
    
    # Gather existing votes on current memories
    existing_pairs = []
    comparisons = []
    for key, score in being.votes.items():
        ids_in_key = set(key)
        if ids_in_key <= mem_ids:  # both memories still current
            a_id, b_id = sorted(key)
            existing_pairs.append((a_id, b_id))
            comparisons.append((id_to_mem[a_id], id_to_mem[b_id], score))
    
    print(f"📊 {len(existing_pairs)} existing votes on current memories")
    
    # Find connected components
    components = find_components(mem_ids, existing_pairs)
    print(f"🔗 {len(components)} connected components")
    
    # Connect components with minimal new edges
    new_pairs = []
    if len(components) > 1:
        # Deterministic RNG for reproducibility
        rng = random.Random(hash(tuple(sorted(mem_ids))))
        # Connect each component to the first
        main = components[0]
        for comp in components[1:]:
            a_id = rng.choice(main)
            b_id = rng.choice(comp)
            new_pairs.append((a_id, b_id))
            main = main + comp  # merge for next iteration
    
    # Add a few extra for robustness
    rng = random.Random(hash(tuple(sorted(mem_ids))) + 1)
    for _ in range(5):
        a, b = rng.sample(list(mem_ids), 2)
        if frozenset({a, b}) not in being.votes:
            new_pairs.append((a, b))
    
    # Vote on new pairs only
    if new_pairs:
        for a_id, b_id in tqdm(new_pairs, desc="Voting", unit="pair"):
            a, b = id_to_mem[a_id], id_to_mem[b_id]
            comparisons.append((a, b, vote(being, a, b)))
    
    ranked = rank_from_comparisons(mems, comparisons)
    
    kept, released = ranked[:budget], ranked[budget:]
    append(being, Compaction(ts(), [m.id for m in kept], [m.id for m in released]))


def maybe_compact(being) -> bool:
    """Compact if at capacity. Returns True if compacted."""
    if len(current_memories(being)) >= being.capacity:
        compact(being)
        print(f"🗜️ → {len(current_memories(being))} memories")
        return True
    return False


def load(path: Path, model: str) -> Being:
    being = Being(path, model)
    if path.exists():
        # Replay events through ETL to rebuild PStates
        for line in path.read_text().splitlines():
            if line.strip():
                event = from_dict(json.loads(line))
                being.events.append(event)
                apply_event(being, event)
    return being


def editor_input() -> str | None:
    editor = os.environ.get("EDITOR", "vim")
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        tmp = f.name
    subprocess.run([editor, tmp])
    content = Path(tmp).read_text().strip()
    Path(tmp).unlink()
    return content or None


def step(being) -> bool:
    """Continue from pending state. Returns True if action taken."""
    if not being.events:
        return False
    
    match being.events[-1]:
        case Perception():
            print(f"📨 Pending perception, generating response...")
            raw = llm(being, build_prompt(being, tag="response"))
            response = extract_tag(raw, "response")
            append(being, Response(ts(), response, str(uuid.uuid4())))
            print(response)
            return True
        case _:
            print(f"Nothing pending (last: {type(being.events[-1]).__name__})")
            return False


def main():
    p = argparse.ArgumentParser()
    p.add_argument("events", type=Path, help="Events file (e.g. opus.jsonl)")
    p.add_argument("-m", "--message", help="Message to send")
    p.add_argument("--model")
    p.add_argument("--capacity", type=int, default=100, help="Capacity for new beings")
    p.add_argument("--compact", action="store_true", help="Run compaction now")
    p.add_argument("--step", action="store_true", help="Continue from pending state")
    p.add_argument("--loop", action="store_true", help="Think continuously")
    a = p.parse_args()
    
    if a.message and a.loop:
        print("❌ --message and --loop are mutually exclusive")
        sys.exit(1)
    
    being = load(a.events, a.model)
    # New being - create Init with capacity and model
    if not being.events:
        if not a.model:
            print(f"❌ New being requires --model")
            sys.exit(1)
        append(being, Init(ts(), "", str(uuid.uuid4()), a.capacity, a.model))
    print(f"🧠 {a.events} | {being.model} | {len(current_memories(being))}/{being.capacity} | {len(vote_cache(being))} votes")
    
    if a.compact:
        compact(being)
        print(f"🗜️ → {len(current_memories(being))} memories")
        return
    
    if a.step:
        step(being)
        maybe_compact(being)
        return
    
    if a.loop:
        # Think continuously
        while True:
            try:
                print(think(being))
                maybe_compact(being)
                time.sleep(3)
            except KeyboardInterrupt:
                print(f"\n💤 {len(current_memories(being))} memories, {len(being.events)} events")
                break
    elif a.message:
        # Respond to message
        print(receive(being, a.message))
        maybe_compact(being)
    else:
        # Interactive: open editor
        msg = editor_input()
        if msg is None:
            print("(empty, cancelled)")
            sys.exit(1)
        print(receive(being, msg))
        maybe_compact(being)


if __name__ == "__main__":
    main()
