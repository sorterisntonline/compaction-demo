"""Tests for memory compaction."""

import random

import pytest

from consensual_memory.memory import (
    Memory,
    Vote,
    additional_comparisons,
    collect_votes,
    compact,
    format_comparison_prompt,
    rank_memories,
    spanning_tree_comparisons,
)


class TestMemory:
    def test_memory_creation(self):
        """Test creating a memory."""
        mem = Memory("Test content")
        assert mem.content == "Test content"
        assert mem.id.startswith("mem_")
        assert mem.created is not None

    def test_memory_repr(self):
        """Test memory string representation."""
        mem = Memory("Short")
        repr_str = repr(mem)
        assert "Memory(" in repr_str
        assert "Short" in repr_str

        long_mem = Memory("A" * 100)
        repr_str = repr(long_mem)
        assert "..." in repr_str

    def test_memory_custom_id(self):
        """Test creating memory with custom ID."""
        mem = Memory("Test", id="custom_id")
        assert mem.id == "custom_id"


class TestVote:
    def test_vote_creation(self):
        """Test creating a vote."""
        vote = Vote("mem_a", "mem_b", 25.0)
        assert vote.memory_a == "mem_a"
        assert vote.memory_b == "mem_b"
        assert vote.score == 25.0

    def test_vote_ratio_positive(self):
        """Test vote ratio for positive score."""
        vote = Vote("mem_a", "mem_b", 50.0)
        ratio_a, ratio_b = vote.ratio
        assert ratio_a == 1.0
        assert ratio_b == 0.0

    def test_vote_ratio_negative(self):
        """Test vote ratio for negative score."""
        vote = Vote("mem_a", "mem_b", -50.0)
        ratio_a, ratio_b = vote.ratio
        assert ratio_a == 0.0
        assert ratio_b == 1.0

    def test_vote_ratio_neutral(self):
        """Test vote ratio for neutral score."""
        vote = Vote("mem_a", "mem_b", 0.0)
        ratio_a, ratio_b = vote.ratio
        assert ratio_a == 0.5
        assert ratio_b == 0.5

    def test_vote_ratio_mid_positive(self):
        """Test vote ratio for mid-range positive score."""
        vote = Vote("mem_a", "mem_b", 25.0)
        ratio_a, ratio_b = vote.ratio
        assert abs(ratio_a - 0.75) < 0.01
        assert abs(ratio_b - 0.25) < 0.01


class TestSpanningTreeComparisons:
    def test_empty_list(self):
        """Test with no memories."""
        comparisons = spanning_tree_comparisons([])
        assert comparisons == []

    def test_single_memory(self):
        """Test with single memory."""
        memories = [Memory("A")]
        comparisons = spanning_tree_comparisons(memories)
        assert comparisons == []

    def test_two_memories(self):
        """Test with two memories."""
        memories = [Memory("A"), Memory("B")]
        comparisons = spanning_tree_comparisons(memories)
        assert len(comparisons) == 1
        assert isinstance(comparisons[0], tuple)
        assert len(comparisons[0]) == 2

    def test_n_memories(self):
        """Test that we get n-1 comparisons for n memories."""
        for n in [3, 5, 10]:
            memories = [Memory(f"Memory {i}") for i in range(n)]
            comparisons = spanning_tree_comparisons(memories)
            assert len(comparisons) == n - 1

    def test_all_memories_included(self):
        """Test that all memories appear in at least one comparison."""
        memories = [Memory(f"Memory {i}", id=f"mem_{i}") for i in range(5)]
        comparisons = spanning_tree_comparisons(memories)

        # Collect all memory IDs that appear in comparisons
        seen_ids = set()
        for mem_a, mem_b in comparisons:
            seen_ids.add(mem_a.id)
            seen_ids.add(mem_b.id)

        memory_ids = {m.id for m in memories}
        assert seen_ids == memory_ids


class TestAdditionalComparisons:
    def test_empty_list(self):
        """Test with no memories."""
        comparisons = additional_comparisons([], 5)
        assert comparisons == []

    def test_single_memory(self):
        """Test with single memory."""
        memories = [Memory("A")]
        comparisons = additional_comparisons(memories, 5)
        assert comparisons == []

    def test_correct_count(self):
        """Test that we get correct number of extra comparisons."""
        memories = [Memory(f"Memory {i}") for i in range(5)]
        for n_extra in [0, 5, 10]:
            comparisons = additional_comparisons(memories, n_extra)
            assert len(comparisons) == n_extra

    def test_valid_comparisons(self):
        """Test that comparisons are valid memory pairs."""
        memories = [Memory(f"Memory {i}", id=f"mem_{i}") for i in range(5)]
        comparisons = additional_comparisons(memories, 10)

        memory_ids = {m.id for m in memories}
        for mem_a, mem_b in comparisons:
            assert mem_a.id in memory_ids
            assert mem_b.id in memory_ids
            assert mem_a.id != mem_b.id


