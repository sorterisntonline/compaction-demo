# compaction-demo

An AI agent accumulates memories as an append-only JSONL log. When the log outgrows a fixed capacity, **compaction** decides which memories to keep and which to release. The decision is made by the agent itself: it votes on pairs of memories, and a rank-centrality algorithm turns those pairwise preferences into a global ordering.

## The idea

An agent has a **capacity** (say, 100 memories). It thinks, perceives, responds, and all of these become memories. Once the count exceeds `capacity / 2`, compaction fires. The agent is asked "which of these two memories matters more?" for a sample of pairs. The votes feed into a Markov-chain ranking algorithm that produces a global preference order. The top-ranked memories survive; the rest are released.

Released memories aren't deleted. They stay in the log and in `all_memories`. A future compaction can **resurrect** them if the agent's priorities shift.

## How it works

### Events

Everything is an event, appended to a `.jsonl` file. State is derived by replaying the log.

| Event | Fields | Compactable? |
|-------|--------|-------------|
| `Init` | `timestamp, id, capacity, model, vote_model, api_key` | No (immune) |
| `Thought` | `timestamp, content, id` | Yes |
| `Perception` | `timestamp, content, id` | Yes |
| `Response` | `timestamp, content, id` | Yes |
| `Declaration` | `timestamp, content, id` | No (immune) |
| `Vote` | `timestamp, vote_a_id, vote_b_id, vote_score, reasoning` | N/A (metadata) |
| `Compaction` | `timestamp, kept_ids, released_ids, resurrected_ids` | N/A (metadata) |

`Init` and `Declaration` are immune -- they always stay in active memory. Votes and Compaction events are bookkeeping; they're never in the "current memory" set.

### The compaction algorithm

```
compact(being, strategy):

  1. Guard: if current memories <= capacity/2, return early.

  2. Collect all existing votes between known memories.
     Run union-find to find disconnected components in the vote graph.

  3. Bridge votes: if the vote graph has multiple components among
     current memories, generate pairwise votes between components
     so rank centrality can see the full picture.

  4. Random votes: sample ~max(20, N/10) new random pairs from
     current memories that haven't been compared yet.

  5. Execute votes: for each new pair, ask the LLM
     "which memory is more important? score -50 to +50"
     and persist the Vote event.

  6. Rank: feed ALL votes (historical + new) into rank_from_comparisons(),
     which builds a comparison matrix and computes the stationary
     distribution of a Markov chain. This produces a global ordering
     over every memory the agent has ever had.

  7. Allocate budget (= capacity/2) across four slot types:
     - continuity:   top-ranked current memories
     - resurrection: top-ranked released memories (brought back)
     - random:       weighted sample of released memories (biased toward
                     high-rank and old age)
     - novelty:      most recent current memories by timestamp

  8. Write a Compaction event recording kept_ids, released_ids,
     and resurrected_ids. apply_event() updates being.current.
```

### Strategies

A `CompactionStrategy` controls how the budget is split:

| Strategy | Continuity | Resurrection | Random | Novelty |
|----------|-----------|-------------|--------|---------|
| `default` | 1.0 | 0 | 0 | 0 |
| `resurrection` | 0.5 | 0.3 | 0 | 0.2 |
| `dream` | 0.5 | 0.2 | 0.1 | 0.2 |

**default** is pure rank-based survival. **resurrection** brings back old memories that rank well globally. **dream** adds a random element -- buried memories can resurface by chance, weighted by rank and age.

### Rank centrality

The ranking engine (`rank.py`) implements rank centrality for incomplete pairwise comparisons. Given a comparison matrix A where `A[i][j] / (A[i][j] + A[j][i])` is the probability that j is preferred to i, it constructs a transition matrix for a random walk and finds its stationary distribution via power iteration. The stationary probability of each item is its global score.

This is the same math used for tournament rankings -- it handles cycles, incomplete data, and varying comparison strengths gracefully. The graph of comparisons must be connected, which is why `compact()` generates bridge votes between disconnected components.

### State management

`Being` holds the live state:

- `events` -- the full ordered log (append-only)
- `current` -- `{id: event}` dict of active memories
- `all_memories` -- `{id: event}` dict of every memory ever (never shrinks)
- `votes` -- `{(low_id, high_id): score}` cache of pairwise comparisons

`apply_event()` is the pure state-transition function, called both during live operation (`append()`) and during replay (`load()`). A freshly-loaded being has identical state to one that has been running live -- this is the event-sourcing guarantee.

## Usage

```
uv sync
```

### CLI

```bash
python cli.py init agent.jsonl --model gpt-4o --capacity 20
python cli.py add agent.jsonl "The user prefers short answers"
python cli.py add agent.jsonl "We're working on a billing system"
python cli.py show agent.jsonl
python cli.py compact agent.jsonl --strategy default
```

Compaction requires `OPENROUTER_API_KEY` set in the environment (or `.env`). The vote LLM is configured via `vote_model` in the Init event.

### Tests

```bash
uv run pytest
```

All tests run without an API key. They stub the vote function:

```python
async def fake_vote(_being, a, b):
    return 50 if a.id > b.id else -50

monkeypatch.setattr("adam.vote", fake_vote)
```

With a fixed `random.seed`, compaction is fully deterministic.

**test_integration.py** -- end-to-end: builds a being with 12 memories at capacity 4, runs compaction with stubbed votes, asserts the result is deterministic and that current memory count equals `budget + 1` (budget + immune Init).

**test_rank.py** -- verifies the ranking algorithm produces correct orderings from comparison matrices.

**test_memory.py** -- schema round-trip serialization, prompt formatting, union-find correctness, and that `apply_event(Compaction(...))` correctly removes released memories from `current`.

**test_vote_cache.py** -- verifies that `vote()` reuses cached scores without calling the LLM, and that score sign flips correctly when argument order is reversed.

## Files

```
adam.py       Being, compact(), vote(), append(), load(), apply_event()
schema.py     Event types (frozen dataclasses), to_dict/from_dict
rank.py       rank_centrality(), rank_from_comparisons()
cli.py        CLI: init, add, show, compact
tests/        14 tests, all offline
pyproject.toml
```
