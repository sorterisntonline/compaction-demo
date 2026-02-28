"""
Application state management using event sourcing
"""
import time
from pathlib import Path
from typing import Dict
from dataclasses import dataclass, field

from event_store import EventStore
from .events import AppInit, ConfigChanged

@dataclass  
class AppState:
    config: Dict[str, Dict[str, str]] = field(default_factory=dict)  # being_id -> {key: value}
    version: str = "0.1.0"

def app_reducer(state: AppState, event) -> None:
    """Reduce events to build app state"""
    match event:
        case AppInit(version=version):
            state.version = version
            
        case ConfigChanged(being_id=being_id, key=key, value=value):
            if being_id not in state.config:
                state.config[being_id] = {}
            state.config[being_id][key] = value

class AppStateManager:
    def __init__(self, log_path: Path):
        initial_state = AppState()
        self.store = EventStore(log_path, app_reducer, initial_state)
        
        # Initialize with AppInit if empty
        if not log_path.exists():
            self.store.append(AppInit(timestamp=int(time.time() * 1000)))
    
    def get_config(self, being_id: str, key: str, default: str = "") -> str:
        """Get config value for a being"""
        state = self.store.state
        return state.config.get(being_id, {}).get(key, default)
    
    def get_colors(self, being_id: str) -> Dict[str, str]:
        """Get colors for a being, with defaults"""
        return {
            "primary": self.get_config(being_id, "primary_color", "#ccc"),
            "secondary": self.get_config(being_id, "secondary_color", "#888")
        }

    def get_messaging(self, being_id: str) -> Dict[str, str]:
        """Get messaging handles for a being"""
        return {
            "phone": self.get_config(being_id, "phone", ""),
            "telegram": self.get_config(being_id, "telegram", ""),
            "signal": self.get_config(being_id, "signal", ""),
            "matrix": self.get_config(being_id, "matrix", ""),
        }
    
    def set_config(self, being_id: str, key: str, value: str):
        """Set config value for a being"""
        event = ConfigChanged(
            timestamp=int(time.time() * 1000),
            being_id=being_id,
            key=key,
            value=value
        )
        self.store.append(event)

# Global app state instance
_app_state = None

def get_app_state(log_path: Path = None) -> AppStateManager:
    """Get the global app state instance"""
    global _app_state
    if _app_state is None:
        if log_path is None:
            log_path = Path(__file__).parent.parent / "application.jsonl"
        _app_state = AppStateManager(log_path)
    return _app_state
