"""Integration tests for the full compaction pipeline."""

import random

import pytest

from consensual_memory import Memory, compact
from consensual_memory.llm import make_llm_voter


class TestEndToEndCompaction:
    def test_full_pipeline_with_mock_llm(self):
        """Test complete compaction pipeline with mock LLM."""

        # Mock LLM that prefers memories with "important" keyword
        def mock_llm(prompt):
            if "important" in prompt.lower():
                # Count occurrences in each memory section
                lines = prompt.split("\n")
                a_section = "\n".join(lines[lines.index("Memory A:") : lines.index("Memory B:")])
                b_section = "\n".join(lines[lines.index("Memory B:") :])

                a_count = a_section.lower().count("important")
                b_count = b_section.lower().count("important")

                if a_count > b_count:
                    return "35"
                elif b_count > a_count:
                    return "-35"
            return "0"

        voter = make_llm_voter(mock_llm)

        memories = [
            Memory("This is an important task about the deadline"),
            Memory("Random conversation about the weather"),
            Memory("Important meeting notes from yesterday"),
            Memory("Casual chat about movies"),
            Memory("Very important: project requirements"),
            Memory("Discussion about lunch options"),
        ]

        kept, released = compact(memories, budget=3, vote_fn=voter)

        # Should keep the 3 memories with "important" keyword
        kept_contents = [m.content for m in kept]
        assert len(kept) == 3
        assert all("important" in c.lower() for c in kept_contents)

        # Should release the 3 without "important"
        released_contents = [m.content for m in released]
        assert len(released) == 3
        assert all("important" not in c.lower() for c in released_contents)

    def test_stability_with_extra_comparisons(self):
        """Test that extra comparisons improve ranking stability."""
        random.seed(42)

        # Create memories with known preference order
        memories = [Memory(f"Memory with priority {i}", id=f"mem_{i}") for i in range(10)]

        def priority_voter(a: Memory, b: Memory) -> float:
            # Extract priority from content
            a_priority = int(a.content.split()[-1])
            b_priority = int(b.content.split()[-1])
            diff = a_priority - b_priority
            return max(-50, min(50, diff * 5))

        # Run multiple times with different random seeds
        results = []
        for seed in range(5):
            random.seed(seed)
            kept, _ = compact(memories, budget=5, vote_fn=priority_voter, extra_comparisons=10)
            kept_ids = sorted(m.id for m in kept)
            results.append(kept_ids)

        # All runs should keep the top 5 priorities (5-9)
        expected = sorted([f"mem_{i}" for i in range(5, 10)])
        for result in results:
            assert result == expected

    def test_gradual_compaction(self):
        """Test repeated compaction with decreasing budgets."""
        memories = [Memory(f"Memory about topic {i}", id=f"mem_{i}") for i in range(20)]

        def oracle_voter(a: Memory, b: Memory) -> float:
            idx_a = int(a.id.split("_")[1])
            idx_b = int(b.id.split("_")[1])
            diff = idx_a - idx_b
            return max(-50, min(50, diff * 5))

        # First compaction: 20 -> 15
        current_memories, _ = compact(memories, budget=15, vote_fn=oracle_voter)
        assert len(current_memories) == 15

        # Second compaction: 15 -> 10
        current_memories, _ = compact(current_memories, budget=10, vote_fn=oracle_voter)
        assert len(current_memories) == 10

        # Third compaction: 10 -> 5
        current_memories, _ = compact(current_memories, budget=5, vote_fn=oracle_voter)
        assert len(current_memories) == 5

        # Should end up with top 5 priorities
        kept_ids = {m.id for m in current_memories}
        expected = {f"mem_{i}" for i in range(15, 20)}
        assert kept_ids == expected

    def test_empty_and_edge_cases(self):
        """Test various edge cases."""
        voter = lambda a, b: 0

        # Empty list
        kept, released = compact([], budget=5, vote_fn=voter)
        assert kept == []
        assert released == []

        # Single memory
        mem = Memory("Only memory")
        kept, released = compact([mem], budget=1, vote_fn=voter)
        assert len(kept) == 1
        assert len(released) == 0

        # Budget of 0
        memories = [Memory(f"Mem {i}") for i in range(5)]
        kept, released = compact(memories, budget=0, vote_fn=voter)
        assert len(kept) == 0
        assert len(released) == 5

    def test_tie_breaking(self):
        """Test behavior when all votes are neutral."""
        memories = [Memory(f"Memory {i}", id=f"mem_{i}") for i in range(5)]

        # Neutral voter - all memories equal
        neutral_voter = lambda a, b: 0

        kept, released = compact(memories, budget=3, vote_fn=neutral_voter)

        # Should keep exactly 3 and release 2
        assert len(kept) == 3
        assert len(released) == 2

        # All original memories should be accounted for
        all_ids = {m.id for m in kept} | {m.id for m in released}
        original_ids = {m.id for m in memories}
        assert all_ids == original_ids

    def test_deterministic_with_fixed_seed(self):
        """Test that results are deterministic with fixed random seed."""
        memories = [Memory(f"Memory {i}", id=f"mem_{i}") for i in range(10)]

        def voter(a: Memory, b: Memory) -> float:
            idx_a = int(a.id.split("_")[1])
            idx_b = int(b.id.split("_")[1])
            return (idx_a - idx_b) * 5

        # Run twice with same seed
        random.seed(100)
        kept1, _ = compact(memories, budget=5, vote_fn=voter)

        random.seed(100)
        kept2, _ = compact(memories, budget=5, vote_fn=voter)

        # Results should be identical
        assert [m.id for m in kept1] == [m.id for m in kept2]
