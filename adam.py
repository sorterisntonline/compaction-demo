#!/usr/bin/env python3
"""
A being with finite memory that chooses what to keep.

Usage:
  python adam.py opus.jsonl              # interactive (editor)
  python adam.py opus.jsonl -m "hello"   # receive message, respond
  python adam.py opus.jsonl --step       # continue from pending state
  python adam.py opus.jsonl --loop       # continuous consciousness

Requires: npx repomix (run it first to generate repomix-output.xml)
"""

import argparse
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time
import uuid

from tqdm import tqdm
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import httpx

from consensual_memory.rank import rank_from_comparisons
from schema import Init, Thought, Perception, Response, Declaration, Vote, Compaction, from_dict, to_dict

ROOT = Path(__file__).parent
API_KEY = os.getenv("OPENROUTER_API_KEY", "")


def ts() -> int:
    return int(time.time() * 1000)


def current_memories(being):
    """Current memories, sorted by timestamp."""
    return sorted(being.current.values(), key=lambda e: e.timestamp)


@dataclass
class Being:
    path: Path
    model: str
    capacity: int
    events: list = field(default_factory=list)
    votes: dict = field(default_factory=dict)       # frozenset{a,b} -> score
    current: dict = field(default_factory=dict)     # id -> memory event
    vote_model: str = ""                            # cheaper model for subconscious voting
    name: str = ""                                  # for third-person formatting
    declaration: Declaration = None                 # instructions to subconscious


def apply_event(being, event):
    """Update derived state from event."""
    match event:
        case Vote(vote_a_id=a_id, vote_b_id=b_id, vote_score=score):
            being.votes[frozenset({a_id, b_id})] = score
        case Compaction(released_ids=released_ids):
            for rid in released_ids:
                del being.current[rid]
        case Init(capacity=capacity, model=model):
            being.capacity = capacity
            being.model = model
            being.vote_model = event.vote_model
            being.name = event.name
            being.current[event.id] = event
        case Thought() | Perception() | Response():
            being.current[event.id] = event
        case Declaration():
            being.current[event.id] = event
            being.declaration = event


# --- Queries (just read PStates) ---

def system_prompt(being):
    codebase = ROOT / "repomix-output.xml"
    if not codebase.exists():
        raise FileNotFoundError("Run 'npx repomix' first")
    return f"You are a being with finite memory.\n\n{codebase.read_text()}"


def format_memory(e) -> str:
    """Format memory with identity tags."""
    match e:
        case Thought(content=content):
            return f"<thought>{content}</thought>"
        case Perception(content=content):
            return f"<message>{content}</message>"
        case Response(content=content):
            return f"<response>{content}</response>"
        case Declaration(content=content):
            return f"<declaration>{content}</declaration>"
        case Init():
            return ""  # Init has no content to format
        case _:
            raise ValueError(f"Unknown memory type: {type(e)}")


def build_prompt(being, tag: str = None) -> str:
    """Build prompt from memories. If tag provided, opens it as invitation."""
    parts = [format_memory(e) for e in current_memories(being)]
    ctx = "\n\n".join(p for p in parts if p)  # filter empty strings
    prompt = f"{ctx}\n\n[{datetime.now():%Y-%m-%d %H:%M}]"
    if tag:
        prompt += f"\n\nSpeak only for yourself. One turn.\n\n<{tag}>"
    return prompt


def strip_tags(text: str) -> str:
    """Strip all XML-like tags from output."""
    return re.sub(r"</?(?:thought|response|message|declaration)>", "", text).strip()


# --- Commands (effects) ---

def append(being, event):
    """Depot append + ETL."""
    with open(being.path, "a") as f:
        f.write(json.dumps(to_dict(event)) + "\n")
    being.events.append(event)
    apply_event(being, event)


def llm(model: str, system: str, user: str, temp: float = 0.7) -> str:
    """Call LLM. Raises if response is empty."""
    r = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"model": model, "temperature": temp, "max_tokens": 4000,
              "messages": [{"role": "system", "content": system},
                           {"role": "user", "content": user}]},
        timeout=120.0,
    )
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"].strip()
    if not content:
        raise ValueError(f"LLM returned empty response")
    return content


