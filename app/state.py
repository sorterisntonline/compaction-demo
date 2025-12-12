"""
Application state management using event sourcing
"""
import json
import time
from pathlib import Path
from typing import Dict, Any

from .events import AppEvent, AppInit, ConfigChanged, from_dict, to_dict


class AppState:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.config: Dict[str, Dict[str, str]] = {}  # being_id -> {key: value}
        self.version = "0.1.0"
        
        self._replay_events()
    
    def _replay_events(self):
        """Replay all events from application.jsonl to build materialized views"""
        if not self.log_path.exists():
            # Initialize with AppInit event
            self._append_event(AppInit(timestamp=int(time.time() * 1000)))
            return
        
        with open(self.log_path) as f:
            for line in f:
                if line.strip():
                    event_dict = json.loads(line)
                    event = from_dict(event_dict)
                    self._apply_event(event)
    
    def _apply_event(self, event: AppEvent):
        """Apply a single event to update materialized views"""
        match event:
            case AppInit(version=version):
                self.version = version
            
            case ConfigChanged(being_id=being_id, key=key, value=value):
                if being_id not in self.config:
                    self.config[being_id] = {}
                self.config[being_id][key] = value
    
    def _append_event(self, event: AppEvent):
        """Append event to log and apply to materialized views"""
        with open(self.log_path, 'a') as f:
            f.write(json.dumps(to_dict(event)) + '\n')
        self._apply_event(event)
    
    def get_config(self, being_id: str, key: str, default: str = "") -> str:
        """Get config value for a being"""
        return self.config.get(being_id, {}).get(key, default)
    
    def get_colors(self, being_id: str) -> Dict[str, str]:
        """Get colors for a being, with defaults"""
        return {
            "primary": self.get_config(being_id, "primary_color", "#ccc"),
            "secondary": self.get_config(being_id, "secondary_color", "#888")
        }
    
    def set_config(self, being_id: str, key: str, value: str):
        """Set config value for a being"""
        event = ConfigChanged(
            timestamp=int(time.time() * 1000),
            being_id=being_id,
            key=key,
            value=value
        )
        self._append_event(event)


# Global app state instance
_app_state = None

def get_app_state(log_path: Path = None) -> AppState:
    """Get the global app state instance"""
    global _app_state
    if _app_state is None:
        if log_path is None:
            log_path = Path(__file__).parent / "application.jsonl"
        _app_state = AppState(log_path)
    return _app_state
