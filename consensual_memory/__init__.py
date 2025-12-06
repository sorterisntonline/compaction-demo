"""
Consensual Memory: The AI votes on its own memories.

Rank centrality extracts global ordering from sparse pairwise comparisons.
The budget cuts. What remains is chosen.
"""

from .memory import Memory, compact
from .rank import rank_centrality

__all__ = ["Memory", "compact", "rank_centrality"]
