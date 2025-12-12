"""
Test todo application using event sourcing
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List
from pathlib import Path

from event_store import event, EventStore

# Event definitions
@event
class TodoCreated:
    timestamp: int
    todo_id: str
    text: str

@event  
class TodoCompleted:
    timestamp: int
    todo_id: str

@event
class TodoDeleted:
    timestamp: int
    todo_id: str

# State definition
@dataclass
class TodoState:
    todos: Dict[str, str] = field(default_factory=dict)  # id -> text
    completed: set = field(default_factory=set)  # set of completed ids

# Reducer
def todo_reducer(state: TodoState, event) -> None:
    """Reduce events to build todo state"""
    match event:
        case TodoCreated(todo_id=todo_id, text=text):
            state.todos[todo_id] = text
            
        case TodoCompleted(todo_id=todo_id):
            state.completed.add(todo_id)
            
        case TodoDeleted(todo_id=todo_id):
            state.todos.pop(todo_id, None)
            state.completed.discard(todo_id)

# Todo app class
class TodoApp:
    def __init__(self, log_path: Path):
        initial_state = TodoState()
        self.store = EventStore(log_path, todo_reducer, initial_state)
    
    def create_todo(self, todo_id: str, text: str):
        event = TodoCreated(
            timestamp=int(time.time() * 1000),
            todo_id=todo_id,
            text=text
        )
        self.store.append(event)
    
    def complete_todo(self, todo_id: str):
        event = TodoCompleted(
            timestamp=int(time.time() * 1000), 
            todo_id=todo_id
        )
        self.store.append(event)
    
    def delete_todo(self, todo_id: str):
        event = TodoDeleted(
            timestamp=int(time.time() * 1000),
            todo_id=todo_id
        )
        self.store.append(event)
    
    def list_todos(self) -> List[Dict[str, str]]:
        state = self.store.state
        return [
            {
                "id": todo_id,
                "text": text,
                "completed": todo_id in state.completed
            }
            for todo_id, text in state.todos.items()
        ]
    
    def get_stats(self) -> Dict[str, int]:
        state = self.store.state
        total = len(state.todos)
        completed = len(state.completed)
        return {
            "total": total,
            "completed": completed,
            "remaining": total - completed
        }
