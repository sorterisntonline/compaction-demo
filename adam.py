#!/usr/bin/env python3

import json
import os
import random
import re
import time
import uuid

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

from rank import rank_from_comparisons
from schema import Init, Thought, Perception, Response, Declaration, Vote, Compaction, from_dict, to_dict

ROOT = Path(__file__).parent

load_dotenv()
API_KEY = os.getenv("OPENROUTER_API_KEY", "")
MOCK_LLM = os.getenv("MOCK_LLM", "")


def ts() -> int:
    return int(time.time() * 1000)


def current_memories(being):
    return sorted(being.current.values(), key=lambda e: e.timestamp)


@dataclass
class Being:
    path: Path
    model: str
    capacity: int
    events: list = field(default_factory=list)
    votes: dict = field(default_factory=dict)
    current: dict = field(default_factory=dict)
    all_memories: dict = field(default_factory=dict)
    vote_model: str = ""
    declaration: Declaration = None
    api_key: str = ""
    commands: object = None  # asyncio.Queue, set by web layer


@dataclass
class CompactionStrategy:
    continuity: float = 1.0
    resurrection: float = 0.0
    random: float = 0.0
    novelty: float = 0.0


STRATEGIES = {
    "default": CompactionStrategy(),
    "resurrection": CompactionStrategy(continuity=0.5, resurrection=0.3, novelty=0.2),
    "dream": CompactionStrategy(continuity=0.5, resurrection=0.2, random=0.1, novelty=0.2),
}


@dataclass
class Progress:
    current: int
    total: int
    phase: str


def apply_event(being, event):
    match event:
        case Vote(vote_a_id=a_id, vote_b_id=b_id, vote_score=score):
            low, high = sorted([a_id, b_id])
            normalized = score if a_id == low else -score
            being.votes[(low, high)] = normalized
        case Compaction(released_ids=released_ids, resurrected_ids=resurrected_ids):
            for rid in released_ids:
                if rid in being.current:
                    del being.current[rid]
            for rid in resurrected_ids:
                if rid in being.all_memories and rid not in being.current:
                    being.current[rid] = being.all_memories[rid]
        case Init(capacity=capacity, model=model):
            being.capacity = capacity
            being.model = model
            being.vote_model = event.vote_model
            being.current[event.id] = event
            being.all_memories[event.id] = event
        case Thought() | Perception() | Response():
            being.current[event.id] = event
            being.all_memories[event.id] = event
        case Declaration():
            being.current[event.id] = event
            being.all_memories[event.id] = event
            being.declaration = event


def system_prompt(being):
    if MOCK_LLM:
        return "You are a being with finite memory."
    codebase = ROOT / "repomix-output.xml"
    if not codebase.exists():
        raise FileNotFoundError("Run 'npx repomix' first")
    return f"You are a being with finite memory.\n\n{codebase.read_text()}"


def format_memory(e) -> str:
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
            return ""
        case _:
            raise ValueError(f"Unknown memory type: {type(e)}")


def build_prompt(being, tag: str = None) -> str:
    parts = [format_memory(e) for e in current_memories(being)]
    ctx = "\n\n".join(p for p in parts if p)
    prompt = f"{ctx}\n\n[{datetime.now():%Y-%m-%d %H:%M}]"
    if tag:
        prompt += f"\n\nSpeak only for yourself. One turn.\n\n<{tag}>"
    return prompt


def strip_tags(text: str) -> str:
    return re.sub(r"</?(?:thought|response|message|declaration)>", "", text).strip()


def append(being, event):
    with open(being.path, "a") as f:
        f.write(json.dumps(to_dict(event)) + "\n")
    being.events.append(event)
    apply_event(being, event)


_http_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=120.0)
    return _http_client


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def llm(model: str, system: str, user: str, temp: float = 0.7, api_key: str = "") -> str:
    if MOCK_LLM:
        tag = "thought" if "<thought>" in user else "response"
        return f"mock {tag} reply"

    key = api_key or API_KEY
    if not key:
        raise ValueError("No API key provided. Set OPENROUTER_API_KEY in .env or pass api_key to llm()")

    payload = {"model": model, "temperature": temp, "max_tokens": 4000,
               "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": user}]}

    r = await _get_client().post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json=payload,
    )
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"].strip()
    if not content:
        raise ValueError("LLM returned empty response")
    return content


