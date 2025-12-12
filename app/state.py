"""
Application state management using event sourcing
"""
import json
import time
from pathlib import Path
from typing import Dict, Any

from .events import AppEvent, AppInit, ColorConfigChanged, from_dict, to_dict


class AppState:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.being_colors: Dict[str, Dict[str, str]] = {}  # being_id -> {primary, secondary}
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
            
            case ColorConfigChanged(being_id=being_id, primary_color=primary, secondary_color=secondary):
                self.being_colors[being_id] = {
                    "primary": primary,
                    "secondary": secondary
                }
    
    def _append_event(self, event: AppEvent):
        """Append event to log and apply to materialized views"""
        with open(self.log_path, 'a') as f:
            f.write(json.dumps(to_dict(event)) + '\n')
        self._apply_event(event)
    
    def get_colors(self, being_id: str) -> Dict[str, str]:
        """Get colors for a being, with defaults"""
        return self.being_colors.get(being_id, {
            "primary": "#ccc",
            "secondary": "#888"
        })
    
    def update_colors(self, being_id: str, primary_color: str, secondary_color: str):
        """Update colors for a being"""
        event = ColorConfigChanged(
            timestamp=int(time.time() * 1000),
            being_id=being_id,
            primary_color=primary_color,
            secondary_color=secondary_color
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
