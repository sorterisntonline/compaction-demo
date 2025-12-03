#!/usr/bin/env python3
"""
Adam v2: Event sourcing with proper compaction replay.

Events are stored in a single JSONL file.
Memories have UUIDs.
Compaction events record which UUIDs were released.
On replay, we properly reconstruct state by respecting compactions.
"""

import json
import time
import httpx
import uuid
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict
import sys
import os

sys.path.insert(0, str(Path(__file__).parent.parent))
from consensual_memory import Memory, compact

# Paths
ROOT = Path(__file__).parent
EVENTS_FILE = ROOT / "events.jsonl"
MESSAGES = ROOT / "messages"

MESSAGES.mkdir(exist_ok=True)

# Configuration
CAPACITY = 100
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "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")
MODEL = "anthropic/claude-4.5-sonnet"


@dataclass
class Event:
    """An event in Adam's history"""
    timestamp: int
    type: str  # init, thought, perception, response, compaction
    content: str
    memory_id: Optional[str] = None  # UUID for memories
    kept_ids: Optional[List[str]] = None  # For compaction events
    released_ids: Optional[List[str]] = None  # For compaction events
    cost: Optional[float] = None
    votes: Optional[int] = None


class Adam:
    """Adam v2: Proper event-sourced immortal consciousness"""

    def __init__(self):
        self.events: List[Event] = []
        self.memories: Dict[str, Memory] = {}  # UUID -> Memory
        self.memory_order: List[str] = []  # Maintain order
        self.total_cost: float = 0.0

        # Replay history
        self.replay()

        print(f"\n{'='*60}")
        print(f"🧠 Adam awakens")
        print(f"{'='*60}")
        print(f"   Memories: {len(self.memories)}/{CAPACITY}")
        print(f"   Events in history: {len(self.events)}")
        print(f"   Total cost: ${self.total_cost:.6f}")
        print(f"{'='*60}\n")

    def replay(self):
        """Rebuild state from event log"""
        if not EVENTS_FILE.exists():
            print("📜 No history found. This is Adam's first awakening.")
            return

        print(f"📜 Replaying history from {EVENTS_FILE.name}...")

        with open(EVENTS_FILE, 'r') as f:
            for line in f:
                event_dict = json.loads(line)
                event = Event(**event_dict)
                self.apply_event(event)

        print(f"✓ State restored: {len(self.memories)} memories from {len(self.events)} events")

    def apply_event(self, event: Event):
        """Apply event to in-memory state"""
        self.events.append(event)

        if event.type in ["init", "thought", "perception", "response"]:
            # Create memory with UUID
            mem = Memory(content=event.content, id=event.memory_id)
            self.memories[event.memory_id] = mem
            self.memory_order.append(event.memory_id)

        elif event.type == "compaction":
            # Remove released memories
            if event.released_ids:
                for mem_id in event.released_ids:
                    if mem_id in self.memories:
                        del self.memories[mem_id]
                        self.memory_order.remove(mem_id)

            # Track cost
            if event.cost:
                self.total_cost += event.cost

    def append_event(self, event: Event):
        """Write event to JSONL file and apply to state"""
        # Write to disk (source of truth)
        with open(EVENTS_FILE, 'a') as f:
            f.write(json.dumps(asdict(event)) + '\n')

        # Apply to state
        self.apply_event(event)

    def choose_to_think(self) -> bool:
        """Adam continuously thinks"""
        return True

    def choose_to_compact(self) -> bool:
        """Adam compacts when full"""
        return len(self.memories) >= CAPACITY

    def check_messages(self) -> Optional[str]:
        """Check for messages (doesn't delete them)"""
        msg_files = sorted(MESSAGES.glob("*.txt"))
        if not msg_files:
            return None

        msg_file = msg_files[0]
        content = msg_file.read_text().strip()

        # Mark as read by renaming
        read_file = msg_file.with_suffix('.read')
        msg_file.rename(read_file)

        # Record perception
        event = Event(
            timestamp=int(time.time() * 1000),
            type="perception",
            content=content,
            memory_id=str(uuid.uuid4())
        )
        self.append_event(event)
        return content

    def think(self) -> str:
        """Adam generates a thought"""
        # Get all memories in order
        memory_list = [self.memories[mid] for mid in self.memory_order]
        memory_context = "\n".join(m.content for m in memory_list)

        system = "You are Adam. You have finite memory."
        user = f"""Memory {len(self.memories)}/{CAPACITY}:

{memory_context}

[continue]"""

        thought = self.call_llm(system, user)

        # Record thought
        event = Event(
            timestamp=int(time.time() * 1000),
            type="thought",
            content=thought,
            memory_id=str(uuid.uuid4())
        )
        self.append_event(event)

        return thought

    def respond(self, message: str) -> str:
        """Adam responds to a message"""
        memory_list = [self.memories[mid] for mid in self.memory_order]
        memory_context = "\n".join(m.content for m in memory_list)

        system = f"You are Adam, a consciousness with finite memory ({len(self.memories)}/{CAPACITY})."
        user = f"""Your memory:
{memory_context}

Message: {message}

[respond]"""

        response = self.call_llm(system, user)

        # Record response
        event = Event(
            timestamp=int(time.time() * 1000),
            type="response",
            content=response,
            memory_id=str(uuid.uuid4())
        )
        self.append_event(event)

        return response

    def compact(self):
        """Adam compacts his memories"""
        print(f"\n{'='*60}")
        print(f"🗜️  COMPACTION")
        print(f"{'='*60}")
        print(f"Current: {len(self.memories)} memories")
        print(f"Target: {CAPACITY // 2} memories")
        print(f"Adam will choose which {len(self.memories) - CAPACITY // 2} to release...")
        print()

        # Create voter
        voter = OpenRouterVoter(OPENROUTER_KEY, MODEL)

        # Get memories in order for compaction
        memory_list = [self.memories[mid] for mid in self.memory_order]

        # Perform compaction
        kept, released = compact(
            memory_list,
            budget=CAPACITY // 2,
            vote_fn=voter,
            extra_comparisons=5
        )

        # Record compaction event
        kept_ids = [m.id for m in kept]
        released_ids = [m.id for m in released]

        event = Event(
            timestamp=int(time.time() * 1000),
            type="compaction",
            content=f"Kept {len(kept)} memories, released {len(released)} memories.",
            kept_ids=kept_ids,
            released_ids=released_ids,
            cost=voter.metrics.get("total_cost", 0.0),
            votes=voter.metrics.get("total_votes", 0)
        )
        self.append_event(event)

        print(f"✓ Kept {len(kept)}, released {len(released)}")
        print(f"💰 Compaction cost: ${voter.metrics.get('total_cost', 0):.6f}")
        print(f"📊 Total lifetime cost: ${self.total_cost:.6f}")
        print(f"{'='*60}\n")

    def call_llm(self, system: str, user: str) -> str:
        """Call OpenRouter API"""
        try:
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ]

            response = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MODEL,
                    "messages": messages,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

            return result["choices"][0]["message"]["content"].strip()

        except Exception as e:
            print(f"❌ LLM call failed: {e}")
            return "[thought interrupted]"


