"""Tests for rank centrality algorithm."""

import numpy as np
import pytest

from consensual_memory.rank import rank_centrality, tarjans_scc


class TestRankCentrality:
    def test_empty_matrix(self):
        """Test with empty matrix."""
        A = np.array([]).reshape(0, 0)
        scores = rank_centrality(A)
        assert len(scores) == 0

    def test_single_item(self):
        """Test with single item."""
        A = np.array([[0.0]])
        scores = rank_centrality(A)
        assert len(scores) == 1
        assert scores[0] == 1.0

    def test_two_items_clear_winner(self):
        """Test with two items, one clearly preferred."""
        # A[j,i] represents how much i is preferred to j
        # So A[1,0] = 0.9 means item 0 beats item 1 (0.9 to 0.1)
        A = np.array([[0.0, 0.1], [0.9, 0.0]])
        scores = rank_centrality(A)
        assert len(scores) == 2
        # Item 0 should be preferred (A[1,0] > A[0,1])
        assert scores[0] > scores[1]
        # Scores should sum to ~1
        assert abs(sum(scores) - 1.0) < 0.01

    def test_three_items_transitive(self):
        """Test with three items in transitive order: A > B > C."""
        # Set up: 0 beats 1, 1 beats 2, 0 beats 2
        A = np.zeros((3, 3))
        # 0 beats 1 (80/20)
        A[1, 0] = 0.8
        A[0, 1] = 0.2
        # 1 beats 2 (70/30)
        A[2, 1] = 0.7
        A[1, 2] = 0.3
        # 0 beats 2 (90/10)
        A[2, 0] = 0.9
        A[0, 2] = 0.1

        scores = rank_centrality(A)
        assert len(scores) == 3
        # Should get ranking: 0 > 1 > 2
        assert scores[0] > scores[1] > scores[2]
        # Scores should sum to ~1
        assert abs(sum(scores) - 1.0) < 0.01

    def test_symmetric_preferences(self):
        """Test with symmetric preferences (no clear winner)."""
        A = np.array([[0.0, 0.5, 0.5], [0.5, 0.0, 0.5], [0.5, 0.5, 0.0]])
        scores = rank_centrality(A)
        assert len(scores) == 3
        # All should be approximately equal
        assert abs(scores[0] - scores[1]) < 0.01
        assert abs(scores[1] - scores[2]) < 0.01
        assert abs(sum(scores) - 1.0) < 0.01

    def test_convergence(self):
        """Test that algorithm converges within tolerance."""
        # Create a larger random tournament
        n = 10
        np.random.seed(42)
        A = np.random.rand(n, n)
        # Make symmetric
        for i in range(n):
            for j in range(i + 1, n):
                total = A[i, j] + A[j, i]
                A[i, j] = A[i, j] / total if total > 0 else 0.5
                A[j, i] = 1 - A[i, j]
            A[i, i] = 0

        scores = rank_centrality(A, tol=1e-8)
        assert len(scores) == n
        assert abs(sum(scores) - 1.0) < 0.01
        # All scores should be positive
        assert all(s > 0 for s in scores)

    def test_sparse_comparisons(self):
        """Test with sparse comparison matrix (not all pairs compared)."""
        # Create spanning tree: 0-1, 1-2, 2-3
        A = np.zeros((4, 4))
        A[1, 0] = 0.8
        A[0, 1] = 0.2
        A[2, 1] = 0.7
        A[1, 2] = 0.3
        A[3, 2] = 0.6
        A[2, 3] = 0.4

        scores = rank_centrality(A)
        assert len(scores) == 4
        # Should still produce valid ranking
        assert scores[0] > scores[1] > scores[2] > scores[3]
        assert abs(sum(scores) - 1.0) < 0.01


class TestTarjansSCC:
    def test_empty_graph(self):
        """Test with empty graph."""
        A = np.array([]).reshape(0, 0)
        sccs = tarjans_scc(A)
        assert len(sccs) == 0

    def test_single_node(self):
        """Test with single node."""
        A = np.array([[0.0]])
        sccs = tarjans_scc(A)
        assert len(sccs) == 1
        assert sccs[0] == [0]

    def test_disconnected_nodes(self):
        """Test with disconnected nodes."""
        A = np.zeros((3, 3))
        sccs = tarjans_scc(A)
        assert len(sccs) == 3
        # Each node is its own component
        all_nodes = set()
        for scc in sccs:
            assert len(scc) == 1
            all_nodes.update(scc)
        assert all_nodes == {0, 1, 2}

    def test_fully_connected(self):
        """Test with fully connected graph."""
        A = np.ones((3, 3))
        sccs = tarjans_scc(A)
        assert len(sccs) == 1
        assert set(sccs[0]) == {0, 1, 2}

    def test_two_components(self):
        """Test with two separate components."""
        A = np.zeros((4, 4))
        # Component 1: 0 <-> 1
        A[0, 1] = 1
        A[1, 0] = 1
        # Component 2: 2 <-> 3
        A[2, 3] = 1
        A[3, 2] = 1

        sccs = tarjans_scc(A)
        assert len(sccs) == 2
        # Check that we have the right components
        component_sets = [set(scc) for scc in sccs]
        assert {0, 1} in component_sets
        assert {2, 3} in component_sets

    def test_chain(self):
        """Test with chain: 0 -> 1 -> 2 -> 3."""
        A = np.zeros((4, 4))
        A[0, 1] = 1
        A[1, 2] = 1
        A[2, 3] = 1

        sccs = tarjans_scc(A)
        # Each node is its own component in a DAG
        assert len(sccs) == 4
        for scc in sccs:
            assert len(scc) == 1

    def test_cycle(self):
        """Test with cycle: 0 -> 1 -> 2 -> 0."""
        A = np.zeros((3, 3))
        A[0, 1] = 1
        A[1, 2] = 1
        A[2, 0] = 1

        sccs = tarjans_scc(A)
        # All nodes in one component
        assert len(sccs) == 1
        assert set(sccs[0]) == {0, 1, 2}

    def test_complex_graph(self):
        """Test with more complex graph structure."""
        # 0 -> 1 <-> 2, 3 -> 1
        # Should have: {0}, {1, 2}, {3}
        A = np.zeros((4, 4))
        A[0, 1] = 1
        A[1, 2] = 1
        A[2, 1] = 1
        A[3, 1] = 1

        sccs = tarjans_scc(A)
        component_sets = [set(scc) for scc in sccs]

        # Find the components
        has_12 = any({1, 2} == cs for cs in component_sets)
        has_0 = any({0} == cs for cs in component_sets)
        has_3 = any({3} == cs for cs in component_sets)

        assert has_12, "Should have component {1, 2}"
        assert has_0, "Should have component {0}"
        assert has_3, "Should have component {3}"
