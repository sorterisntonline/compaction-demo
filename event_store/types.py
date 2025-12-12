"""
Type definitions for event sourcing
"""
from typing import TypeVar, Protocol, Any, Dict, Callable

# Generic event type
Event = TypeVar('Event')

# State type  
State = TypeVar('State')

# Reducer function signature
Reducer = Callable[[State, Event], None]

class EventProtocol(Protocol):
    """Protocol that all events must implement"""
    timestamp: int