async def vote(being, a, b) -> int:
    if not being.vote_model:
        raise ValueError(f"vote_model not set for {being.path}.")
    if not being.declaration:
        raise ValueError(f"No declaration for {being.path}. Being must write !declaration before compaction.")

    votes = being.votes
    low, high = sorted([a.id, b.id])
    key = (low, high)
    if key in votes:
        return votes[key] if a.id == low else -votes[key]

    mems = [m for m in current_memories(being) if not isinstance(m, (Declaration, Init, Vote, Compaction))]
    context = "\n\n".join(format_memory(m) for m in mems)

    user = f"""All memories currently under consideration:

{context}

---

Which of these two is more important to keep?

A: {format_memory(a)}

B: {format_memory(b)}

First, reason through which memory matters more.
Then, at the end, output your score:
  - POSITIVE (up to +50) if you prefer A
  - NEGATIVE (down to -50) if you prefer B"""

    response = await llm(being.vote_model, being.declaration.content, user, api_key=being.api_key)

    matches = re.findall(r"-?\d+", response)
    if not matches:
        print(f"⚠️ No score in response, retrying: {response[:100]}")
        response = await llm(being.vote_model, being.declaration.content, user, api_key=being.api_key)
        matches = re.findall(r"-?\d+", response)
        if not matches:
            raise ValueError(f"Vote failed to produce score after retry: {response[:200]}")

    score = max(-50, min(50, int(matches[-1])))

    append(being, Vote(ts(), a.id, b.id, score, response))
    return score


async def think(being):
    raw = await llm(being.model, system_prompt(being), build_prompt(being, tag="thought"),
              temp=0.9, api_key=being.api_key)
    thought = strip_tags(raw)
    event = Thought(ts(), thought, str(uuid.uuid4()))
    append(being, event)
    yield event


async def receive(being, message: str):
    perception = Perception(ts(), message, str(uuid.uuid4()))
    append(being, perception)
    yield perception

    raw = await llm(being.model, system_prompt(being), build_prompt(being, tag="response"),
              api_key=being.api_key)
    response = strip_tags(raw)
    if "!declaration" in response:
        declaration = response.replace("!declaration", "").strip()
        event = Declaration(ts(), declaration, str(uuid.uuid4()))
        append(being, event)
        yield event
    else:
        event = Response(ts(), response, str(uuid.uuid4()))
        append(being, event)
        yield event


def find_components(nodes, edges):
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


def _weighted_sample(memories, k, id_to_rank, n):
    if not memories or k <= 0:
        return []
    k = min(k, len(memories))
    now = ts()
    weights = []
    for m in memories:
        rank_weight = 1.0 - (id_to_rank.get(m.id, n) / max(n, 1))
        burial_weight = min(1.0, (now - m.timestamp) / (365 * 24 * 3600 * 1000))
        weights.append(rank_weight + burial_weight + 0.01)
    chosen = []
    available = list(range(len(memories)))
    for _ in range(k):
        if not available:
            break
        w = [weights[i] for i in available]
        idx = random.choices(available, weights=w, k=1)[0]
        chosen.append(memories[idx])
        available.remove(idx)
    return chosen


