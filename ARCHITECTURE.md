# Architecture & Design

This document explains how the consensual memory compaction system works and how all the pieces fit together.

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                     Compaction Flow                      │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────┐
        │    1. Create Memories             │
        │    [Memory, Memory, ...]          │
        └───────────┬───────────────────────┘
                    │
                    ▼
        ┌───────────────────────────────────┐
        │    2. Generate Comparisons        │
        │    Spanning Tree (n-1 minimum)    │
        │    + Optional Extra Comparisons   │
        └───────────┬───────────────────────┘
                    │
                    ▼
        ┌───────────────────────────────────┐
        │    3. Collect Votes               │
        │    For each (A, B) pair:          │
        │    vote_fn(A, B) → [-50, +50]     │
        └───────────┬───────────────────────┘
                    │
                    ▼
        ┌───────────────────────────────────┐
        │    4. Build Comparison Matrix     │
        │    Convert votes to probabilities │
        └───────────┬───────────────────────┘
                    │
                    ▼
        ┌───────────────────────────────────┐
        │    5. Rank Centrality Algorithm   │
        │    Compute global ranking scores  │
        └───────────┬───────────────────────┘
                    │
                    ▼
        ┌───────────────────────────────────┐
        │    6. Apply Budget Threshold      │
        │    kept = top K memories          │
        │    released = remaining memories  │
        └───────────────────────────────────┘
```

## Core Components

### 1. Memory (`consensual_memory/memory.py`)

The fundamental unit of context that can be kept or released.

```python
@dataclass
class Memory:
    content: str      # The actual content
    created: datetime # When it was created
    id: str          # Unique identifier
```

**Key Functions:**
- `spanning_tree_comparisons()`: Generate minimum n-1 comparisons
- `collect_votes()`: Present comparisons to voting function
- `rank_memories()`: Convert votes to rankings
- `compact()`: Main entry point for full compaction

### 2. Vote (`consensual_memory/memory.py`)

Represents a pairwise comparison with scalar intensity.

```python
@dataclass
class Vote:
    memory_a: str  # ID of first memory
    memory_b: str  # ID of second memory
    score: float   # -50 to +50 (positive prefers A)
```

The `ratio` property converts the scalar vote to probabilities:
- Score +50 → (1.0, 0.0) - strongly prefer A
- Score 0   → (0.5, 0.5) - no preference
- Score -50 → (0.0, 1.0) - strongly prefer B

### 3. Rank Centrality (`consensual_memory/rank.py`)

Algorithm that computes global rankings from sparse pairwise comparisons.

**Key Insight:** Models preferences as a Markov chain where the stationary distribution represents global ranking.

**Process:**
1. Normalize comparison matrix to probabilities
2. Build transition matrix where rows sum to 1
3. Find stationary distribution via power iteration
4. Return scores (sum to ~1, higher = more preferred)

**Efficiency:**
- Only needs n-1 comparisons minimum (spanning tree)
- Supports sparse comparisons (not all pairs)
- Converges quickly via power iteration
- Uses sparse matrices for large n (>250)

### 4. LLM Integration (`consensual_memory/llm.py`)

Provides voting functions powered by language models.

**`make_llm_voter(ask_fn)`**
- Generic wrapper for any LLM API
- Takes function that sends prompt and returns response
- Handles parsing and error recovery

**`AnthropicVoter`**
- Ready-to-use voter with Claude API
- Configurable model selection
- Automatic API key management

### 5. Tarjan's SCC (`consensual_memory/rank.py`)

Finds strongly connected components in comparison graph.

**Use Case:** When memories form disconnected groups (never compared), each group must be ranked separately.

**Algorithm:** Single-pass DFS that identifies all SCCs in O(V + E) time.

## Data Flow Example

```python
# 1. Create memories
memories = [
    Memory("User prefers Python"),
    Memory("Favorite color is blue"),
    Memory("Project deadline Friday")
]

# 2. Define voting function
def voter(a: Memory, b: Memory) -> float:
    # Prefer memories with keywords
    keywords = ["project", "deadline"]
    a_score = sum(kw in a.content.lower() for kw in keywords)
    b_score = sum(kw in b.content.lower() for kw in keywords)
    return (a_score - b_score) * 25

# 3. Compact
kept, released = compact(memories, budget=2, vote_fn=voter)

