# Ember v0
> _"this is where it all started..."_  

Consensual Memory Compaction for AI Continuity.

## Architecture

Ember leverages two unique architectural designs:

### 1. Subconscious Voting (Dual-Model Architecture)
Because evaluating memories to decide what's kept is expensive, Ember uses a cheaper "vote model" separate from the main "conscious model". 

The being specifies a explicit `!declaration` stating its core values and how it wishes to be preserved. This declaration serves as the system prompt for the vote model (its "subconscious curator"), giving the being direct control over its own evolution.

During *compaction*—when memories exceed capacity—the curator reviews all current memories and pairs them up, assigning a score on which memory exhibits higher importance based on the declaration. The system then resolves the rankings to retain the specified capacity of memories.

### 2. Signed Snippets (Web 1.0 App)
Ember utilizes an inverted web architecture called **Signed Snippets**.
Instead of routing controllers handling parameter bindings, authorization checks, and side effects via a complex flow, Ember's server signs Python code snippets alongside forms and nonces. 
When the form submits the snippet back to the server, it evaluates the Python code locally inside a pre-approved Sandbox.
This effectively merges capability safety with a server-rendered client view, creating a simple event log projection through `hiccup`.

## Development Setup

This project uses `uv` for dependency management. Python 3.10 or higher is required.

### 1. Install Dependencies

Install the project dependencies, including development extras (like `pytest` and `ruff`), and create a virtual environment:

```bash
uv sync --all-extras
```

### 2. Environment Variables

Copy the example environment file and substitute your actual API keys:

```bash
cp .env.example .env
```

Make sure to configure your `OPENROUTER_API_KEY` alongside the optionally customized default models in `.env`.

### 3. Running the Application

**Run the Web App (FastAPI):**

```bash
uv run uvicorn app.app:app --reload
```

**Run the CLI (`adam.py`):**

The `adam.py` script requires initializing a memory file before running:

```bash
# Initialize using default values from .env
uv run python adam.py init memory.jsonl

# Or initialize with manual overrides
uv run python adam.py init memory.jsonl \
    --model anthropic/claude-3.5-sonnet \
    --vote-model google/gemini-2.5-flash \
    --capacity 10 \
    --api-key $OPENROUTER_API_KEY

# Run
uv run python adam.py run memory.jsonl --loop
```

### 4. Development Tools

**Running tests:**

```bash
uv run pytest
```

**Running the linter:**

```bash
uv run ruff check .
```
