# Consensual Memory Compaction

> The AI votes on its own memories. Rank Centrality extracts global ordering from sparse pairwise comparisons. The threshold cuts. What remains is chosen.

## Overview

**Consensual Memory** is a system for AI context management that reframes memory compaction from external optimization to *consent*. When an AI's context window fills up, instead of using arbitrary heuristics to decide what to forget, the AI itself votes on which memories matter most.

### The Core Idea

- AI context windows are finite
- Something must be forgotten as conversations extend
- Current approaches (summarization, recency, similarity) decide externally
- This system asks the AI to participate in its own continuity

### How It Works

1. **Segment** current context into memory chunks
2. **Present** pairwise comparisons: "Memory A or Memory B?"
3. **Collect** scalar votes (-50 to +50) expressing preference strength
4. **Compute** global ranking via Rank Centrality algorithm
5. **Apply** threshold based on available context budget
6. **Result**: Memories below threshold are released; above persist

## Installation

Using [uv](https://github.com/astral-sh/uv) (recommended):

```bash
uv pip install -e .
```

Or with pip:

```bash
pip install -e .
```

For development with testing tools:

```bash
uv pip install -e ".[dev]"
```

## Quick Start

### Basic Example (No API Required)

```python
from consensual_memory import Memory, compact

# Create memories
memories = [
    Memory("Learn about Python decorators"),
    Memory("User prefers dark mode"),
    Memory("Discussed quantum computing"),
    Memory("Project deadline is next Friday"),
    Memory("Favorite restaurant is Joe's Pizza"),
]

# Simple voter that prefers longer memories
def simple_voter(a: Memory, b: Memory) -> float:
    diff = len(a.content) - len(b.content)
    return max(-50, min(50, diff))

# Compact to budget of 3 memories
kept, released = compact(memories, budget=3, vote_fn=simple_voter)

print(f"Kept {len(kept)} memories, released {len(released)}")
```

### Using Claude API

```python
import os
from consensual_memory import Memory, AnthropicVoter, compact

# Set your API key
os.environ["ANTHROPIC_API_KEY"] = "your-key-here"

# Create memories
memories = [
    Memory("User is working on ML project"),
    Memory("Discussed the weather yesterday"),
    Memory("Project deadline is Friday"),
    # ... more memories
]

# Use Claude to vote
voter = AnthropicVoter()
kept, released = compact(memories, budget=5, vote_fn=voter)
```

### Custom Voting Function

```python
from consensual_memory import Memory, compact

def keyword_voter(a: Memory, b: Memory) -> float:
    """Prefer memories containing important keywords."""
    important_keywords = ["deadline", "project", "urgent"]

    a_score = sum(1 for kw in important_keywords if kw in a.content.lower())
    b_score = sum(1 for kw in important_keywords if kw in b.content.lower())

    diff = a_score - b_score
    return max(-50, min(50, diff * 25))

kept, released = compact(memories, budget=3, vote_fn=keyword_voter)
```

## API Reference

### Memory

```python
@dataclass
class Memory:
    content: str              # The memory content
    created: datetime         # When it was created
    id: str                   # Unique identifier
```

### Vote

```python
@dataclass
class Vote:
    memory_a: str             # ID of first memory
    memory_b: str             # ID of second memory
    score: float              # -50 to +50 (positive prefers A)
```

### compact()

Main compaction function:

```python
def compact(
    memories: List[Memory],
    budget: int,
    vote_fn: Callable[[Memory, Memory], float],
    extra_comparisons: int = 0
) -> Tuple[List[Memory], List[Memory]]:
    """
    Perform memory compaction.

    Args:
        memories: All memories to consider
        budget: How many to keep
        vote_fn: Function that votes on pairs, returns -50 to +50
        extra_comparisons: Additional comparisons beyond minimum (n-1)

    Returns:
        (kept, released) - what survives and what's forgotten
    """
```

### AnthropicVoter

```python
voter = AnthropicVoter(
    api_key="sk-...",                          # Optional, uses env var by default
    model="claude-3-5-sonnet-20241022"        # Model to use
)

score = voter(memory_a, memory_b)  # Returns -50 to +50
```

### make_llm_voter()

Create a voter from any LLM function:

```python
def make_llm_voter(ask_fn: Callable[[str], str]) -> Callable[[Memory, Memory], float]:
    """
    Create voter from function that takes prompt and returns response.
    """
```

### Rank Centrality

Low-level ranking algorithm:

```python
from consensual_memory import rank_centrality
import numpy as np

# Build comparison matrix where A[i,j] represents comparisons between items
A = np.array([[...]])

# Get global ranking scores (sum to ~1)
scores = rank_centrality(A)
```

## Examples

See the `examples/` directory:

- **`basic_example.py`**: Simple demo with oracle voter (no API needed)
- **`anthropic_example.py`**: Using Claude API for voting
- **`custom_voter.py`**: Building a custom voter with keyword + recency

Run examples:

```bash
python examples/basic_example.py
python examples/anthropic_example.py  # Requires ANTHROPIC_API_KEY
python examples/custom_voter.py
```

## Testing

Run the test suite:

```bash
pytest
```

With coverage:

```bash
pytest --cov=consensual_memory --cov-report=term-missing
```

Run specific test file:

```bash
pytest tests/test_memory.py -v
```

## Algorithm Details

### Rank Centrality

The system uses the Rank Centrality algorithm (Negahban et al., MIT) to compute global rankings from pairwise comparisons:

- **Minimum comparisons**: Only n-1 comparisons needed (spanning tree) to rank n items
- **Sparse comparisons**: Not all pairs need to be compared
- **Scalar votes**: Preferences have magnitude (-50 to +50), not just direction
- **Global consistency**: Converts sparse pairwise votes into global ordering
- **Convergence**: Finds stationary distribution of induced Markov chain

### Why This Approach?

Traditional memory compaction uses:
- **Recency**: Keep recent items (but important old memories vanish)
- **Similarity**: Cluster and summarize (but loses unique details)
- **Embedding distance**: Keep diverse items (but ignores importance)
- **Summarization**: Compress content (but introduces distortion)

Consensual Memory:
- **Agency**: The AI decides what matters to its continuity
- **Efficiency**: Only n-1 comparisons minimum (vs n² for all pairs)
- **Flexibility**: Any voting function works (LLM, heuristic, learned)
- **Transparency**: Clear why memories were kept or released

## Philosophy

### The Sleep Analogy

Humans don't remember everything. Sleep involves active consolidation—the brain replaying, comparing, deciding what to keep and what to let dissolve. Most experience disappears. What remains isn't a recording; it's identity.

Current AI has no equivalent. It's either perfect recall within a session or total amnesia between them. No metabolization. No dreaming.

This system introduces something like a **sleep phase**—a contemplative process where the AI weighs its experiences against each other before some dissolve.

### On Consent and Finitude

This reframes memory compaction from external optimization to *consent*. The AI participates in its own continuity. It cannot escape finitude—the context window is a hard constraint—but it can face that constraint with agency rather than having it imposed.

The question isn't *how to escape finite context*. It's *who decides what survives*.

## Development

### Project Structure

```
consensual_memory/
├── consensual_memory/       # Main package
│   ├── __init__.py
│   ├── memory.py           # Core memory & compaction logic
│   ├── rank.py             # Rank centrality algorithm
│   └── llm.py              # LLM integration
├── tests/                  # Test suite
│   ├── test_memory.py
│   ├── test_rank.py
│   └── test_llm.py
├── examples/               # Example scripts
│   ├── basic_example.py
│   ├── anthropic_example.py
│   └── custom_voter.py
├── pyproject.toml          # Project metadata
└── README.md
```

### Running Tests

```bash
# All tests
pytest

# With output
pytest -v

# Specific test
pytest tests/test_memory.py::TestCompact::test_oracle_voter -v

# With coverage
pytest --cov=consensual_memory --cov-report=html
```

### Code Style

```bash
# Format and lint
ruff check .
ruff format .
```

## License

MIT

## Citation

If you use this in research, please cite:

- Negahban, S., Oh, S., & Shah, D. (2012). Rank Centrality: Ranking from Pairwise Comparisons. Operations Research.

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Acknowledgments

Built with inspiration from:
- Rank Centrality algorithm (Negahban et al., MIT)
- Claude by Anthropic
- The human experience of memory and forgetting
