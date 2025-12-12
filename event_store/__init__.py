"""
Event sourcing library for immutable append-only logs
"""

from .core import event, append, replay, EventStore
from .types import Event

__all__ = ['event', 'append', 'replay', 'EventStore', 'Event']