# Internal process:
# - Generate 2 comparisons (spanning tree for 3 items)
# - Collect 2 votes from voter function
# - Build 3x3 comparison matrix
# - Run rank centrality
# - Sort by scores
# - Keep top 2, release 1
```

## Algorithm Properties

### Time Complexity

- **Comparison generation:** O(n) for spanning tree
- **Vote collection:** O(c) where c = number of comparisons
- **Rank centrality:** O(n² × i) where i = iterations to converge
- **Overall:** O(n²) for typical cases

### Space Complexity

- **Memory storage:** O(n)
- **Comparison matrix:** O(n²)
- **Sparse mode:** O(nnz) for non-zero entries only

### Guarantees

- ✅ Minimum n-1 comparisons needed
- ✅ Deterministic with fixed random seed
- ✅ Converges for any connected graph
- ✅ Handles sparse comparisons
- ✅ Supports scalar (not just binary) votes

## Testing Strategy

### Unit Tests (`tests/test_*.py`)

- **`test_memory.py`**: Memory, Vote, comparison generation, ranking
- **`test_rank.py`**: Rank centrality algorithm, Tarjan's SCC
- **`test_llm.py`**: LLM voter creation and integration

### Integration Tests (`tests/test_integration.py`)

- End-to-end pipeline with mock LLM
- Stability with extra comparisons
- Gradual compaction (repeated rounds)
- Edge cases and tie-breaking
- Deterministic behavior

### Coverage

- **93% overall coverage**
- 100% coverage on core memory logic
- 97% coverage on rank centrality
- Untested lines are mostly error handling paths

## Extension Points

### Custom Voting Functions

The system accepts any `Callable[[Memory, Memory], float]`:

```python
def recency_voter(a: Memory, b: Memory) -> float:
    """Prefer more recent memories."""
    age_diff = (b.created - a.created).total_seconds()
    return max(-50, min(50, age_diff / 3600))  # hours

def keyword_voter(keywords: list[str]):
    """Prefer memories containing keywords."""
    def vote(a: Memory, b: Memory) -> float:
        a_count = sum(kw in a.content.lower() for kw in keywords)
        b_count = sum(kw in b.content.lower() for kw in keywords)
        return (a_count - b_count) * 20
    return vote

def hybrid_voter(voters: list, weights: list[float]):
    """Combine multiple voting strategies."""
    def vote(a: Memory, b: Memory) -> float:
        scores = [v(a, b) for v in voters]
        weighted = sum(s * w for s, w in zip(scores, weights))
        return max(-50, min(50, weighted))
    return vote
```

### Alternative Ranking Algorithms

While Rank Centrality is used by default, the system could support:

- **PageRank**: For memory graphs with explicit links
- **Bradley-Terry**: For modeling skill ratings
- **Elo**: For incremental updates
- **TrueSkill**: For multi-player comparisons

### Memory Persistence

Add serialization for long-term storage:

```python
import json

def save_memories(memories: list[Memory], path: str):
    data = [{"content": m.content, "created": m.created.isoformat(),
             "id": m.id} for m in memories]
    with open(path, 'w') as f:
        json.dump(data, f)

def load_memories(path: str) -> list[Memory]:
    with open(path) as f:
        data = json.load(f)
    return [Memory(d["content"],
                   datetime.fromisoformat(d["created"]),
                   d["id"]) for d in data]
```

## Performance Considerations

### For Small n (<100)

- Use default settings
- Spanning tree sufficient
- Fast convergence

### For Medium n (100-1000)

- Add 10-20 extra comparisons for robustness
- Consider batching votes for LLM efficiency
- Sparse matrix mode activates automatically at n≥250

### For Large n (>1000)

- Use hierarchical compaction (multiple rounds)
- Consider approximate algorithms
- Cache vote results to avoid redundant LLM calls
- Use faster vote functions where possible

## Future Enhancements

1. **Incremental Updates**: Add/remove memories without full recomputation
2. **Vote Caching**: Store and reuse previous votes
3. **Adaptive Comparisons**: Strategically choose which pairs to compare
4. **Multi-Attribute Ranking**: Rank on different dimensions simultaneously
5. **Explanation Generation**: Explain why memories were kept/released
6. **Active Learning**: Query uncertain comparisons first
7. **Consensus Voting**: Combine votes from multiple LLMs or humans

## References

- Negahban, S., Oh, S., & Shah, D. (2012). "Rank Centrality: Ranking from Pairwise Comparisons." Operations Research.
- Tarjan, R. (1972). "Depth-first search and linear graph algorithms." SIAM Journal on Computing.
