#!/usr/bin/env python3
"""
Example showing how to create a custom voting function.

This demonstrates building a voter based on keyword matching and recency.
"""

from datetime import datetime, timedelta

from consensual_memory import Memory, compact


def keyword_recency_voter(keywords: list[str], recency_weight: float = 0.5):
    """
    Create a voter that prefers memories containing keywords and recent memories.

    Args:
        keywords: List of important keywords to look for
        recency_weight: Weight given to recency (0-1), vs keyword matching
    """

    def vote(a: Memory, b: Memory) -> float:
        # Count keyword matches
        keywords_lower = [k.lower() for k in keywords]
        a_matches = sum(1 for kw in keywords_lower if kw in a.content.lower())
        b_matches = sum(1 for kw in keywords_lower if kw in b.content.lower())

        # Calculate recency score (more recent = higher score)
        now = datetime.now()
        a_age_hours = (now - a.created).total_seconds() / 3600
        b_age_hours = (now - b.created).total_seconds() / 3600

        # Normalize to 0-1 (assuming memories are within 24 hours)
        a_recency = max(0, 1 - a_age_hours / 24)
        b_recency = max(0, 1 - b_age_hours / 24)

        # Normalize keyword score to 0-1
        max_matches = max(a_matches, b_matches, 1)
        a_kw_score = a_matches / max_matches
        b_kw_score = b_matches / max_matches

        # Combine scores
        a_score = recency_weight * a_recency + (1 - recency_weight) * a_kw_score
        b_score = recency_weight * b_recency + (1 - recency_weight) * b_kw_score

        # Convert to -50 to +50 scale
        diff = a_score - b_score
        return max(-50, min(50, diff * 100))

    return vote


def main():
    print("=== Custom Voter Example ===\n")

    # Create memories at different times with different content
    base_time = datetime.now() - timedelta(hours=12)

    memories = [
        Memory(
            "Discussed machine learning algorithms for classification",
            id="mem_0",
        ),
        Memory("Had a conversation about cooking recipes", id="mem_1"),
        Memory("Analyzed neural network architectures for the project", id="mem_2"),
        Memory("Talked about weekend plans and movies", id="mem_3"),
        Memory("Debugged the training loop in the ML pipeline", id="mem_4"),
        Memory("Discussed favorite books and authors", id="mem_5"),
        Memory("Reviewed the latest research papers on transformers", id="mem_6"),
        Memory("Planned a trip to the mountains", id="mem_7"),
    ]

    # Set different creation times
    for i, mem in enumerate(memories):
        mem.created = base_time + timedelta(hours=i)

    # Create voter that prioritizes ML-related keywords
    keywords = ["machine learning", "neural", "training", "ML", "research", "transformers"]
    voter = keyword_recency_voter(keywords, recency_weight=0.3)

    print(f"Total memories: {len(memories)}")
    print(f"Memory budget: 4")
    print(f"Priority keywords: {keywords}")
    print(f"Recency weight: 30%, Keyword weight: 70%\n")

    # Perform compaction
    kept, released = compact(memories, budget=4, vote_fn=voter, extra_comparisons=3)

    print("=== Results ===\n")
    print("Kept:")
    for i, m in enumerate(kept, 1):
        age = (datetime.now() - m.created).total_seconds() / 3600
        print(f"  {i}. [{m.id}] {m.content[:60]}... (age: {age:.1f}h)")

    print("\nReleased:")
    for i, m in enumerate(released, 1):
        age = (datetime.now() - m.created).total_seconds() / 3600
        print(f"  {i}. [{m.id}] {m.content[:60]}... (age: {age:.1f}h)")

    print("\n=== Analysis ===")
    print("The voter prioritized memories about machine learning and neural networks")
    print("while releasing memories about casual topics like cooking, movies, and trips.")


if __name__ == "__main__":
    main()
