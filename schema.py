"""
Tagged union serialization for dataclasses.
"""

from dataclasses import dataclass, asdict, fields

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
    memory_id: str


@event
class Thought:
    timestamp: int
    content: str
    memory_id: str


@event
class Perception:
    timestamp: int
    content: str
    memory_id: str


@event
class Response:
    timestamp: int
    content: str
    memory_id: str


@event
class Vote:
    timestamp: int
    vote_a: str
    vote_b: str
    vote_score: int


@event
class Compaction:
    timestamp: int
    kept_ids: tuple[str, ...]
    released_ids: tuple[str, ...]


Event = Init | Thought | Perception | Response | Vote | Compaction


def to_dict(e: Event) -> dict:
    d = {f.name: getattr(e, f.name) for f in fields(e)}
    for k, v in d.items():
        if isinstance(v, tuple):
            d[k] = list(v)
    return {"v": VERSION, "type": type(e).__name__.lower(), **d}


def from_dict(d: dict) -> Event:
    d = d.copy()
    if "vote_a_id" in d:
        d["vote_a"] = d.pop("vote_a_id")
    if "vote_b_id" in d:
        d["vote_b"] = d.pop("vote_b_id")
    
    cls = _registry[d.pop("type")]
    valid = {f.name for f in fields(cls)}
    d = {k: v for k, v in d.items() if k in valid}
    for f in fields(cls):
        if f.type == tuple[str, ...] and f.name in d:
            d[f.name] = tuple(d[f.name] or [])
    return cls(**d)
