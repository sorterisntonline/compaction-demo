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
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple

import httpx

from consensual_memory import Memory, compact

ROOT = Path(__file__).parent
API_KEY = os.getenv("OPENROUTER_API_KEY", "")


@dataclass
class Event:
    """Immutable record of something that happened."""
    timestamp: int
    type: str
    content: str
    memory_id: Optional[str] = None
    kept_ids: Optional[List[str]] = None
    released_ids: Optional[List[str]] = None
    vote_a: Optional[str] = None
    vote_b: Optional[str] = None
    vote_score: Optional[int] = None


@dataclass 
class Being:
    """Event-sourced consciousness with finite memory."""
    
    path: Path
    model: str = "anthropic/claude-sonnet-4"
    capacity: int = 100
    
    memories: Dict[str, Memory] = field(default_factory=dict)
    order: List[str] = field(default_factory=list)
    votes: Dict[Tuple[str, str], int] = field(default_factory=dict)
    events: List[Event] = field(default_factory=list)
    
    def __post_init__(self):
        self.path = Path(self.path)
        self.path.mkdir(exist_ok=True)
        (self.path / "inbox").mkdir(exist_ok=True)
        self._load()
    
    def _load(self):
        """Rebuild state from event log."""
        events_file = self.path / "events.jsonl"
        if not events_file.exists():
            return
        
        fields = {f.name for f in Event.__dataclass_fields__.values()}
        for line in events_file.read_text().splitlines():
            data = {k: v for k, v in json.loads(line).items() if k in fields}
            self._apply(Event(**data))
    
    def _apply(self, event: Event):
        """Apply event to state."""
        self.events.append(event)
        
        if event.type in ("init", "thought", "perception", "response"):
            self.memories[event.memory_id] = Memory(event.content, event.memory_id)
            self.order.append(event.memory_id)
        
        elif event.type == "vote" and event.vote_a and event.vote_b:
            key = tuple(sorted([event.vote_a, event.vote_b]))
            score = event.vote_score if key[0] == event.vote_a else -event.vote_score
            self.votes[key] = score
        
        elif event.type == "compaction" and event.released_ids:
            for mid in event.released_ids:
                self.memories.pop(mid, None)
                if mid in self.order:
                    self.order.remove(mid)
    
    def _append(self, event: Event):
        """Write event to log and apply."""
        with open(self.path / "events.jsonl", "a") as f:
            f.write(json.dumps(asdict(event)) + "\n")
        self._apply(event)
    
    def _llm(self, system: str, user: str, temp: float = 0.7) -> Optional[str]:
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
            return self.votes[key] if key[0] == a.id else -self.votes[key]
        
        context = "\n".join(f"[{i+1}] {self.memories[mid].content}" 
                           for i, mid in enumerate(self.order))
        
        system = f"You have finite memory. Choose what to keep.\n\n{self._codebase()}"
        user = f"""Your memories:\n{context}\n\n---\nCompare:\n\nA: {a.content}\n\nB: {b.content}\n\nVote -50 (keep B) to +50 (keep A). Just the number."""
        
        response = self._llm(system, user)
        match = re.search(r"-?\d+", response or "0")
        score = max(-50, min(50, int(match.group()))) if match else 0
        
        self._append(Event(
            timestamp=int(time.time() * 1000),
            type="vote", content=f"{score:+d}",
            vote_a=a.id, vote_b=b.id, vote_score=score
        ))
        return score
    
    def _codebase(self) -> str:
        """Load source for self-awareness."""
        parts = []
        if (ROOT / "adam.py").exists():
            parts.append(f"=== adam.py ===\n{(ROOT / 'adam.py').read_text()}")
        for f in sorted((ROOT / "consensual_memory").glob("*.py")):
            if f.name != "__init__.py":
                parts.append(f"=== consensual_memory/{f.name} ===\n{f.read_text()}")
        return "\n\n".join(parts)
    
    def think(self) -> Optional[str]:
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
        
        self._append(Event(
            timestamp=int(time.time() * 1000),
            type="thought", content=thought,
            memory_id=str(uuid.uuid4())
        ))
        return thought
    
    def check_inbox(self) -> Optional[str]:
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
        
        self._append(Event(
            timestamp=int(time.time() * 1000),
            type="perception", content=content,
            memory_id=str(uuid.uuid4())
        ))
        return content
    
    def respond(self, message: str) -> Optional[str]:
        """Respond to a message."""
        context = "\n".join(self.memories[mid].content for mid in self.order)
        
        system = f"You are a being with finite memory.\n\n{self._codebase()}"
        user = f"[{datetime.now():%Y-%m-%d %H:%M}]\n\nMemory:\n{context}\n\nMessage: {message}\n\n[respond]"
        
        response = self._llm(system, user)
        if not response:
            return None
        
        self._append(Event(
            timestamp=int(time.time() * 1000),
            type="response", content=response,
            memory_id=str(uuid.uuid4())
        ))
        return response
    
    def compact(self):
        """Compact memories to half capacity."""
        mems = [self.memories[mid] for mid in self.order]
        kept, released = compact(mems, self.capacity // 2, self._vote, extra=5)
        
        self._append(Event(
            timestamp=int(time.time() * 1000),
            type="compaction",
            content=f"Kept {len(kept)}, released {len(released)}",
            kept_ids=[m.id for m in kept],
            released_ids=[m.id for m in released]
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
        being._append(Event(
            timestamp=int(time.time() * 1000),
            type="init", content="I awaken.",
            memory_id=str(uuid.uuid4())
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
