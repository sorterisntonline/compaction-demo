from dataclasses import dataclass, fields, asdict

VERSION = 2
_registry: dict[str, type] = {}


def event(cls):
    _registry[cls.__name__.lower()] = cls
    return dataclass(frozen=True)(cls)


@event
class Init:
    timestamp: int
    id: str
    capacity: int = 100
    model: str = ""
    vote_model: str = ""
    api_key: str = ""  # OpenRouter API key for this being


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
class Declaration:
    timestamp: int
    content: str
    id: str


@event
class Vote:
    timestamp: int
    vote_a_id: str
    vote_b_id: str
    vote_score: int
    reasoning: str = ""


@event
class Compaction:
    timestamp: int
    kept_ids: list[str]
    released_ids: list[str]


Event = Init | Thought | Perception | Response | Declaration | Vote | Compaction


def to_dict(e: Event) -> dict:
    return {"v": VERSION, "type": type(e).__name__.lower(), **asdict(e)}


def from_dict(d: dict) -> Event:
    if "memory_id" in d:
        d["id"] = d.pop("memory_id")
    cls = _registry[d["type"]]
    valid = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in d.items() if k in valid})
