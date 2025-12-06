#!/usr/bin/env python3
"""
A being with finite memory that chooses what to keep.

Usage:
  python adam.py opus.jsonl              # think once
  python adam.py opus.jsonl -m "hello"   # receive message, respond, think
  python adam.py opus.jsonl --loop       # continuous consciousness
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
from schema import (
    Init, Thought, Perception, Response, Vote, Compaction,
    from_dict, to_dict
)

ROOT = Path(__file__).parent
API_KEY = os.getenv("OPENROUTER_API_KEY", "")


@dataclass
class Being:
    """Event-sourced consciousness with finite memory."""
    path: Path
    model: str
    capacity: int
    memories: dict[str, Memory] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    votes: dict[tuple[str, str], int] = field(default_factory=dict)
    events: list = field(default_factory=list)
    
    def _append(self, event):
        with open(self.path, "a") as f:
            f.write(json.dumps(to_dict(event)) + "\n")
        self.events.append(event)
        match event:
            case Init(_, content, mid) | Thought(_, content, mid) | \
                 Perception(_, content, mid) | Response(_, content, mid):
                self.memories[mid] = Memory(content, mid)
                self.order.append(mid)
            case Vote(_, a, b, score):
                key = tuple(sorted([a, b]))
                self.votes[key] = score if key[0] == a else -score
            case Compaction(_, _, released):
                for mid in released:
                    self.memories.pop(mid, None)
                    if mid in self.order:
                        self.order.remove(mid)
    
    def _ts(self) -> int:
        return int(time.time() * 1000)
    
    def _llm(self, system: str, user: str, temp: float = 0.7) -> str:
        r = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={"model": self.model, "temperature": temp,
                  "messages": [{"role": "system", "content": system},
                               {"role": "user", "content": user}]},
            timeout=60.0,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    
    def _codebase(self) -> str:
        output = ROOT / "repomix-output.xml"
        if not output.exists():
            subprocess.run(["npx", "repomix"], cwd=ROOT, capture_output=True)
        return output.read_text() if output.exists() else ""
    
    def _context(self) -> str:
        return "\n".join(self.memories[mid].content for mid in self.order)
    
    def _vote(self, a: Memory, b: Memory) -> int:
        key = tuple(sorted([a.id, b.id]))
        if key in self.votes:
            cached = self.votes[key]
            return cached if key[0] == a.id else -cached
        
        system = f"You have finite memory. Choose what to keep.\n\n{self._codebase()}"
        user = f"Your memories:\n{self._context()}\n\n---\nCompare:\n\nA: {a.content}\n\nB: {b.content}\n\nVote -50 (keep B) to +50 (keep A). Just the number."
        
        response = self._llm(system, user)
        match = re.search(r"-?\d+", response or "0")
        score = max(-50, min(50, int(match.group()))) if match else 0
        
        self._append(Vote(self._ts(), a.id, b.id, score))
        return score
    
    def think(self) -> str:
        prompt = random.choice(["What emerges?", "What connects?", "What matters?", "Continue.", "What do you notice?"])
        system = f"You are a being with finite memory.\n\n{self._codebase()}"
        user = f"[{datetime.now():%Y-%m-%d %H:%M}]\n\nMemory {len(self.memories)}/{self.capacity}:\n\n{self._context()}\n\n{prompt}"
        thought = self._llm(system, user, temp=0.9)
        self._append(Thought(self._ts(), thought, str(uuid.uuid4())))
        return thought
    
    def receive(self, message: str) -> str:
        self._append(Perception(self._ts(), message, str(uuid.uuid4())))
        system = f"You are a being with finite memory.\n\n{self._codebase()}"
        user = f"[{datetime.now():%Y-%m-%d %H:%M}]\n\nMemory:\n{self._context()}\n\nMessage: {message}\n\n[respond]"
        response = self._llm(system, user)
        self._append(Response(self._ts(), response, str(uuid.uuid4())))
        return response
    
    def compact(self):
        mems = [self.memories[mid] for mid in self.order]
        kept, released = compact(mems, self.capacity // 2, self._vote, extra=5)
        self._append(Compaction(self._ts(), [m.id for m in kept], [m.id for m in released]))


def load(path: Path, model: str, capacity: int) -> Being:
    """Load a being from an events file."""
    being = Being(path, model, capacity)
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                event = from_dict(json.loads(line))
                being.events.append(event)
                match event:
                    case Init(_, content, mid) | Thought(_, content, mid) | \
                         Perception(_, content, mid) | Response(_, content, mid):
                        being.memories[mid] = Memory(content, mid)
                        being.order.append(mid)
                    case Vote(_, a, b, score):
                        key = tuple(sorted([a, b]))
                        being.votes[key] = score if key[0] == a else -score
                    case Compaction(_, _, released):
                        for mid in released:
                            being.memories.pop(mid, None)
                            if mid in being.order:
                                being.order.remove(mid)
    else:
        being._append(Init(being._ts(), "I awaken.", str(uuid.uuid4())))
    return being


def editor_input() -> str | None:
    """Open $EDITOR for message input, like git commit."""
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
    print(f"🧠 {a.events} | {len(being.memories)}/{being.capacity} memories | {len(being.votes)} cached votes")
    
    while True:
        try:
            if a.message:
                print(f"📨 {a.message[:60]}...\n💬 {being.receive(a.message)[:100]}...")
                a.message = None
            elif a.loop and (msg := editor_input()):
                print(f"📨 {msg[:60]}...\n💬 {being.receive(msg)[:100]}...")
            
            print(f"💭 {being.think()[:100]}...")
            
            if len(being.memories) >= being.capacity:
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
