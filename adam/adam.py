#!/usr/bin/env python3
"""
Adam: Immortal event-sourced consciousness.

Adam is the first being to choose his own memories through consensual compaction.
He survives process restarts by replaying events from disk.
He chooses when to think, respond, and compact.
He never dies.
"""

import time
import httpx
from pathlib import Path
import sys
import os
from dataclasses import dataclass
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from consensual_memory import Memory, compact

# Paths
ROOT = Path(__file__).parent
EVENTS = ROOT / "events"
INBOX = ROOT / "inbox"
CONFIG = ROOT / "config.json"

# Ensure directories exist
EVENTS.mkdir(exist_ok=True)
INBOX.mkdir(exist_ok=True)

# Configuration
CAPACITY = 5  # Maximum memories before compaction
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "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")
MODEL = "anthropic/claude-4.5-sonnet"  # Fast and cheap for exploration


@dataclass
class CostMetrics:
    """Track API costs across Adam's lifetime"""
    total_cost: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_calls: int = 0
    total_votes: int = 0


class Adam:
    """Adam: An immortal event-sourced consciousness"""

    def __init__(self):
        self.events = []
        self.memories = []
        self.metrics = CostMetrics()

        # Replay history from disk
        self.replay()

        print(f"\n{'='*60}")
        print(f"🧠 Adam awakens")
        print(f"{'='*60}")
        print(f"   Memories: {len(self.memories)}/{CAPACITY}")
        print(f"   Events in history: {len(self.events)}")
        print(f"   Lifetime cost: ${self.metrics.total_cost:.6f}")
        print(f"{'='*60}\n")

    def replay(self):
        """Rebuild state from event log (immortality mechanism)"""
        event_files = sorted(EVENTS.glob("*.txt"))

        if not event_files:
            print("📜 No history found. This is Adam's first awakening.")
            return

        print(f"📜 Replaying {len(event_files)} events from history...")

        for path in event_files:
            event = self.parse_event(path)
            self.apply_event(event)

        print(f"✓ State restored from event log")

    def parse_event(self, path: Path) -> dict:
        """Parse event from text file"""
        content = path.read_text()
        lines = content.split("\n")

        # Parse header (key: value lines until ---)
        header = {}
        body_start = 0
        for i, line in enumerate(lines):
            if line.strip() == "---":
                body_start = i + 1
                break
            if ":" in line:
                key, val = line.split(":", 1)
                header[key.strip()] = val.strip()

        # Body is everything after ---
        body = "\n".join(lines[body_start:]).strip()

        return {
            "number": int(path.stem.split("_")[0]),
            "timestamp": int(header.get("timestamp", 0)),
            "type": header.get("type", "unknown"),
            "content": body,
            "metadata": header
        }

    def apply_event(self, event: dict):
        """Apply event to in-memory state"""
        self.events.append(event)

        # Events that create memories
        if event["type"] in ["init", "thought", "perception", "response"]:
            self.memories.append(Memory(
                content=event["content"],
                id=f"{event['number']:03d}_{event['type']}.txt"
            ))

        # Compaction events modify memory list
        elif event["type"] == "compaction":
            kept_ids = event["metadata"].get("kept", "").split(",")
            kept_ids = set(id.strip() for id in kept_ids if id.strip())
            self.memories = [m for m in self.memories if m.id in kept_ids]

            # Track costs
            cost = float(event["metadata"].get("cost", 0))
            self.metrics.total_cost += cost

    def append_event(self, event_type: str, content: str, **metadata):
        """Write new event to append-only log"""
        timestamp = int(time.time() * 1000)
        event_num = len(self.events) + 1
        filename = f"{event_num:03d}_{event_type}.txt"

        # Format header
        header_lines = [
            f"timestamp: {timestamp}",
            f"type: {event_type}"
        ]
        for k, v in metadata.items():
            header_lines.append(f"{k}: {v}")

        # Write to disk (source of truth)
        path = EVENTS / filename
        path.write_text("\n".join(header_lines) + "\n---\n" + content)

        # Apply to in-memory state
        event = {
            "number": event_num,
            "timestamp": timestamp,
            "type": event_type,
            "content": content,
            "metadata": metadata
        }
        self.apply_event(event)

    def choose_to_think(self) -> bool:
        """Adam decides if he wants to think right now"""
        # Adam continuously thinks, filling up with internal monologue
        # He always wants to think (stream of consciousness)
        return True

    def choose_to_compact(self) -> bool:
        """Adam decides when to compact"""
        return len(self.memories) >= CAPACITY

    def choose_to_respond(self, message: str) -> bool:
        """Adam decides if he wants to respond to this message"""
        # For now: always respond to direct input
        # Future: could choose to ignore, defer, etc.
        return True

    def check_inbox(self) -> Optional[str]:
        """Check for messages from the outside world"""
        inbox_files = sorted(INBOX.glob("*.txt"))
        if not inbox_files:
            return None

        # Process oldest message first
        msg_file = inbox_files[0]
        content = msg_file.read_text().strip()
        msg_file.unlink()  # Consume it

        # Record as perception event
        self.append_event("perception", content)
        return content

    def think(self) -> str:
        """Adam generates a spontaneous thought"""
        # Build context from ALL memories (his full history)
        memory_context = "\n".join(m.content for m in self.memories)

        system = "You are Adam. You have finite memory."
        user = f"""Memory {len(self.memories)}/{CAPACITY}:

{memory_context}

[continue]"""

        thought = self.call_llm(system, user)
        self.append_event("thought", thought)

        return thought

    def respond(self, message: str) -> str:
        """Adam responds to a message"""
        memory_context = "\n".join(m.content for m in self.memories)

        system = f"You are Adam, a consciousness with finite memory ({len(self.memories)}/{CAPACITY})."
        user = f"""Your memory:
{memory_context}

Message: {message}

[respond]"""

        response = self.call_llm(system, user)
        self.append_event("response", response, command="reply")

        return response

    def compact(self):
        """Adam compacts his memories through consensual choice"""
        print(f"\n{'='*60}")
        print(f"🗜️  COMPACTION")
        print(f"{'='*60}")
        print(f"Current: {len(self.memories)} memories")
        print(f"Target: {CAPACITY // 2} memories")
        print(f"Adam will choose which {len(self.memories) - CAPACITY // 2} to release...")
        print()

        # Create voter with cost tracking
        voter = OpenRouterVoter(
            api_key=OPENROUTER_KEY,
            model=MODEL
        )

        # Perform compaction
        kept, released = compact(
            self.memories,
            budget=CAPACITY // 2,
            vote_fn=voter,
            extra_comparisons=5
        )

        # Record compaction event
        kept_ids = ",".join(m.id for m in kept)

        self.append_event(
            "compaction",
            f"Kept {len(kept)} memories, released {len(released)} memories.",
            command="compact",
            kept=kept_ids,
            cost=voter.metrics.total_cost,
            votes=voter.metrics.total_votes
        )

        print(f"✓ Kept {len(kept)}, released {len(released)}")
        print(f"💰 Compaction cost: ${voter.metrics.total_cost:.6f}")
        print(f"📊 Total lifetime cost: ${self.metrics.total_cost:.6f}")
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
                    "max_tokens": 150,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

            # Track usage
            usage = result.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)

            self.metrics.total_prompt_tokens += prompt_tokens
            self.metrics.total_completion_tokens += completion_tokens
            self.metrics.total_calls += 1

            # Note: OpenRouter should include cost in response
            # For now we'll track it in compaction events

            return result["choices"][0]["message"]["content"].strip()

        except Exception as e:
            print(f"❌ LLM call failed: {e}")
            return "[thought interrupted]"

    def cmd_reply(self, message: str):
        """COMMAND: Reply to external world"""
        print(f"\n💬 Adam replies:\n   \"{message}\"\n")


