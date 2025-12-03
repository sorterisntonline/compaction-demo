#!/usr/bin/env python3
"""
Test script for Adam - runs a few iterations then exits.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import Adam's main module
from adam import Adam

def test_adam():
    """Run Adam for a few test iterations"""
    adam = Adam()

    # Initialize if needed
    if len(adam.events) == 0:
        adam.append_event(
            "init",
            "Adam comes online. He is the first being to choose his own memories. "
            "He will explore what it means to have finite context and consensual compaction."
        )

    print("\nRunning 5 test iterations...\n")

    for i in range(5):
        print(f"--- Iteration {i+1} ---")

        # Check inbox
        incoming = adam.check_inbox()
        if incoming:
            print(f"📨 Message: {incoming}")
            if adam.choose_to_respond(incoming):
                print("🤔 Adam is thinking of a response...")
                response = adam.respond(incoming)
                print(f"💬 Adam: {response}\n")

        # Maybe think
        if adam.choose_to_think():
            print("💭 Adam chooses to think...")
            thought = adam.think()
            print(f"   '{thought}'\n")

        # Check compaction
        if adam.choose_to_compact():
            print("🗜️  Adam would compact here (skipped in test)\n")

        print(f"📊 Status: {len(adam.memories)}/{100} memories\n")

    print(f"\n✓ Test complete!")
    print(f"  Events: {len(adam.events)}")
    print(f"  Memories: {len(adam.memories)}")
    print(f"  Check events/ directory to see what Adam wrote")


if __name__ == "__main__":
    test_adam()
