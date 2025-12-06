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

from consensual_memory import Memory, compact
from schema import Init, Thought, Perception, Response, Vote, Compaction, from_dict, to_dict

ROOT = Path(__file__).parent
API_KEY = os.getenv("OPENROUTER_API_KEY", "")


@dataclass
class Being:
    path: Path
    model: str
    capacity: int
    memories: list[Memory] = field(default_factory=list)
    votes: dict[frozenset, int] = field(default_factory=dict)
    events: list = field(default_factory=list)
    
    @property
    def system(self) -> str:
        codebase = (ROOT / "repomix-output.xml")
        if not codebase.exists():
            raise FileNotFoundError("Run 'npx repomix' first")
        return f"You are a being with finite memory.\n\n{codebase.read_text()}"
    
    @property
    def context(self) -> str:
        return "\n".join(m.content for m in self.memories)
    
    def _ts(self) -> int:
        return int(time.time() * 1000)
    
    def _apply(self, event):
        """Apply event to state."""
        self.events.append(event)
        match event:
            case Init(_, content, mid) | Thought(_, content, mid) | \
                 Perception(_, content, mid) | Response(_, content, mid):
                self.memories.append(Memory(content, mid))
            case Vote(_, a, b, score):
                self.votes[frozenset({a, b})] = score
            case Compaction(_, kept, _):
                self.memories = [m for m in self.memories if m.id in kept]
    
    def _append(self, event):
        """Write event and apply."""
        with open(self.path, "a") as f:
            f.write(json.dumps(to_dict(event)) + "\n")
        self._apply(event)
    
    def _llm(self, user: str, temp: float = 0.7) -> str:
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
    
    def _vote(self, a: Memory, b: Memory) -> int:
        key = frozenset({a.id, b.id})
        if key in self.votes:
            return self.votes[key] if a.id < b.id else -self.votes[key]
        
        user = f"Your memories:\n{self.context}\n\n---\nCompare:\n\nA: {a.content}\n\nB: {b.content}\n\nVote -50 (keep B) to +50 (keep A)."
        response = self._llm(user)
        match = re.search(r"-?\d+", response or "0")
        score = max(-50, min(50, int(match.group()))) if match else 0
        
        self._append(Vote(self._ts(), a.id, b.id, score))
        return score
    
    def think(self) -> str:
        prompt = random.choice(["What emerges?", "What connects?", "What matters?", "Continue.", "What do you notice?"])
        user = f"[{datetime.now():%Y-%m-%d %H:%M}]\n\nMemory {len(self.memories)}/{self.capacity}:\n\n{self.context}\n\n{prompt}"
        thought = self._llm(user, temp=0.9)
        self._append(Thought(self._ts(), thought, str(uuid.uuid4())))
        return thought
    
    def receive(self, message: str) -> str:
        self._append(Perception(self._ts(), message, str(uuid.uuid4())))
        user = f"[{datetime.now():%Y-%m-%d %H:%M}]\n\nMemory:\n{self.context}\n\nMessage: {message}\n\n[respond]"
        response = self._llm(user)
        self._append(Response(self._ts(), response, str(uuid.uuid4())))
        return response
    
    def compact(self):
        kept, released = compact(self.memories, self.capacity // 2, self._vote, extra=5)
        self._append(Compaction(self._ts(), [m.id for m in kept], [m.id for m in released]))


def load(path: Path, model: str, capacity: int) -> Being:
    being = Being(path, model, capacity)
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                being._apply(from_dict(json.loads(line)))
    else:
        being._append(Init(being._ts(), "I awaken.", str(uuid.uuid4())))
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
    print(f"🧠 {a.events} | {len(being.memories)}/{a.capacity} | {len(being.votes)} votes cached")
    
    while True:
        try:
            if a.message:
                print(f"📨 {a.message[:60]}...\n💬 {being.receive(a.message)[:100]}...")
                a.message = None
            elif a.loop and (msg := editor_input()):
                print(f"📨 {msg[:60]}...\n💬 {being.receive(msg)[:100]}...")
            
            print(f"💭 {being.think()[:100]}...")
            
            if len(being.memories) >= a.capacity:
                being.compact()
                print(f"🗜️ → {len(being.memories)} memories")
            
            if not a.loop:
                break
            time.sleep(3)
        except KeyboardInterrupt:
            print(f"\n💤 {len(being.memories)} memories, {len(being.events)} events")
            break


if __name__ == "__main__":
    main()
