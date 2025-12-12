"""
Event sourcing library for immutable append-only logs
"""

from .core import event, EventStore
from .types import Event

__all__ = ['event', 'EventStore', 'Event']
