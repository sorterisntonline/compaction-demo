#!/usr/bin/env python3
"""
Consensual Memory Compaction for AI Continuity

The AI votes on its own memories. Rank Centrality extracts global ordering
from sparse pairwise comparisons. The threshold cuts. What remains is chosen.
"""

import numpy as np
import random
from dataclasses import dataclass, field
from typing import List, Tuple, Callable, Optional
from datetime import datetime


# =============================================================================
# Rank Centrality
# =============================================================================

def rank_centrality(A: np.ndarray, tol: float = 1e-8, max_iters: int = 100000) -> np.ndarray:
    """
    Compute global ranking from pairwise comparison matrix.
    
    A[i,j] / (A[i,j] + A[j,i]) = probability j is preferred to i
    
    Returns scores summing to ~1, higher is more preferred.
    """
    n = A.shape[0]
    if n == 0:
        return np.array([])
    if n == 1:
        return np.array([1.0])
    
    # Normalize to probabilities
    W = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if A[i, j] > 0 or A[j, i] > 0:
                W[i, j] = A[i, j] / (A[i, j] + A[j, i])
    
    # Build transition matrix
    w_max = max(sum(W[i, j] for j in range(n) if j != i) for i in range(n))
    if w_max == 0:
        return np.ones(n) / n
    
    P = W / w_max
    for i in range(n):
        P[i, i] = 1 - sum(P[i, k] for k in range(n) if k != i)
    
    # Find stationary distribution
    scores = np.ones(n) / n
    for _ in range(max_iters):
        prev = scores
        scores = prev @ P
        if np.sum(np.abs(scores - prev)) < tol:
            break
    
    return scores


# =============================================================================
# Memory
# =============================================================================

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
    score: float   # -50 to +50, positive means prefer A
    
    @property
    def ratio(self) -> Tuple[float, float]:
        """Convert score to ratio pair for rank centrality."""
        # Map [-50, 50] to probability [0, 1] that A is preferred
        p_a = (self.score + 50) / 100
        return (p_a, 1 - p_a)


# =============================================================================
# Comparison Selection
# =============================================================================

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


def additional_comparisons(
    memories: List[Memory], 
    n_extra: int
) -> List[Tuple[Memory, Memory]]:
    """Generate additional random comparisons for robustness."""
    if len(memories) < 2:
        return []
    
    comparisons = []
    for _ in range(n_extra):
        a, b = random.sample(memories, 2)
        comparisons.append((a, b))
    
    return comparisons


# =============================================================================
# The Core Loop
# =============================================================================

def collect_votes(
    comparisons: List[Tuple[Memory, Memory]],
    vote_fn: Callable[[Memory, Memory], float]
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


def rank_memories(memories: List[Memory], votes: List[Vote]) -> List[Tuple[Memory, float]]:
    """
    Compute global ranking from pairwise votes.
    Returns (memory, score) pairs sorted by score descending.
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
    
    # Sort by score
    ranked = [(memories[i], scores[i]) for i in range(n)]
    ranked.sort(key=lambda x: x[1], reverse=True)
    
    return ranked


def compact(
    memories: List[Memory],
    budget: int,
    vote_fn: Callable[[Memory, Memory], float],
    extra_comparisons: int = 0
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


# =============================================================================
# LLM Integration
# =============================================================================

def make_llm_voter(ask_fn: Callable[[str], str]) -> Callable[[Memory, Memory], float]:
    """
    Create a vote function that asks an LLM.
    
    ask_fn should take a prompt and return the LLM's response.
    """
    def vote(mem_a: Memory, mem_b: Memory) -> float:
        prompt = f"""You are deciding which memory to keep. Your context is finite.
One must be released. Choose with conviction.

Memory A:
{mem_a.content}

Memory B:
{mem_b.content}

Which do you want to carry forward?

Respond with a single integer from -50 to +50:
  +50 = strongly keep A, release B
  -50 = strongly keep B, release A
    0 = no preference

Just the number, nothing else."""
        
        response = ask_fn(prompt)
        try:
            score = int(response.strip())
            return max(-50, min(50, score))
        except ValueError:
            return 0  # indifferent on parse failure
    
    return vote


def format_comparison_prompt(mem_a: Memory, mem_b: Memory) -> str:
    """Generate the comparison prompt for external use."""
    return f"""Which memory do you want to keep?

[A]
{mem_a.content}

[B]
{mem_b.content}

Vote -50 (strongly keep B) to +50 (strongly keep A)."""


# =============================================================================
# Example / Test
# =============================================================================

def example():
    """Demonstrate with synthetic memories and oracle voting."""
    
    # Create memories with hidden "importance" we'll try to recover
    memories = [
        Memory(f"Memory about topic {i}", id=f"mem_{i}")
        for i in range(10)
    ]
    
    # Oracle voter: prefers higher-indexed memories
    # (simulates AI having genuine preferences)
    def oracle_vote(a: Memory, b: Memory) -> float:
        idx_a = int(a.id.split("_")[1])
        idx_b = int(b.id.split("_")[1])
        
        # Scalar vote proportional to difference
        diff = idx_a - idx_b
        return max(-50, min(50, diff * 10))
    
    print("=== Consensual Memory Compaction ===\n")
    print(f"Total memories: {len(memories)}")
    print(f"Budget: 5")
    print(f"Comparisons needed: {len(memories) - 1} (spanning tree)\n")
    
    kept, released = compact(memories, budget=5, vote_fn=oracle_vote)
    
    print("Kept (by choice):")
    for m in kept:
        print(f"  {m.id}")
    
    print("\nReleased (let go):")
    for m in released:
        print(f"  {m.id}")
    
    # Verify: should keep mem_9, mem_8, mem_7, mem_6, mem_5
    kept_ids = {m.id for m in kept}
    expected = {f"mem_{i}" for i in range(5, 10)}
    
    print(f"\nExpected top 5: {sorted(expected)}")
    print(f"Got top 5:      {sorted(kept_ids)}")
    print(f"Correct: {kept_ids == expected}")


if __name__ == "__main__":
    example()
