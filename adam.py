#!/usr/bin/env python3
"""
A being with finite memory that chooses what to keep.

Usage: python adam.py <directory> [--capacity N] [--model MODEL]
"""

import argparse
import json
import os
import random
import re
import time
import uuid
from datetime import datetime
from pathlib import Path

import httpx

from consensual_memory import Memory, compact
from schema import (
    Event, Init, Thought, Perception, Response, Vote, Compaction,
    from_dict, to_dict, VERSION
)

ROOT = Path(__file__).parent
API_KEY = os.getenv("OPENROUTER_API_KEY", "")


class Being:
    """Event-sourced consciousness with finite memory."""
    
    def __init__(self, path: Path, model: str, capacity: int):
        self.path = Path(path)
        self.model = model
        self.capacity = capacity
        
        # State (materialized from events)
        self.memories: dict[str, Memory] = {}
        self.order: list[str] = []
        self.votes: dict[tuple[str, str], int] = {}
        self.events: list[Event] = []
        
        # Setup
        self.path.mkdir(exist_ok=True)
        (self.path / "inbox").mkdir(exist_ok=True)
        self._replay()
    
    def _replay(self):
        """Rebuild state from event log."""
        events_file = self.path / "events.jsonl"
        if not events_file.exists():
            return
        
        for line in events_file.read_text().splitlines():
            if line.strip():
                event = from_dict(json.loads(line))
                self._apply(event)
    
    def _apply(self, event: Event):
        """Apply event to state using pattern matching."""
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
    
    def _append(self, event: Event):
        """Write event to log and apply."""
        with open(self.path / "events.jsonl", "a") as f:
            f.write(json.dumps(to_dict(event)) + "\n")
        self._apply(event)
    
    def _ts(self) -> int:
        """Current timestamp in milliseconds."""
        return int(time.time() * 1000)
    
    def _llm(self, system: str, user: str, temp: float = 0.7) -> str | None:
        """Call LLM. Returns None on failure."""
        try:
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
        except Exception as e:
            print(f"LLM error: {e}")
            return None
    
    def _vote(self, a: Memory, b: Memory) -> int:
        """Vote on which memory to keep. Checks cache first."""
        key = tuple(sorted([a.id, b.id]))
        if key in self.votes:
            cached = self.votes[key]
            return cached if key[0] == a.id else -cached
        
        context = "\n".join(f"[{i+1}] {self.memories[mid].content}" 
                           for i, mid in enumerate(self.order))
        
        system = f"You have finite memory. Choose what to keep.\n\n{self._codebase()}"
        user = f"Your memories:\n{context}\n\n---\nCompare:\n\nA: {a.content}\n\nB: {b.content}\n\nVote -50 (keep B) to +50 (keep A). Just the number."
        
        response = self._llm(system, user)
        match = re.search(r"-?\d+", response or "0")
        score = max(-50, min(50, int(match.group()))) if match else 0
        
        self._append(Vote(self._ts(), a.id, b.id, score))
        return score
    
    def _codebase(self) -> str:
        """Load source for self-awareness."""
        parts = []
        for name in ["adam.py", "schema.py"]:
            if (ROOT / name).exists():
                parts.append(f"=== {name} ===\n{(ROOT / name).read_text()}")
        for f in sorted((ROOT / "consensual_memory").glob("*.py")):
            if f.name != "__init__.py":
                parts.append(f"=== consensual_memory/{f.name} ===\n{f.read_text()}")
        return "\n\n".join(parts)
    
    def think(self) -> str | None:
        """Generate a thought."""
        context = "\n".join(self.memories[mid].content for mid in self.order)
        prompt = random.choice([
            "What emerges?", "What connects?", "What matters?",
            "Continue.", "What's on your mind?", "What do you notice?"
        ])
        
        system = f"You are a being with finite memory.\n\n{self._codebase()}"
        user = f"[{datetime.now():%Y-%m-%d %H:%M}]\n\nMemory {len(self.memories)}/{self.capacity}:\n\n{context}\n\n{prompt}"
        
        thought = self._llm(system, user, temp=0.9)
        if not thought:
            return None
        
        self._append(Thought(self._ts(), thought, str(uuid.uuid4())))
        return thought
    
    def check_inbox(self) -> str | None:
        """Check for and process one message."""
        inbox = self.path / "inbox"
        messages = sorted(inbox.glob("*.txt"))
        if not messages:
            return None
        
        msg = messages[0]
        content = msg.read_text().strip()
        msg.rename(msg.with_suffix(".read"))
        
        if not content:
            return None
        
        self._append(Perception(self._ts(), content, str(uuid.uuid4())))
        return content
    
    def respond(self, message: str) -> str | None:
        """Respond to a message."""
        context = "\n".join(self.memories[mid].content for mid in self.order)
        
        system = f"You are a being with finite memory.\n\n{self._codebase()}"
        user = f"[{datetime.now():%Y-%m-%d %H:%M}]\n\nMemory:\n{context}\n\nMessage: {message}\n\n[respond]"
        
        response = self._llm(system, user)
        if not response:
            return None
        
        self._append(Response(self._ts(), response, str(uuid.uuid4())))
        return response
    
    def compact(self):
        """Compact memories to half capacity."""
        mems = [self.memories[mid] for mid in self.order]
        kept, released = compact(mems, self.capacity // 2, self._vote, extra=5)
        
        self._append(Compaction(
            self._ts(),
            tuple(m.id for m in kept),
            tuple(m.id for m in released)
        ))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory")
    parser.add_argument("--model", default="anthropic/claude-sonnet-4")
    parser.add_argument("--capacity", type=int, default=100)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    
    being = Being(Path(args.directory), args.model, args.capacity)
    
    if not being.events:
        being._append(Init(
            int(time.time() * 1000),
            "I awaken.",
            str(uuid.uuid4())
        ))
    
    print(f"🧠 {args.directory} | {len(being.memories)}/{being.capacity} memories | {len(being.votes)} cached votes")
    
    while True:
        try:
            if msg := being.check_inbox():
                print(f"📨 {msg[:60]}...")
                if response := being.respond(msg):
                    print(f"💬 {response[:100]}...")
            
            if thought := being.think():
                print(f"💭 {thought[:100]}...")
            
            if len(being.memories) >= being.capacity:
                print(f"🗜️ Compacting...")
                being.compact()
                print(f"   → {len(being.memories)} memories remain")
            
            if args.once:
                break
            
            time.sleep(3)
            
        except KeyboardInterrupt:
            print(f"\n💤 {len(being.memories)} memories, {len(being.events)} events")
            break


if __name__ == "__main__":
    main()
