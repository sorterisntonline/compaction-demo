"""Tests for rank centrality and ranking helpers."""

import numpy as np

from consensual_memory.rank import rank_centrality, rank_from_comparisons


class Dummy:
    def __init__(self, id):
        self.id = id


class TestRankCentrality:
    def test_two_items_clear_winner(self):
        """Matrix with clear preference should rank winner higher."""
        # A[j, i] encodes preference for i over j.
        A = np.array([[0.0, 0.1], [0.9, 0.0]])
        scores = rank_centrality(A)
        assert len(scores) == 2
        assert scores[0] > scores[1]
        assert abs(sum(scores) - 1.0) < 0.01

    def test_three_items_transitive(self):
        """Transitive comparisons should yield ordered scores."""
        A = np.zeros((3, 3))
        # 0 beats 1, 1 beats 2, 0 beats 2
        A[1, 0] = 0.8
        A[0, 1] = 0.2
        A[2, 1] = 0.7
        A[1, 2] = 0.3
        A[2, 0] = 0.9
        A[0, 2] = 0.1

        scores = rank_centrality(A)
        assert len(scores) == 3
        assert scores[0] > scores[1] > scores[2]
        assert abs(sum(scores) - 1.0) < 0.01


class TestRankFromComparisons:
    def test_orders_memories_by_scores(self):
        """Comparisons with strong preferences should sort accordingly."""
        a, b, c = Dummy("a"), Dummy("b"), Dummy("c")
        comparisons = [
            (a, b, 50),  # prefer a over b
            (a, c, 50),  # prefer a over c
            (b, c, 50),  # prefer b over c
        ]
        ranked = rank_from_comparisons([a, b, c], comparisons)
        assert [m.id for m in ranked] == ["a", "b", "c"]

    def test_single_memory_passthrough(self):
        """Single input should be returned unchanged."""
        solo = Dummy("only")
        ranked = rank_from_comparisons([solo], [])
        assert ranked == [solo]
