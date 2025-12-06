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

from consensual_memory.memory import compact
from schema import Init, Thought, Perception, Response, Vote, Compaction, from_dict, to_dict
from specter import P, ALL

ROOT = Path(__file__).parent
API_KEY = os.getenv("OPENROUTER_API_KEY", "")


def ts() -> int:
    return int(time.time() * 1000)


@dataclass
class Being:
    path: Path
    model: str
    capacity: int
    events: list = field(default_factory=list)
    
    # PStates: derived from events
    @property
    def released(self) -> set:
        return {id for e in self.events if isinstance(e, Compaction) for id in e.released_ids}
    
    @property
    def votes(self) -> dict:
        return {frozenset({e.vote_a_id, e.vote_b_id}): e.vote_score for e in self.events if isinstance(e, Vote)}
    
    @property
    def current(self) -> list:
        is_memory = lambda e: isinstance(e, (Init, Thought, Perception, Response))
        not_released = lambda e: e.id not in self.released
        return P.events[ALL][is_memory][not_released].select(self)
    
    @property
    def system(self) -> str:
        codebase = ROOT / "repomix-output.xml"
        if not codebase.exists():
            raise FileNotFoundError("Run 'npx repomix' first")
        return f"You are a being with finite memory.\n\n{codebase.read_text()}"
    
    # Views
    def prompt(self, suffix: str) -> str:
        ctx = "\n".join(e.content for e in self.current)
        return f"[{datetime.now():%Y-%m-%d %H:%M}]\n\nMemory {len(self.current)}/{self.capacity}:\n\n{ctx}\n\n{suffix}"
    
    # Depot: just append
    def append(self, event):
        with open(self.path, "a") as f:
            f.write(json.dumps(to_dict(event)) + "\n")
        self.events.append(event)
    
    # Actions
    def llm(self, user: str, temp: float = 0.7) -> str:
        r = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={"model": self.model, "temperature": temp,
                  "messages": [{"role": "system", "content": self.system},
                               {"role": "user", "content": user}]},
            timeout=60.0,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    
    def vote(self, a, b) -> int:
        key = frozenset({a.id, b.id})
        if key in self.votes:
            return self.votes[key] if a.id < b.id else -self.votes[key]
        
        ctx = "\n".join(e.content for e in self.current)
        user = f"Your memories:\n{ctx}\n\n---\nCompare:\n\nA: {a.content}\n\nB: {b.content}\n\nVote -50 (keep B) to +50 (keep A)."
        response = self.llm(user)
        match = re.search(r"-?\d+", response or "0")
        score = max(-50, min(50, int(match.group()))) if match else 0
        
        self.append(Vote(ts(), a.id, b.id, score))
        return score
    
    def think(self) -> str:
        prompt = random.choice(["What emerges?", "What connects?", "What matters?", "Continue.", "What do you notice?"])
        thought = self.llm(self.prompt(prompt), temp=0.9)
        self.append(Thought(ts(), thought, str(uuid.uuid4())))
        return thought
    
    def receive(self, message: str) -> str:
        self.append(Perception(ts(), message, str(uuid.uuid4())))
        response = self.llm(self.prompt(f"Message: {message}\n\n[respond]"))
        self.append(Response(ts(), response, str(uuid.uuid4())))
        return response
    
    def do_compact(self):
        mems = self.current
        kept, released = compact(mems, self.capacity // 2, self.vote, extra=5)
        self.append(Compaction(ts(), [m.id for m in kept], [m.id for m in released]))


def load(path: Path, model: str, capacity: int) -> Being:
    being = Being(path, model, capacity)
    if path.exists():
        being.events = [from_dict(json.loads(line)) for line in path.read_text().splitlines() if line.strip()]
    else:
        being.append(Init(ts(), "I awaken.", str(uuid.uuid4())))
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
    print(f"🧠 {a.events} | {len(being.current)}/{a.capacity} | {len(being.votes)} votes")
    
    while True:
        try:
            if a.message:
                print(f"📨 {a.message[:60]}...\n💬 {being.receive(a.message)[:100]}...")
                a.message = None
            elif a.loop and (msg := editor_input()):
                print(f"📨 {msg[:60]}...\n💬 {being.receive(msg)[:100]}...")
            
            print(f"💭 {being.think()[:100]}...")
            
            if len(being.current) >= a.capacity:
                being.do_compact()
                print(f"🗜️ → {len(being.current)} memories")
            
            if not a.loop:
                break
            time.sleep(3)
        except KeyboardInterrupt:
            print(f"\n💤 {len(being.current)} memories, {len(being.events)} events")
            break


if __name__ == "__main__":
    main()
