"""
Tests for event sourcing core functionality
"""
import pytest
import tempfile
from pathlib import Path
from dataclasses import dataclass

from event_store import event, append, replay, EventStore
from event_store.core import to_dict, from_dict

@event
class TestEvent:
    timestamp: int
    message: str
    count: int = 0

@event  
class AnotherEvent:
    timestamp: int
    value: str

def test_event_decorator():
    """Test that @event decorator registers events correctly"""
    from event_store.core import _registry
    
    assert 'testevent' in _registry
    assert _registry['testevent'] == TestEvent
    
    # Test event creation
    event_obj = TestEvent(timestamp=123, message="hello", count=5)
    assert event_obj.timestamp == 123
    assert event_obj.message == "hello"
    assert event_obj.count == 5

def test_to_dict_from_dict():
    """Test event serialization/deserialization"""
    event_obj = TestEvent(timestamp=456, message="world")
    
    # Test to_dict
    data = to_dict(event_obj)
    expected = {
        "type": "testevent",
        "timestamp": 456,
        "message": "world", 
        "count": 0
    }
    assert data == expected
    
    # Test from_dict
    reconstructed = from_dict(data)
    assert reconstructed == event_obj
    assert type(reconstructed) == TestEvent

def test_append_and_replay():
    """Test appending events to file and replaying them"""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test.jsonl"
        
        # Append some events
        event1 = TestEvent(timestamp=100, message="first")
        event2 = AnotherEvent(timestamp=200, value="second")
        event3 = TestEvent(timestamp=300, message="third", count=10)
        
        append(log_path, event1)
        append(log_path, event2)
        append(log_path, event3)
        
        # Replay events
        events = list(replay(log_path))
        
        assert len(events) == 3
        assert events[0] == event1
        assert events[1] == event2
        assert events[2] == event3

def test_empty_replay():
    """Test replaying from non-existent file"""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "nonexistent.jsonl"
        events = list(replay(log_path))
        assert events == []

@dataclass
class CountState:
    count: int = 0
    messages: list = None
    
    def __post_init__(self):
        if self.messages is None:
            self.messages = []

def count_reducer(state: CountState, event) -> CountState:
    new_state = CountState(
        count=state.count,
        messages=state.messages.copy()
    )
    
    match event:
        case TestEvent(message=msg, count=c):
            new_state.count += c
            new_state.messages.append(msg)
        case AnotherEvent(value=v):
            new_state.messages.append(f"another: {v}")
    
    return new_state

def test_event_store():
    """Test EventStore with state management"""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "store.jsonl"
        
        # Create store
        initial_state = CountState()
        store = EventStore(log_path, count_reducer, initial_state)
        
        # Initial state
        state = store.get_state()
        assert state.count == 0
        assert state.messages == []
        
        # Add some events
        store.append_event(TestEvent(timestamp=100, message="hello", count=5))
        store.append_event(AnotherEvent(timestamp=200, value="world"))
        store.append_event(TestEvent(timestamp=300, message="goodbye", count=3))
        
        # Check final state
        state = store.get_state()
        assert state.count == 8
        assert state.messages == ["hello", "another: world", "goodbye"]

def test_event_store_persistence():
    """Test that EventStore correctly rebuilds state from persisted events"""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "persist.jsonl"
        
        # Create first store and add events
        initial_state = CountState()
        store1 = EventStore(log_path, count_reducer, initial_state)
        
        store1.append_event(TestEvent(timestamp=100, message="first", count=10))
        store1.append_event(TestEvent(timestamp=200, message="second", count=20))
        
        state1 = store1.get_state()
        assert state1.count == 30
        assert state1.messages == ["first", "second"]
        
        # Create second store from same file - should rebuild state
        store2 = EventStore(log_path, count_reducer, CountState())
        
        state2 = store2.get_state()
        assert state2.count == 30
        assert state2.messages == ["first", "second"]
        
        # Add more events to second store
        store2.append_event(TestEvent(timestamp=300, message="third", count=5))
        
        state2_final = store2.get_state()
        assert state2_final.count == 35
        assert state2_final.messages == ["first", "second", "third"]

def test_unknown_event_type():
    """Test handling of unknown event types"""
    bad_data = {"type": "unknownevent", "timestamp": 123}
    
    with pytest.raises(ValueError, match="Unknown event type: unknownevent"):
        from_dict(bad_data)