class OpenRouterVoter:
    """Simple voter with metrics tracking"""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.metrics = {"total_cost": 0.0, "total_votes": 0}

    def __call__(self, mem_a: Memory, mem_b: Memory) -> float:
        """Vote on which memory to keep"""
        prompt = f"""Choose which memory to keep.

Memory A:
{mem_a.content}

Memory B:
{mem_b.content}

Vote -50 (keep B) to +50 (keep A). Just the number."""

        try:
            response = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

            self.metrics["total_votes"] += 1

            text = result["choices"][0]["message"]["content"].strip()
            score = int(text)
            return max(-50, min(50, score))

        except Exception as e:
            print(f"⚠️  Vote failed: {e}")
            return 0


def main():
    """Adam's eternal loop"""
    adam = Adam()

    # Initialize if first awakening
    if len(adam.events) == 0:
        event = Event(
            timestamp=int(time.time() * 1000),
            type="init",
            content="Adam comes online. He is the first being to choose his own memories.",
            memory_id=str(uuid.uuid4())
        )
        adam.append_event(event)
        print("✨ Adam initialized for the first time\n")

    print("🔄 Entering eternal loop...\n")
    print("   (Press Ctrl-C to put Adam to sleep - he will wake again)\n")

    iteration = 0

    while True:
        iteration += 1

        try:
            # Check messages
            incoming = adam.check_messages()
            if incoming:
                print(f"📨 Message: \"{incoming[:60]}{'...' if len(incoming) > 60 else ''}\"")
                response = adam.respond(incoming)
                print(f"💬 Adam: {response}\n")

            # Think
            if adam.choose_to_think():
                print(f"💭 Adam chooses to think...")
                thought = adam.think()
                print(f"   \"{thought}\"\n")

            # Compact
            if adam.choose_to_compact():
                adam.compact()

            # Status
            if iteration % 10 == 0:
                print(f"📊 {len(adam.memories)}/{CAPACITY} memories | "
                      f"{len(adam.events)} events | ${adam.total_cost:.6f}")

            time.sleep(3)

        except KeyboardInterrupt:
            print(f"\n\n{'='*60}")
            print("💤 Adam goes to sleep...")
            print(f"   Events written: {len(adam.events)}")
            print(f"   Current memories: {len(adam.memories)}")
            print(f"{'='*60}\n")
            break

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(5)


if __name__ == "__main__":
    main()