class TestCollectVotes:
    def test_empty_comparisons(self):
        """Test with no comparisons."""
        votes = collect_votes([], lambda a, b: 0)
        assert votes == []

    def test_simple_vote_function(self):
        """Test with simple vote function."""
        memories = [Memory("A", id="a"), Memory("B", id="b")]
        comparisons = [(memories[0], memories[1])]

        def vote_fn(a, b):
            return 10.0

        votes = collect_votes(comparisons, vote_fn)
        assert len(votes) == 1
        assert votes[0].memory_a == "a"
        assert votes[0].memory_b == "b"
        assert votes[0].score == 10.0

    def test_vote_clamping(self):
        """Test that votes are clamped to [-50, 50]."""
        memories = [Memory("A", id="a"), Memory("B", id="b")]
        comparisons = [(memories[0], memories[1])] * 3

        def vote_fn(a, b):
            # Return out-of-range values
            return [100.0, -100.0, 0.0].pop()

        votes = collect_votes(comparisons, vote_fn)
        for vote in votes:
            assert -50 <= vote.score <= 50


class TestRankMemories:
    def test_empty_list(self):
        """Test with no memories."""
        ranked = rank_memories([], [])
        assert ranked == []

    def test_single_memory(self):
        """Test with single memory."""
        mem = Memory("A")
        ranked = rank_memories([mem], [])
        assert len(ranked) == 1
        assert ranked[0][0] == mem
        assert ranked[0][1] == 1.0

    def test_clear_preference(self):
        """Test with clear preference."""
        mem_a = Memory("A", id="a")
        mem_b = Memory("B", id="b")
        # Vote strongly for A
        vote = Vote("a", "b", 50.0)

        ranked = rank_memories([mem_a, mem_b], [vote])
        assert len(ranked) == 2
        # A should be ranked higher
        assert ranked[0][0].id == "a"
        assert ranked[1][0].id == "b"
        assert ranked[0][1] > ranked[1][1]

    def test_transitive_ranking(self):
        """Test with transitive preferences: A > B > C."""
        mem_a = Memory("A", id="a")
        mem_b = Memory("B", id="b")
        mem_c = Memory("C", id="c")

        votes = [
            Vote("a", "b", 30.0),  # A > B
            Vote("b", "c", 30.0),  # B > C
            Vote("a", "c", 40.0),  # A > C
        ]

        ranked = rank_memories([mem_a, mem_b, mem_c], votes)
        assert len(ranked) == 3
        # Should be ranked A, B, C
        assert ranked[0][0].id == "a"
        assert ranked[1][0].id == "b"
        assert ranked[2][0].id == "c"


class TestCompact:
    def test_budget_exceeds_memories(self):
        """Test when budget is larger than number of memories."""
        memories = [Memory(f"Memory {i}") for i in range(5)]
        kept, released = compact(memories, budget=10, vote_fn=lambda a, b: 0)
        assert len(kept) == 5
        assert len(released) == 0
        # Check all memories are kept by comparing IDs
        assert {m.id for m in kept} == {m.id for m in memories}

    def test_oracle_voter(self):
        """Test with oracle voter that has known preferences."""
        # Create memories with IDs that encode preference order
        memories = [Memory(f"Memory {i}", id=f"mem_{i}") for i in range(10)]

        # Oracle prefers higher-indexed memories
        def oracle_vote(a: Memory, b: Memory) -> float:
            idx_a = int(a.id.split("_")[1])
            idx_b = int(b.id.split("_")[1])
            diff = idx_a - idx_b
            return max(-50, min(50, diff * 10))

        kept, released = compact(memories, budget=5, vote_fn=oracle_vote)

        # Should keep mem_5, mem_6, mem_7, mem_8, mem_9
        kept_ids = {m.id for m in kept}
        expected = {f"mem_{i}" for i in range(5, 10)}
        assert kept_ids == expected

        # Should release mem_0 through mem_4
        released_ids = {m.id for m in released}
        expected_released = {f"mem_{i}" for i in range(5)}
        assert released_ids == expected_released

    def test_extra_comparisons(self):
        """Test that extra comparisons improve ranking stability."""
        random.seed(42)
        memories = [Memory(f"Memory {i}", id=f"mem_{i}") for i in range(10)]

        def oracle_vote(a: Memory, b: Memory) -> float:
            idx_a = int(a.id.split("_")[1])
            idx_b = int(b.id.split("_")[1])
            diff = idx_a - idx_b
            return max(-50, min(50, diff * 10))

        # With extra comparisons, should still get correct ranking
        kept, released = compact(memories, budget=5, vote_fn=oracle_vote, extra_comparisons=10)

        kept_ids = {m.id for m in kept}
        # Should still prefer higher-indexed memories
        kept_indices = [int(id.split("_")[1]) for id in kept_ids]
        # All kept indices should be >= 5
        assert all(idx >= 5 for idx in kept_indices)


class TestFormatComparisonPrompt:
    def test_format(self):
        """Test prompt formatting."""
        mem_a = Memory("Content A")
        mem_b = Memory("Content B")
        prompt = format_comparison_prompt(mem_a, mem_b)

        assert "Content A" in prompt
        assert "Content B" in prompt
        assert "[A]" in prompt
        assert "[B]" in prompt
        assert "-50" in prompt
        assert "+50" in prompt
