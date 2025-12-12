"""
Core event sourcing functionality
"""
import json
import time
from dataclasses import dataclass, fields, asdict
from pathlib import Path
from typing import TypeVar, Generic, Callable, Iterator, Any, Dict, Optional

from .types import Event, State, Reducer

# Global event registry
_registry: Dict[str, type] = {}

def event(cls):
    """Decorator to register event classes"""
    _registry[cls.__name__.lower()] = cls
    return dataclass(frozen=True)(cls)

def to_dict(e) -> Dict[str, Any]:
    """Convert event to dictionary"""
    return {"type": type(e).__name__.lower(), **asdict(e)}

def from_dict(d: Dict[str, Any]):
    """Convert dictionary to event"""
    event_type = d["type"]
    if event_type not in _registry:
        raise ValueError(f"Unknown event type: {event_type}")
    
    cls = _registry[event_type]
    valid_fields = {f.name for f in fields(cls)}
    kwargs = {k: v for k, v in d.items() if k in valid_fields}
    return cls(**kwargs)

def append(log_path: Path, event) -> None:
    """Append event to JSONL file"""
    with open(log_path, 'a') as f:
        f.write(json.dumps(to_dict(event)) + '\n')

def replay(log_path: Path) -> Iterator:
    """Replay events from JSONL file"""
    if not log_path.exists():
        return
    
    with open(log_path) as f:
        for line in f:
            if line.strip():
                event_dict = json.loads(line)
                yield from_dict(event_dict)

class EventStore(Generic[State]):
    """Generic event store with state management"""
    
    def __init__(self, log_path: Path, reducer: Reducer[State, Any], initial_state: State):
        self.log_path = log_path
        self.reducer = reducer
        self.state = initial_state
        
        self._replay_all()
    
    def _replay_all(self):
        """Replay all events to rebuild state"""
        for event in replay(self.log_path):
            self.state = self.reducer(self.state, event)
    
    def append_event(self, event) -> None:
        """Append event and update state"""
        append(self.log_path, event)
        self.state = self.reducer(self.state, event)
    
    def get_state(self) -> State:
        """Get current state"""
        return self.state
