from dataclasses import dataclass, fields, asdict

VERSION = 1
_app_registry: dict[str, type] = {}


def app_event(cls):
    _app_registry[cls.__name__.lower()] = cls
    return dataclass(frozen=True)(cls)


@app_event
class AppInit:
    timestamp: int
    version: str = "0.1.0"


@app_event
class ConfigChanged:
    timestamp: int
    being_id: str
    key: str
    value: str  # JSON string for complex values


AppEvent = AppInit | ConfigChanged


def to_dict(e: AppEvent) -> dict:
    return {"v": VERSION, "type": type(e).__name__.lower(), **asdict(e)}


def from_dict(d: dict) -> AppEvent:
    cls = _app_registry[d["type"]]
    valid = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in d.items() if k in valid})
