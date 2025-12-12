"""
Tests for todo app example
"""
import tempfile
from pathlib import Path

from .todo_app import TodoApp, TodoState, todo_reducer, TodoCreated, TodoCompleted, TodoDeleted

def test_todo_reducer():
    """Test the todo reducer function"""
    initial_state = TodoState()
    
    # Create todo
    event1 = TodoCreated(timestamp=100, todo_id="1", text="Buy milk")
    state1 = todo_reducer(initial_state, event1)
    
    assert "1" in state1.todos
    assert state1.todos["1"] == "Buy milk"
    assert "1" not in state1.completed
    
    # Complete todo
    event2 = TodoCompleted(timestamp=200, todo_id="1")
    state2 = todo_reducer(state1, event2)
    
    assert "1" in state2.todos
    assert "1" in state2.completed
    
    # Delete todo
    event3 = TodoDeleted(timestamp=300, todo_id="1")
    state3 = todo_reducer(state2, event3)
    
    assert "1" not in state3.todos
    assert "1" not in state3.completed

def test_todo_app():
    """Test complete todo application"""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "todos.jsonl"
        app = TodoApp(log_path)
        
        # Start with empty state
        assert app.list_todos() == []
        assert app.get_stats() == {"total": 0, "completed": 0, "remaining": 0}
        
        # Create some todos
        app.create_todo("1", "Buy groceries")
        app.create_todo("2", "Walk the dog")
        app.create_todo("3", "Write tests")
        
        todos = app.list_todos()
        assert len(todos) == 3
        assert todos[0]["text"] == "Buy groceries"
        assert todos[0]["completed"] == False
        
        stats = app.get_stats()
        assert stats == {"total": 3, "completed": 0, "remaining": 3}
        
        # Complete a todo
        app.complete_todo("1")
        
        todos = app.list_todos()
        grocery_todo = next(t for t in todos if t["id"] == "1")
        assert grocery_todo["completed"] == True
        
        stats = app.get_stats()
        assert stats == {"total": 3, "completed": 1, "remaining": 2}
        
        # Delete a todo
        app.delete_todo("2")
        
        todos = app.list_todos()
        assert len(todos) == 2
        assert not any(t["id"] == "2" for t in todos)
        
        stats = app.get_stats()
        assert stats == {"total": 2, "completed": 1, "remaining": 1}

def test_todo_app_persistence():
    """Test that todo app state persists across restarts"""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "persist_todos.jsonl"
        
        # First app instance
        app1 = TodoApp(log_path)
        app1.create_todo("1", "Persistent todo")
        app1.complete_todo("1")
        
        stats1 = app1.get_stats()
        assert stats1 == {"total": 1, "completed": 1, "remaining": 0}
        
        # Second app instance - should rebuild state
        app2 = TodoApp(log_path)
        
        stats2 = app2.get_stats()
        assert stats2 == {"total": 1, "completed": 1, "remaining": 0}
        
        todos2 = app2.list_todos()
        assert len(todos2) == 1
        assert todos2[0]["text"] == "Persistent todo"
        assert todos2[0]["completed"] == True

def test_todo_app_multiple_operations():
    """Test complex sequence of operations"""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "complex_todos.jsonl"
        app = TodoApp(log_path)
        
        # Create many todos
        for i in range(10):
            app.create_todo(str(i), f"Todo {i}")
        
        assert app.get_stats() == {"total": 10, "completed": 0, "remaining": 10}
        
        # Complete every other one
        for i in range(0, 10, 2):
            app.complete_todo(str(i))
        
        assert app.get_stats() == {"total": 10, "completed": 5, "remaining": 5}
        
        # Delete completed ones
        for i in range(0, 10, 2):
            app.delete_todo(str(i))
        
        assert app.get_stats() == {"total": 5, "completed": 0, "remaining": 5}
        
        # Verify remaining todos
        todos = app.list_todos()
        remaining_ids = {t["id"] for t in todos}
        expected_ids = {"1", "3", "5", "7", "9"}
        assert remaining_ids == expected_ids
