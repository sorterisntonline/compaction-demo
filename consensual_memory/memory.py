#!/usr/bin/env python3
"""
Core memory compaction logic.
"""

import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, List, Tuple

import numpy as np

from .rank import rank_centrality


@dataclass
class Memory:
    """A chunk of context the AI might keep or release."""

    content: str
    created: datetime = field(default_factory=datetime.now)
    id: str = field(default_factory=lambda: f"mem_{random.randint(0, 2**32):08x}")

    def __repr__(self):
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"Memory({self.id}: {preview!r})"


@dataclass
class Vote:
    """A pairwise comparison with scalar intensity."""

    memory_a: str  # id
    memory_b: str  # id
    score: float  # -50 to +50, positive means prefer A

    @property
    def ratio(self) -> Tuple[float, float]:
        """Convert score to ratio pair for rank centrality."""
        # Map [-50, 50] to probability [0, 1] that A is preferred
        p_a = (self.score + 50) / 100
        return (p_a, 1 - p_a)


def spanning_tree_comparisons(memories: List[Memory]) -> List[Tuple[Memory, Memory]]:
    """
    Generate n-1 comparisons forming a random spanning tree.
    Minimum comparisons needed to rank n items.
    """
    if len(memories) < 2:
        return []

    comparisons = []
    perm = random.sample(memories, len(memories))

    for k in range(1, len(perm)):
        # Connect new node to random existing node
        existing = random.choice(perm[:k])
        new = perm[k]
        comparisons.append((existing, new))

    return comparisons


def additional_comparisons(memories: List[Memory], n_extra: int) -> List[Tuple[Memory, Memory]]:
    """Generate additional random comparisons for robustness."""
    if len(memories) < 2:
        return []

    comparisons = []
    for _ in range(n_extra):
        a, b = random.sample(memories, 2)
        comparisons.append((a, b))

    return comparisons


def collect_votes(
    comparisons: List[Tuple[Memory, Memory]], vote_fn: Callable[[Memory, Memory], float]
) -> List[Vote]:
    """
    Present each comparison to the vote function.

    vote_fn(a, b) should return -50 to +50:
        +50 = strongly prefer to keep A
        -50 = strongly prefer to keep B
          0 = indifferent
    """
    votes = []
    for mem_a, mem_b in comparisons:
        score = vote_fn(mem_a, mem_b)
        score = max(-50, min(50, score))  # clamp
        votes.append(Vote(mem_a.id, mem_b.id, score))
    return votes


def rank_memories(
    memories: List[Memory], 
    votes: List[Vote],
    prior_scores: dict = None
) -> List[Tuple[Memory, float]]:
    """
    Compute global ranking from pairwise votes.
    Returns (memory, score) pairs sorted by score descending.
    
    Args:
        memories: List of memories to rank
        votes: List of pairwise votes
        prior_scores: Optional dict of memory_id -> prior strength (from past compactions)
    """
    if not memories:
        return []
    if len(memories) == 1:
        return [(memories[0], 1.0)]

    # Build index
    id_to_idx = {m.id: i for i, m in enumerate(memories)}
    n = len(memories)

    # Build comparison matrix
    A = np.zeros((n, n))
    for vote in votes:
        if vote.memory_a in id_to_idx and vote.memory_b in id_to_idx:
            i = id_to_idx[vote.memory_a]
            j = id_to_idx[vote.memory_b]
            ratio_a, ratio_b = vote.ratio
            A[j, i] += ratio_a  # i preferred to j
            A[i, j] += ratio_b  # j preferred to i

    # Compute rankings
    scores = rank_centrality(A)

    # Add prior strengths (normalized to same scale as rank centrality)
    if prior_scores:
        # Normalize prior scores to [0, 1] range similar to rank centrality output
        prior_values = [prior_scores.get(m.id, 0) for m in memories]
        if prior_values:
            max_abs = max(abs(v) for v in prior_values) or 1
            # Add normalized prior as a boost (0.1 weight to not overwhelm current votes)
            for i, m in enumerate(memories):
                prior = prior_scores.get(m.id, 0)
                scores[i] += 0.1 * (prior / max_abs)

    # Sort by score
    ranked = [(memories[i], scores[i]) for i in range(n)]
    ranked.sort(key=lambda x: x[1], reverse=True)

    return ranked


def compact(
    memories: List[Memory],
    budget: int,
    vote_fn: Callable[[Memory, Memory], float],
    extra_comparisons: int = 0,
) -> Tuple[List[Memory], List[Memory]]:
    """
    The full compaction process.

    Args:
        memories: All memories to consider
        budget: How many to keep
        vote_fn: Function that votes on pairs
        extra_comparisons: Additional comparisons beyond spanning tree

    Returns:
        (kept, released) - the AI chose what survives
    """
    if len(memories) <= budget:
        return memories, []

    # Generate comparisons
    comparisons = spanning_tree_comparisons(memories)
    if extra_comparisons > 0:
        comparisons += additional_comparisons(memories, extra_comparisons)

    # Collect votes
    votes = collect_votes(comparisons, vote_fn)

    # Rank
    ranked = rank_memories(memories, votes)

    # Cut
    kept = [m for m, _ in ranked[:budget]]
    released = [m for m, _ in ranked[budget:]]

    return kept, released


def format_comparison_prompt(mem_a: Memory, mem_b: Memory) -> str:
    """Generate the comparison prompt for external use."""
    return f"""Which memory do you want to keep?

[A]
{mem_a.content}

[B]
{mem_b.content}

Vote -50 (strongly keep B) to +50 (strongly keep A)."""
