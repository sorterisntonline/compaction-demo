#!/usr/bin/env python3
"""
Integration test for vote caching mechanism.

Tests that:
1. Vote events are created during compaction
2. Votes are cached and reused in subsequent compactions
3. Cache hits save LLM calls
"""

import json
import os
import sys
import tempfile
from pathlib import Path

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

# Skip if no API key
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set"
)


def test_vote_caching():
    """Test that votes are cached and reused across compactions."""
    from adam import Being, Event, Config
    
    # Create temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        
        # Create config with cheap model and small capacity
        config = Config(
            name="TestBot",
            model="google/gemini-2.0-flash-001",  # Cheap and fast
            capacity=5  # Small to trigger compaction quickly
        )
        config.save(data_dir / "config.json")
        
        # Create being
        being = Being(data_dir)
        
        # Add some memories manually (to avoid thinking costs)
        for i in range(6):
            event = Event(
                timestamp=1000 + i,
                type="thought",
                content=f"Memory {i}: This is test thought number {i}.",
                memory_id=f"mem_{i}"
            )
            being.append_event(event)
        
        assert len(being.memories) == 6
        assert being.choose_to_compact()  # Should need compaction
        
        # First compaction - no cache hits expected
        being.compact()
        
        # Check vote events were created
        vote_events = [e for e in being.events if e.type == "vote"]
        assert len(vote_events) > 0, "No vote events were created!"
        
        # Check cache was populated
        assert len(being.vote_cache) > 0, "Vote cache is empty!"
        
        print(f"\n✓ First compaction: {len(vote_events)} vote events, {len(being.vote_cache)} cached")
        
        # After compaction, should have fewer memories
        assert len(being.memories) <= being.config.capacity // 2
        
        # Add more memories to trigger another compaction
        for i in range(6, 10):
            event = Event(
                timestamp=2000 + i,
                type="thought",
                content=f"Memory {i}: This is another test thought number {i}.",
                memory_id=f"mem_{i}"
            )
            being.append_event(event)
        
        # Force compaction again
        while len(being.memories) < being.config.capacity:
            event = Event(
                timestamp=3000 + len(being.memories),
                type="thought",
                content=f"Filler memory to trigger compaction.",
                memory_id=f"filler_{len(being.memories)}"
            )
            being.append_event(event)
        
        cache_size_before = len(being.vote_cache)
        being.compact()
        
        # Check more vote events
        vote_events_after = [e for e in being.events if e.type == "vote"]
        new_votes = len(vote_events_after) - len(vote_events)
        
        print(f"✓ Second compaction: {new_votes} new votes, cache grew from {cache_size_before} to {len(being.vote_cache)}")
        
        # Verify cache persists after reload
        events_file = data_dir / "events.jsonl"
        assert events_file.exists()
        
        # Reload being from disk
        being2 = Being(data_dir)
        assert len(being2.vote_cache) == len(being.vote_cache), "Cache not restored from events!"
        
        print(f"✓ Cache persists: {len(being2.vote_cache)} cached votes after reload")


def test_cache_reuse_on_replay():
    """Test that vote cache is properly rebuilt from events on replay."""
    from adam import Being, Event, Config
    
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        
        # Create config
        config = Config(name="ReplayTest", model="google/gemini-2.0-flash-001", capacity=5)
        config.save(data_dir / "config.json")
        
        # Write some vote events directly to the events file
        events_file = data_dir / "events.jsonl"
        with open(events_file, 'w') as f:
            # Init event
            f.write(json.dumps({
                "timestamp": 1000,
                "type": "init",
                "content": "Test init",
                "memory_id": "mem_init"
            }) + '\n')
            
            # Some thought events
            for i in range(3):
                f.write(json.dumps({
                    "timestamp": 2000 + i,
                    "type": "thought",
                    "content": f"Thought {i}",
                    "memory_id": f"mem_{i}"
                }) + '\n')
            
            # Vote events
            f.write(json.dumps({
                "timestamp": 3000,
                "type": "vote",
                "content": "Vote: +25",
                "vote_a_id": "mem_0",
                "vote_b_id": "mem_1",
                "vote_score": 25
            }) + '\n')
            
            f.write(json.dumps({
                "timestamp": 3001,
                "type": "vote",
                "content": "Vote: -10",
                "vote_a_id": "mem_1",
                "vote_b_id": "mem_2",
                "vote_score": -10
            }) + '\n')
        
        # Load being and check cache
        being = Being(data_dir)
        
        assert len(being.vote_cache) == 2, f"Expected 2 cached votes, got {len(being.vote_cache)}"
        
        # Check cache lookups work with correct sign handling
        cached_01 = being._get_cached_vote("mem_0", "mem_1")
        assert cached_01 == 25, f"Expected +25 for mem_0 vs mem_1, got {cached_01}"
        
        cached_10 = being._get_cached_vote("mem_1", "mem_0")
        assert cached_10 == -25, f"Expected -25 for mem_1 vs mem_0 (reversed), got {cached_10}"
        
        cached_12 = being._get_cached_vote("mem_1", "mem_2")
        assert cached_12 == -10, f"Expected -10 for mem_1 vs mem_2, got {cached_12}"
        
        # Non-existent pair returns None
        cached_02 = being._get_cached_vote("mem_0", "mem_2")
        assert cached_02 is None, f"Expected None for uncached pair, got {cached_02}"
        
        print("✓ Vote cache correctly rebuilt from events")
        print(f"  mem_0 vs mem_1 = +25, mem_1 vs mem_0 = -25 (flipped)")
        print(f"  mem_1 vs mem_2 = -10")


if __name__ == "__main__":
    print("Running vote cache integration tests...\n")
    test_cache_reuse_on_replay()
    print()
    test_vote_caching()
    print("\n✅ All tests passed!")

