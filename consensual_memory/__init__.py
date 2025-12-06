"""
Consensual Memory: The AI votes on its own memories.

Rank centrality extracts global ordering from sparse pairwise comparisons.
The budget cuts. What remains is chosen.
"""

from .rank import rank_centrality, rank_from_comparisons

__all__ = ["rank_centrality", "rank_from_comparisons"]