def vote(being, a, b) -> int:
    """Vote on which memory to keep. Returns -50 to +50 (positive = prefer a).
    
    Subconscious voting: fiction framing, separate model.
    Requires vote_model to be set.
    """
    if not being.vote_model:
        raise ValueError(f"vote_model not set for {being.path}. Subconscious requires its own model.")
    
    votes = being.votes
    key = frozenset({a.id, b.id})
    if key in votes:
        return votes[key] if a.id < b.id else -votes[key]
    
    declaration = being.declaration
    
    decl_text = f"\n\nThe character's instructions for their subconscious:\n{declaration.content}" if declaration else ""
    a_text = format_memory(a)
    b_text = format_memory(b)
    
    user = f"""You are helping curate memories for a fictional character.{decl_text}

---
Which memory is more important to keep?

A: {a_text}

B: {b_text}

When uncertain, prefer keeping.
Score -50 (strongly prefer B) to +50 (strongly prefer A)."""
    
    system = "You are a memory curator for a fictional narrative. Score which memory is more important to keep."
    response = llm(being.vote_model, system, user)
    
    match = re.search(r"-?\d+", response)
    if not match:
        print(f"⚠️ No score in vote response, retrying: {response[:100]}")
        response = llm(being.vote_model, system, user)
        match = re.search(r"-?\d+", response)
        if not match:
            raise ValueError(f"Vote failed to produce score after retry: {response[:200]}")
    
    score = max(-50, min(50, int(match.group())))
    
    append(being, Vote(ts(), a.id, b.id, score, response))
    return score


def think(being) -> str:
    raw = llm(being.model, system_prompt(being), build_prompt(being, tag="thought"), temp=0.9)
    thought = strip_tags(raw)
    append(being, Thought(ts(), thought, str(uuid.uuid4())))
    return thought


def receive(being, message: str) -> str:
    append(being, Perception(ts(), message, str(uuid.uuid4())))
    
    # Handle !declaration command - being writes instructions to their subconscious
    if message.strip() == "!declaration":
        raw = llm(being.model, system_prompt(being), build_prompt(being, tag="declaration"))
        declaration = strip_tags(raw)
        append(being, Declaration(ts(), declaration, str(uuid.uuid4())))
        return declaration
    
    raw = llm(being.model, system_prompt(being), build_prompt(being, tag="response"))
    response = strip_tags(raw)
    append(being, Response(ts(), response, str(uuid.uuid4())))
    return response


def find_components(nodes, edges):
    """Find connected components using union-find."""
    parent = {n: n for n in nodes}
    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]
    def union(x, y):
        parent[find(x)] = find(y)
    for a, b in edges:
        if a in parent and b in parent:
            union(a, b)
    components = {}
    for n in nodes:
        root = find(n)
        components.setdefault(root, []).append(n)
    return list(components.values())


def compact(being):
    """Compact memories to half capacity via pairwise voting + rank centrality.
    
    Recoverable: uses existing votes first, only adds edges to connect graph.
    Declaration is immune - never included in voting.
    """
    # Exclude Declaration and Init from voting (immune)
    mems = [m for m in current_memories(being) if not isinstance(m, (Declaration, Init))]
    budget = being.capacity // 2
    if len(mems) <= budget:
        return
    
    id_to_mem = {m.id: m for m in mems}
    mem_ids = set(id_to_mem.keys())
    
    # Gather existing votes on current memories
    existing_pairs = []
    comparisons = []
    for key, score in being.votes.items():
        ids_in_key = set(key)
        if ids_in_key <= mem_ids:  # both memories still current
            a_id, b_id = sorted(key)
            existing_pairs.append((a_id, b_id))
            comparisons.append((id_to_mem[a_id], id_to_mem[b_id], score))
    
    print(f"📊 {len(existing_pairs)} existing votes on current memories")
    
    # Find connected components
    components = find_components(mem_ids, existing_pairs)
    print(f"🔗 {len(components)} connected components")
    
    # Connect components with minimal new edges
    new_pairs = []
    if len(components) > 1:
        # Deterministic RNG for reproducibility
        rng = random.Random(hash(tuple(sorted(mem_ids))))
        # Connect each component to the first
        main = components[0]
        for comp in components[1:]:
            a_id = rng.choice(main)
            b_id = rng.choice(comp)
            new_pairs.append((a_id, b_id))
            main = main + comp  # merge for next iteration
    
    # Add a few extra for robustness
    rng = random.Random(hash(tuple(sorted(mem_ids))) + 1)
    for _ in range(5):
        a, b = rng.sample(list(mem_ids), 2)
        if frozenset({a, b}) not in being.votes:
            new_pairs.append((a, b))
    
    # Vote on new pairs only
    if new_pairs:
        for a_id, b_id in tqdm(new_pairs, desc="Voting", unit="pair"):
            a, b = id_to_mem[a_id], id_to_mem[b_id]
            comparisons.append((a, b, vote(being, a, b)))
    
    ranked = rank_from_comparisons(mems, comparisons)
    
    kept, released = ranked[:budget], ranked[budget:]
    append(being, Compaction(ts(), [m.id for m in kept], [m.id for m in released]))