async def compact(being, strategy=None):
    if strategy is None:
        strategy = STRATEGIES["default"]

    MEMORY_TYPES = (Thought, Perception, Response)

    current_mems = [m for m in current_memories(being) if isinstance(m, MEMORY_TYPES)]
    budget = being.capacity // 2
    if len(current_mems) <= budget:
        return

    current_ids = {m.id for m in current_mems}

    all_mems = [m for m in being.all_memories.values() if isinstance(m, MEMORY_TYPES)]
    all_id_to_mem = {m.id: m for m in all_mems}
    all_ids = set(all_id_to_mem.keys())

    existing_pairs = []
    comparisons = []
    for (low_id, high_id), score in being.votes.items():
        if low_id in all_ids and high_id in all_ids:
            existing_pairs.append((low_id, high_id))
            comparisons.append((all_id_to_mem[low_id], all_id_to_mem[high_id], score))

    components = find_components(all_ids, existing_pairs)

    new_pairs = []
    if len(components) > 1:
        comp_current = []
        for comp in components:
            current_in_comp = [m for m in comp if m in current_ids]
            if current_in_comp:
                comp_current.append(current_in_comp)

        if len(comp_current) > 1:
            main = comp_current[0]
            for comp in comp_current[1:]:
                for _ in range(min(3, len(comp), len(main))):
                    a_id = random.choice(main)
                    b_id = random.choice(comp)
                    new_pairs.append((a_id, b_id))
                main = main + comp

    num_random = max(20, len(current_ids) // 10)
    for _ in range(num_random):
        if len(current_ids) < 2:
            break
        a, b = random.sample(list(current_ids), 2)
        low, high = sorted([a, b])
        if (low, high) not in being.votes:
            new_pairs.append((a, b))

    if new_pairs:
        total = len(new_pairs)
        for i, (a_id, b_id) in enumerate(new_pairs):
            yield Progress(i + 1, total, "Voting")
            a, b = all_id_to_mem[a_id], all_id_to_mem[b_id]
            before = len(being.events)
            try:
                score = await vote(being, a, b)
                comparisons.append((a, b, score))
                if len(being.events) > before:
                    yield being.events[-1]  # the new Vote event
            except Exception as e:
                print(f"⚠️ Vote failed after retries, skipping: {e}")

    ranked_all = rank_from_comparisons(all_mems, comparisons)

    continuity_slots = int(budget * strategy.continuity)
    resurrection_slots = int(budget * strategy.resurrection)
    random_slots = int(budget * strategy.random)
    novelty_slots = budget - continuity_slots - resurrection_slots - random_slots

    id_to_rank = {m.id: i for i, m in enumerate(ranked_all)}
    released_pool = all_ids - current_ids

    ranked_current = [m for m in ranked_all if m.id in current_ids]
    continuity_picks = ranked_current[:continuity_slots]
    used_ids = {m.id for m in continuity_picks}

    ranked_released = [m for m in ranked_all if m.id in released_pool]
    resurrection_picks = ranked_released[:resurrection_slots]
    used_ids.update(m.id for m in resurrection_picks)

    remaining_released = [m for m in ranked_released if m.id not in used_ids]
    random_picks = _weighted_sample(remaining_released, random_slots, id_to_rank, len(ranked_all))
    used_ids.update(m.id for m in random_picks)

    recent_current = sorted(
        [m for m in current_mems if m.id not in used_ids],
        key=lambda m: m.timestamp, reverse=True,
    )
    novelty_picks = recent_current[:max(novelty_slots, 0)]
    used_ids.update(m.id for m in novelty_picks)

    kept = continuity_picks + novelty_picks
    resurrected = resurrection_picks + random_picks
    released = [m for m in current_mems if m.id not in used_ids]

    compaction_event = Compaction(
        ts(),
        kept_ids=[m.id for m in kept],
        released_ids=[m.id for m in released],
        resurrected_ids=[m.id for m in resurrected],
    )
    append(being, compaction_event)
    yield compaction_event


def load(path: Path) -> Being:
    if not path.exists():
        raise ValueError(f"{path} does not exist. Use 'init' to create.")

    model, capacity, vote_model, api_key = None, None, "", ""
    for line in path.read_text().splitlines():
        if line.strip():
            d = json.loads(line)
            if d.get("type") == "init":
                model = d.get("model")
                capacity = d.get("capacity")
                vote_model = d.get("vote_model", "")
                api_key = d.get("api_key", "")
                break

    if not model:
        raise ValueError(f"{path}: Init event missing 'model'")
    if not capacity:
        raise ValueError(f"{path}: Init event missing 'capacity'")

    being = Being(path, model, capacity, api_key=api_key, vote_model=vote_model)
    for i, line in enumerate(path.read_text().splitlines(), 1):
        if line.strip():
            try:
                event = from_dict(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{i}: {e}") from e
            being.events.append(event)
            apply_event(being, event)
    return being
