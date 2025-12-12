"""
Core event sourcing functionality
"""
import json
from dataclasses import dataclass, fields, asdict
from pathlib import Path
from typing import TypeVar, Generic, Callable, Iterator, Any, Dict

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

@dataclass
class EventStore(Generic[State]):
    """Generic event store with state management"""
    log_path: Path
    reducer: Reducer[State, Any] 
    state: State
    
    def __post_init__(self):
        """Replay all events to rebuild state after initialization"""
        self._replay_all()
    
    def _replay(self) -> Iterator:
        """Replay events from JSONL file"""
        if not self.log_path.exists():
            return
        
        with open(self.log_path) as f:
            for line in f:
                if line.strip():
                    event_dict = json.loads(line)
                    yield from_dict(event_dict)
    
    def _replay_all(self):
        """Replay all events to rebuild state"""
        for event in self._replay():
            self.reducer(self.state, event)
    
    def append(self, event) -> None:
        """Append event to file and update state"""
        with open(self.log_path, 'a') as f:
            f.write(json.dumps(to_dict(event)) + '\n')
        self.reducer(self.state, event)