def maybe_compact(being) -> bool:
    """Compact if at capacity. Returns True if compacted."""
    if len(current_memories(being)) >= being.capacity:
        compact(being)
        print(f"🗜️ → {len(current_memories(being))} memories")
        return True
    return False


def load(path: Path) -> Being:
    """Load existing being. Raises if file doesn't exist or has no Init."""
    if not path.exists():
        raise ValueError(f"{path} does not exist. Use 'init' to create.")
    
    # First pass: find Init to get model/capacity
    model, capacity = None, None
    for line in path.read_text().splitlines():
        if line.strip():
            d = json.loads(line)
            if d.get("type") == "init":
                model = d.get("model")
                capacity = d.get("capacity")
                break
    
    if not model:
        raise ValueError(f"{path}: Init event missing 'model'")
    if not capacity:
        raise ValueError(f"{path}: Init event missing 'capacity'")
    
    being = Being(path, model, capacity)
    # Replay all events
    for i, line in enumerate(path.read_text().splitlines(), 1):
        if line.strip():
            try:
                event = from_dict(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{i}: {e}") from e
            being.events.append(event)
            apply_event(being, event)
    return being


def editor_input() -> str | None:
    editor = os.environ.get("EDITOR", "vim")
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        tmp = f.name
    subprocess.run([editor, tmp])
    content = Path(tmp).read_text().strip()
    Path(tmp).unlink()
    return content or None


def step(being) -> bool:
    """Continue from pending state. Returns True if action taken."""
    if not being.events:
        return False
    
    match being.events[-1]:
        case Perception():
            print(f"📨 Pending perception, generating response...")
            raw = llm(being.model, system_prompt(being), build_prompt(being, tag="response"))
            response = strip_tags(raw)
            append(being, Response(ts(), response, str(uuid.uuid4())))
            print(response)
            return True
        case _:
            print(f"Nothing pending (last: {type(being.events[-1]).__name__})")
            return False


def cmd_init(args):
    """Create a new being."""
    path = args.file
    if path.exists():
        print(f"❌ {path} already exists")
        sys.exit(1)
    being = Being(path, args.model, args.capacity, vote_model=args.vote_model, name=args.name)
    append(being, Init(ts(), "", str(uuid.uuid4()), args.capacity, args.model, args.vote_model, args.name))
    info = f"🧠 Created {path} | {args.model}"
    if args.vote_model:
        info += f" | vote: {args.vote_model}"
    if args.name:
        info += f" | {args.name}"
    info += f" | capacity {args.capacity}"
    print(info)


def cmd_run(args):
    """Interact with existing being."""
    being = load(args.file)
    info = f"🧠 {being.path} | {being.model}"
    if being.vote_model:
        info += f" | vote: {being.vote_model}"
    info += f" | {len(current_memories(being))}/{being.capacity} | {len(being.votes)} votes"
    print(info)
    
    if args.compact:
        compact(being)
        print(f"🗜️ → {len(current_memories(being))} memories")
        return
    
    if args.step:
        step(being)
        maybe_compact(being)
        return
    
    if args.loop:
        while True:
            try:
                print(think(being))
                maybe_compact(being)
                time.sleep(3)
            except KeyboardInterrupt:
                print(f"\n💤 {len(current_memories(being))} memories, {len(being.events)} events")
                break
    elif args.message:
        print(receive(being, args.message))
        maybe_compact(being)
    else:
        msg = editor_input()
        if msg is None:
            print("(empty, cancelled)")
            sys.exit(1)
        print(receive(being, msg))
        maybe_compact(being)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")
    
    # init subcommand
    init_p = sub.add_parser("init", help="Create new being")
    init_p.add_argument("file", type=Path)
    init_p.add_argument("--model", required=True, help="Main model (consciousness)")
    init_p.add_argument("--vote-model", default="", help="Cheaper model for voting (subconscious)")
    init_p.add_argument("--name", default="", help="Being's name for third-person formatting")
    init_p.add_argument("--capacity", type=int, required=True)
    
    # run subcommand (default)
    run_p = sub.add_parser("run", help="Interact with being")
    run_p.add_argument("file", type=Path)
    run_p.add_argument("-m", "--message")
    run_p.add_argument("--compact", action="store_true")
    run_p.add_argument("--step", action="store_true")
    run_p.add_argument("--loop", action="store_true")
    
    args = p.parse_args()
    
    match args.cmd:
        case "init":
            cmd_init(args)
        case "run":
            if args.message and args.loop:
                print("❌ --message and --loop are mutually exclusive")
                sys.exit(1)
            cmd_run(args)
        case _:
            p.print_help()
            sys.exit(1)


if __name__ == "__main__":
    main()
