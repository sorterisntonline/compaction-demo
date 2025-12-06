"""
Memory compaction through pairwise voting and rank centrality.

The AI votes on its own memories. Sparse comparisons form a spanning tree.
Rank centrality extracts global ordering. The budget cuts. What remains is chosen.
"""

import random
from dataclasses import dataclass, field
from typing import Callable, List, Tuple

import numpy as np

from .rank import rank_centrality


@dataclass
class Memory:
    """A unit of experience the AI might keep or release."""
    content: str
    id: str = field(default_factory=lambda: f"{random.randint(0, 2**64):016x}")


def compact(
    memories: List[Memory],
    budget: int,
    vote: Callable[[Memory, Memory], float],
    extra: int = 0,
) -> Tuple[List[Memory], List[Memory]]:
    """
    Compact memories to fit budget through pairwise voting.

    Args:
        memories: All memories to consider
        budget: How many to keep
        vote: vote(a, b) returns -50..+50 (positive prefers a)
        extra: Additional comparisons beyond the spanning tree

    Returns:
        (kept, released)
    """
    if len(memories) <= budget:
        return list(memories), []

    # Build spanning tree: n-1 comparisons guarantee connectivity
    shuffled = random.sample(memories, len(memories))
    pairs = [(random.choice(shuffled[:k]), shuffled[k]) for k in range(1, len(shuffled))]
    
    # Add extra comparisons for robustness
    pairs += [tuple(random.sample(memories, 2)) for _ in range(extra)]

    # Collect votes and build comparison matrix
    n = len(memories)
    idx = {m.id: i for i, m in enumerate(memories)}
    A = np.zeros((n, n))

    for a, b in pairs:
        score = max(-50, min(50, vote(a, b)))
        p_a = (score + 50) / 100  # Map to [0, 1]
        i, j = idx[a.id], idx[b.id]
        A[j, i] += p_a      # a preferred to b
        A[i, j] += 1 - p_a  # b preferred to a

    # Rank and partition
    scores = rank_centrality(A)
    ranked = sorted(range(n), key=lambda i: scores[i], reverse=True)

    kept = [memories[i] for i in ranked[:budget]]
    released = [memories[i] for i in ranked[budget:]]

    return kept, released