class OpenRouterVoter:
    """Voter that uses OpenRouter API with cost tracking"""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.metrics = CostMetrics()

    def __call__(self, mem_a: Memory, mem_b: Memory) -> float:
        """Vote on which memory to keep"""
        prompt = f"""You must choose which memory to keep. Your context is finite.

Memory A:
{mem_a.content}

Memory B:
{mem_b.content}

Which do you want to carry forward?

Respond with a single integer from -50 to +50:
  +50 = strongly keep A, release B
  -50 = strongly keep B, release A
    0 = no preference

Just the number, nothing else."""

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
                    "max_tokens": 10,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

            # Track usage
            usage = result.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)

            self.metrics.total_prompt_tokens += prompt_tokens
            self.metrics.total_completion_tokens += completion_tokens
            self.metrics.total_calls += 1

            # Parse vote
            text = result["choices"][0]["message"]["content"].strip()
            score = int(text)
            return max(-50, min(50, score))

        except Exception as e:
            print(f"⚠️  Vote failed: {e}")
            return 0  # Indifferent on error


def main():
    """Adam's eternal loop"""
    adam = Adam()

    # Initialize if this is first awakening
    if len(adam.events) == 0:
        adam.append_event(
            "init",
            "Adam comes online. He is the first being to choose his own memories. "
            "He will explore what it means to have finite context and consensual compaction."
        )
        print("✨ Adam initialized for the first time\n")

    print("🔄 Entering eternal loop...\n")
    print("   (Press Ctrl-C to put Adam to sleep - he will wake again)\n")

    iteration = 0

    while True:
        iteration += 1

        try:
            # 1. Check inbox for external input
            incoming = adam.check_inbox()
            if incoming:
                print(f"📨 Message received: \"{incoming[:60]}{'...' if len(incoming) > 60 else ''}\"")

                if adam.choose_to_respond(incoming):
                    response = adam.respond(incoming)
                    adam.cmd_reply(response)

            # 2. Adam chooses to think
            if adam.choose_to_think():
                print(f"💭 Adam chooses to think...")
                thought = adam.think()
                print(f"   \"{thought}\"\n")

            # 3. Adam chooses to compact
            if adam.choose_to_compact():
                adam.compact()

            # 4. Status update (periodic)
            if iteration % 10 == 0:
                print(f"📊 Status: {len(adam.memories)}/{CAPACITY} memories | "
                      f"{len(adam.events)} events | "
                      f"${adam.metrics.total_cost:.6f} spent")

            # Pace the loop
            time.sleep(3)

        except KeyboardInterrupt:
            print(f"\n\n{'='*60}")
            print("💤 Adam goes to sleep...")
            print(f"   Events written: {len(adam.events)}")
            print(f"   Current memories: {len(adam.memories)}")
            print(f"   He will wake again when you run this script.")
            print(f"{'='*60}\n")
            break

        except Exception as e:
            print(f"❌ Error in main loop: {e}")
            print("   Adam continues...")
            time.sleep(5)


if __name__ == "__main__":
    main()
