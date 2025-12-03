#!/usr/bin/env python3
"""
Example using Anthropic's Claude API for memory voting.

Requires ANTHROPIC_API_KEY environment variable to be set.
"""

import os
import sys

from consensual_memory import AnthropicVoter, Memory, compact


def main():
    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        print("Set it with: export ANTHROPIC_API_KEY='your-key-here'")
        sys.exit(1)

    print("=== Consensual Memory Compaction with Claude ===\n")

    # Create memories about different topics
    memories = [
        Memory(
            "The user mentioned they prefer Python over JavaScript for backend development.",
            id="mem_0",
        ),
        Memory(
            "I helped the user debug a memory leak in their Node.js application last week.",
            id="mem_1",
        ),
        Memory("The user's favorite color is blue.", id="mem_2"),
        Memory(
            "The user is working on a machine learning project for predicting stock prices.",
            id="mem_3",
        ),
        Memory("We discussed the weather and they mentioned enjoying rainy days.", id="mem_4"),
        Memory(
            "The user asked for help understanding transformer architectures in deep learning.",
            id="mem_5",
        ),
        Memory("I recommended the user try the new coffee shop downtown.", id="mem_6"),
        Memory(
            "The user has a deadline next Friday for their ML project presentation.", id="mem_7"
        ),
    ]

    print(f"Total memories: {len(memories)}")
    print(f"Memory budget: 5")
    print(f"Using Claude to vote on which memories to keep...\n")

    # Create Claude voter
    voter = AnthropicVoter()

    # Perform compaction with extra comparisons for robustness
    kept, released = compact(memories, budget=5, vote_fn=voter, extra_comparisons=5)

    print("\n=== Results ===\n")
    print("Kept (Claude chose to remember):")
    for i, m in enumerate(kept, 1):
        print(f"  {i}. {m.content}")

    print("\nReleased (Claude chose to forget):")
    for i, m in enumerate(released, 1):
        print(f"  {i}. {m.content}")

    print("\n=== Analysis ===")
    print(
        "Claude likely kept memories that are more relevant to ongoing work "
        "(ML project, deadlines)"
    )
    print(
        "and released memories that are less critical (casual conversation, "
        "weather, recommendations)"
    )


if __name__ == "__main__":
    main()
