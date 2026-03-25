# Memory Compaction via Vote-Based Ranking

A demonstration of memory compaction for AI systems with finite context windows.

## Problem

Large language models have finite context windows. When building AI agents with long-running memory, the event log eventually exceeds available tokens. Simply truncating loses important historical context. **Compaction** solves this by keeping the most valuable memories and releasing the rest.

## Solution: Vote-Based Ranking

This repo implements compaction through **pairwise preference voting**:

1. **Vote phase**: For a sample of memory pairs, ask the LLM: "Which memory is more important?" (-50 to +50 score).
2. **Rank phase**: Aggregate votes using rank centrality (a tournament-style ranking algorithm) to produce a global preference order.
3. **Keep phase**: Retain the top-ranked memories; release the rest.
4. **Resurrect phase**: Optionally resurrect high-ranked "old" memories that were previously released.

The ranking algorithm is robust: it handles incomplete comparisons, cycles, and ties gracefully.

## Data Model

All events are JSON-serialized in a `.jsonl` file (one event per line). Events are immutable and append-only.

```python
# Memories (4 types)
Thought(timestamp, content, id)      # Internal reasoning
Perception(timestamp, content, id)   # External observation
Response(timestamp, content, id)     # Output to user
Declaration(timestamp, content, id)  # Self-description (immune to compaction)

# System events
Init(timestamp, id, capacity, model, vote_model, api_key)  # Metadata (immune)
Vote(timestamp, vote_a_id, vote_b_id, vote_score, reasoning)  # Pairwise preference
Compaction(timestamp, kept_ids, released_ids, resurrected_ids)  # Compaction result
```

**Immunity**: `Init` and `Declaration` are never compacted. They remain in active memory forever.

## Compaction Strategies

The budget (capacity / 2) is divided among four slot types:

- **default**: 100% continuity (pure rank-based keep, no resurrection)
- **resurrection**: 50% continuity, 30% resurrection (revive old memories), 20% novelty (recent additions)
- **dream**: 50% continuity, 20% resurrection, 10% random, 20% novelty (experimental)

## Running

### Setup

```bash
uv sync
```

### CLI

```bash
# Create a being with capacity 10
python cli.py init my_being.jsonl --model gpt-4o --capacity 10

# Add some perceptions
python cli.py add my_being.jsonl "I saw a cat"
python cli.py add my_being.jsonl "The cat meowed"
python cli.py add my_being.jsonl "I gave the cat food"

# Show current state
python cli.py show my_being.jsonl

# Run compaction (requires OPENROUTER_API_KEY env var)
python cli.py compact my_being.jsonl --strategy default

# Check the result
python cli.py show my_being.jsonl
```

### Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run compaction-specific tests
uv run pytest tests/test_integration.py::test_compact_with_stubbed_vote -v
uv run pytest tests/test_rank.py -v
```

## Key Files

- **`adam.py`**: Core compaction engine
  - `Being`: The state object (events, current memory, votes, rankings)
  - `compact()`: Main compaction async generator
  - `vote()`: LLM-based pairwise comparison
  - `find_components()`: Union-find for vote graph connectivity
  - `rank_from_comparisons()`: Aggregate votes into global ranking

- **`schema.py`**: Event type definitions (immutable dataclasses)

- **`rank.py`**: Rank centrality algorithm
  - Pure math: builds a Markov chain from comparison matrix
  - No LLM calls, deterministic

- **`tests/`**:
  - `test_integration.py`: End-to-end compaction (with stubbed votes)
  - `test_rank.py`: Ranking algorithm correctness
  - `test_memory.py`: Schema serialization and prompt formatting
  - `test_vote_cache.py`: Vote caching behavior

## How Compaction Works (Detailed)

### Phase 1: Check Capacity
If `len(current) <= capacity // 2`, compaction is unnecessary. Return early.

### Phase 2: Build Vote Graph
Collect all existing votes on memories that are still in the system. Run union-find to detect disconnected components in the vote graph.

### Phase 3: Bridge Votes
If vote graph has multiple components, generate new votes to bridge them. This ensures the rank centrality algorithm can see the full ordering.

### Phase 4: Random Votes
Generate ~10% of possible pairs as random samples. This fills gaps in the comparison matrix.

### Phase 5: Execute Votes
For each new pair, call `vote(being, memory_a, memory_b)` → LLM → cache the result.

### Phase 6: Global Ranking
Call `rank_from_comparisons()` using the full vote matrix (all past + new votes) to produce a global ranking.

### Phase 7: Budget Allocation
Allocate `capacity // 2` slots across four strategies:
- **Continuity**: top N current memories by rank
- **Resurrection**: top M released (non-current) memories by rank
- **Random**: biased sample from remaining released (prefer old + high-rank)
- **Novelty**: most recent N current memories (by timestamp)

All four groups are collected into `kept_ids` (continuity + novelty) and `resurrected_ids` (resurrection + random). Everything else is `released_ids`.

### Phase 8: Write Compaction Event
Append a `Compaction` event to the JSONL. This event applies itself via `apply_event()`, which:
- Removes `released_ids` from `current`
- Adds `resurrected_ids` back to `current` (if they exist in `all_memories`)

## Testing Without LLM

Tests mock the `vote()` function to avoid LLM API calls. Example from `test_integration.py`:

```python
def fake_vote(_being, a, b):
    return 50 if a.id > b.id else -50  # Deterministic: higher IDs win

monkeypatch.setattr("adam.vote", fake_vote)
```

With a fixed random seed, compaction is deterministic and repeatable:

```python
random.seed(0)
asyncio.run(compact(being1))
kept_1 = set(being1.current.keys())

random.seed(0)
asyncio.run(compact(being2))
kept_2 = set(being2.current.keys())

assert kept_1 == kept_2  # Same seed → same outcome
```

## Environment

Set these to run compaction against a real LLM:

```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
```

Or mock `adam.vote()` in your tests for reproducibility.

## References

- **Rank centrality**: Graph-based ranking for incomplete pairwise comparisons. Used in sports rankings, recommendation systems.
- **Event sourcing**: Append-only log design. All state derived from event replay.
- **Memory compaction**: Garbage collection strategy for finite context windows.
