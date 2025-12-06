"""
Tagged union serialization for dataclasses.
"""

from dataclasses import dataclass, fields, asdict

VERSION = 2
_registry: dict[str, type] = {}


def event(cls):
    """Register a dataclass as an event variant."""
    _registry[cls.__name__.lower()] = cls
    return dataclass(frozen=True)(cls)


@event
class Init:
    timestamp: int
    content: str
    id: str
    capacity: int = 100  # default for backwards compatibility


@event
class Thought:
    timestamp: int
    content: str
    id: str


@event
class Perception:
    timestamp: int
    content: str
    id: str


@event
class Response:
    timestamp: int
    content: str
    id: str


@event
class Vote:
    timestamp: int
    vote_a_id: str
    vote_b_id: str
    vote_score: int


@event
class Compaction:
    timestamp: int
    kept_ids: list[str]
    released_ids: list[str]


Event = Init | Thought | Perception | Response | Vote | Compaction


def to_dict(e: Event) -> dict:
    return {"v": VERSION, "type": type(e).__name__.lower(), **asdict(e)}


def from_dict(d: dict) -> Event:
    # Migration: memory_id -> id
    if "memory_id" in d:
        d["id"] = d.pop("memory_id")
    cls = _registry[d["type"]]
    valid = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in d.items() if k in valid})
