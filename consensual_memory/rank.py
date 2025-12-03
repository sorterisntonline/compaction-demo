#!/usr/bin/env python3
"""
Rank Centrality algorithm for computing global rankings from pairwise comparisons.
"""

import itertools
from typing import Dict, List, Set

import numpy as np
import scipy.sparse


def rank_centrality(A: np.ndarray, tol: float = 1e-8, max_iters: int = 100000) -> np.ndarray:
    """
    Compute global ranking from pairwise comparison matrix.

    The argument "A" is an n x n matrix such that A[i,j] / (A[i,j] + A[j,i]) represents
    the probability that item j is preferred to item i. For example in a tournament,
    A[i,j] could be the number of times that player j beat player i.

    The matrix may be sparse (i.e. some (i,j) pairs may have no comparisons) but the
    graph induced by non-zero arcs must be fully connected.

    Args:
        A: n x n comparison matrix
        tol: iteration stops when sum(abs(scores - prev_scores)) < tol
        max_iters: maximum number of iterations

    Returns:
        Vector of scores of length n, summing to ~1, where higher is more preferred.
    """
    n = A.shape[0]
    if n == 0:
        return np.array([])
    if n == 1:
        return np.array([1.0])

    # Compute normalized matrix W such that probabilities for each (i,j) pair sum to 1
    W = np.zeros((n, n))
    for i, j in itertools.product(range(n), range(n)):
        if A[i, j] > 0 or A[j, i] > 0:
            W[i, j] = A[i, j] / (A[i, j] + A[j, i])

    # Compute maximum sum of any row of W excluding diagonal
    w_max = max(sum(W[i, j] for j in range(n) if j != i) for i in range(n))
    if w_max == 0:
        return np.ones(n) / n

    # Build transition matrix P where rows sum to 1
    P = W / w_max
    for i in range(n):
        P[i, i] = 1 - sum(P[i, k] for k in range(n) if k != i)

    # Use sparse representation for large matrices
    if n >= 250:
        P = scipy.sparse.csr_array(P)

    # Find stationary distribution via power iteration
    scores = np.ones(n) / n
    for _ in range(max_iters):
        prev = scores
        scores = prev @ P
        if np.sum(np.abs(scores - prev)) < tol:
            break

    return scores


def tarjans_scc(adjacency_matrix: np.ndarray) -> List[List[int]]:
    """
    Find strongly connected components using Tarjan's algorithm.

    Args:
        adjacency_matrix: n x n matrix where A[i,j] > 0 indicates edge from i to j

    Returns:
        List of strongly connected components, each component is a list of node indices.
        Components are returned in reverse topological order.
    """
    n = adjacency_matrix.shape[0]

    # Build adjacency list from matrix
    adj_list: Dict[int, List[int]] = {i: [] for i in range(n)}
    for i in range(n):
        for j in range(n):
            if adjacency_matrix[i, j] > 0 and i != j:
                adj_list[i].append(j)

    # Tarjan's algorithm state
    index_counter = [0]
    stack: List[int] = []
    lowlink: Dict[int, int] = {}
    index: Dict[int, int] = {}
    on_stack: Set[int] = set()
    components: List[List[int]] = []

    def strongconnect(v: int):
        # Set the depth index for v to the smallest unused index
        index[v] = index_counter[0]
        lowlink[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        on_stack.add(v)

        # Consider successors of v
        for w in adj_list[v]:
            if w not in index:
                # Successor w has not yet been visited; recurse on it
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                # Successor w is in stack and hence in the current SCC
                lowlink[v] = min(lowlink[v], index[w])

        # If v is a root node, pop the stack and create an SCC
        if lowlink[v] == index[v]:
            component = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                component.append(w)
                if w == v:
                    break
            components.append(component)

    # Find SCCs for all nodes
    for v in range(n):
        if v not in index:
            strongconnect(v)

    return components
