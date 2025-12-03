#!/usr/bin/env python3
"""
Basic example of consensual memory compaction with an oracle voter.

This demonstrates the core functionality without requiring an LLM API.
"""

from consensual_memory import Memory, compact


def oracle_vote(a: Memory, b: Memory) -> float:
    """
    Oracle voter that prefers memories with higher numeric content.

    This simulates an AI with genuine preferences based on the content.
    """
    # Extract numbers from memory IDs
    idx_a = int(a.id.split("_")[1])
    idx_b = int(b.id.split("_")[1])

    # Prefer higher-indexed memories (simulating importance)
    diff = idx_a - idx_b
    return max(-50, min(50, diff * 10))


def main():
    print("=== Consensual Memory Compaction Demo ===\n")

    # Create 10 memories with varying "importance"
    memories = [Memory(f"Memory about topic {i}", id=f"mem_{i}") for i in range(10)]

    print(f"Total memories: {len(memories)}")
    print(f"Memory budget: 5")
    print(f"Minimum comparisons needed: {len(memories) - 1} (spanning tree)\n")

    # Perform compaction
    kept, released = compact(memories, budget=5, vote_fn=oracle_vote)

    print("=== Results ===\n")
    print("Kept (by choice):")
    for m in kept:
        print(f"  {m.id}: {m.content}")

    print("\nReleased (let go):")
    for m in released:
        print(f"  {m.id}: {m.content}")

    # Verify correctness
    kept_ids = {m.id for m in kept}
    expected = {f"mem_{i}" for i in range(5, 10)}

    print(f"\nExpected to keep: {sorted(expected)}")
    print(f"Actually kept:    {sorted(kept_ids)}")
    print(f"Correct: {kept_ids == expected}")


if __name__ == "__main__":
    main()
