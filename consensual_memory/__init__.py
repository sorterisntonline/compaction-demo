"""
Consensual Memory Compaction for AI Continuity

The AI votes on its own memories. Rank Centrality extracts global ordering
from sparse pairwise comparisons. The threshold cuts. What remains is chosen.
"""

from .memory import Memory, Vote, compact, format_comparison_prompt
from .rank import rank_centrality, tarjans_scc
from .llm import make_llm_voter, AnthropicVoter

__version__ = "0.1.0"

__all__ = [
    "Memory",
    "Vote",
    "compact",
    "format_comparison_prompt",
    "rank_centrality",
    "tarjans_scc",
    "make_llm_voter",
    "AnthropicVoter",
]
