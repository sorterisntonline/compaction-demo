"""
Event schema using algebraic data types.

Each event type is a distinct variant. The type field discriminates.
Serialization preserves the flat JSON structure for compatibility.
"""

from dataclasses import dataclass
from typing import Union

# Schema version - bump when structure changes
VERSION = 2


# === Event Variants ===

@dataclass(frozen=True, slots=True)
class Init:
    ts: int
    content: str
    memory_id: str

@dataclass(frozen=True, slots=True)
class Thought:
    ts: int
    content: str
    memory_id: str

@dataclass(frozen=True, slots=True)
class Perception:
    ts: int
    content: str
    memory_id: str

@dataclass(frozen=True, slots=True)
class Response:
    ts: int
    content: str
    memory_id: str

@dataclass(frozen=True, slots=True)
class Vote:
    ts: int
    a: str  # memory_id
    b: str  # memory_id
    score: int  # -50 to +50

@dataclass(frozen=True, slots=True)
class Compaction:
    ts: int
    kept: tuple[str, ...]
    released: tuple[str, ...]


# The sum type
Event = Init | Thought | Perception | Response | Vote | Compaction


# === Serialization ===

def to_dict(event: Event) -> dict:
    """Serialize event to flat dict for JSON."""
    match event:
        case Init(ts, content, mid):
            return {"v": VERSION, "type": "init", "timestamp": ts, 
                    "content": content, "memory_id": mid}
        case Thought(ts, content, mid):
            return {"v": VERSION, "type": "thought", "timestamp": ts,
                    "content": content, "memory_id": mid}
        case Perception(ts, content, mid):
            return {"v": VERSION, "type": "perception", "timestamp": ts,
                    "content": content, "memory_id": mid}
        case Response(ts, content, mid):
            return {"v": VERSION, "type": "response", "timestamp": ts,
                    "content": content, "memory_id": mid}
        case Vote(ts, a, b, score):
            return {"v": VERSION, "type": "vote", "timestamp": ts,
                    "vote_a": a, "vote_b": b, "vote_score": score}
        case Compaction(ts, kept, released):
            return {"v": VERSION, "type": "compaction", "timestamp": ts,
                    "kept_ids": list(kept), "released_ids": list(released)}


def from_dict(d: dict) -> Event:
    """Deserialize dict to event. Handles all schema versions."""
    # Migrate old formats first
    d = migrate(d)
    
    ts = d["timestamp"]
    match d["type"]:
        case "init":
            return Init(ts, d["content"], d["memory_id"])
        case "thought":
            return Thought(ts, d["content"], d["memory_id"])
        case "perception":
            return Perception(ts, d["content"], d["memory_id"])
        case "response":
            return Response(ts, d["content"], d["memory_id"])
        case "vote":
            return Vote(ts, d["vote_a"], d["vote_b"], d["vote_score"])
        case "compaction":
            return Compaction(ts, tuple(d.get("kept_ids", [])), 
                             tuple(d.get("released_ids", [])))
        case _:
            raise ValueError(f"Unknown event type: {d['type']}")


# === Migration ===

def migrate(d: dict) -> dict:
    """Migrate event dict to current schema version."""
    v = d.get("v", 1)
    
    # v1 -> v2: renamed fields, dropped cost/vote_log
    if v < 2:
        # Drop deprecated fields
        d.pop("cost", None)
        d.pop("vote_log", None)
        d.pop("votes", None)
        
        # Normalize vote fields (old format had vote_a_id, vote_b_id)
        if "vote_a_id" in d:
            d["vote_a"] = d.pop("vote_a_id")
        if "vote_b_id" in d:
            d["vote_b"] = d.pop("vote_b_id")
        
        d["v"] = 2
    
    return d

