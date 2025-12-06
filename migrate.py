#!/usr/bin/env python3
"""
Migrate event logs to current schema version.

Usage: python migrate.py <directory>
"""

import json
import sys
from pathlib import Path

from schema import from_dict, to_dict


def migrate(directory: Path):
    """Migrate events to current schema. Atomic: succeeds fully or not at all."""
    events_file = directory / "events.jsonl"
    if not events_file.exists():
        sys.exit(f"No events.jsonl in {directory}")
    
    # Parse all events (validates + migrates)
    events = []
    for i, line in enumerate(events_file.read_text().splitlines()):
        if not line.strip():
            continue
        try:
            events.append(from_dict(json.loads(line)))
        except Exception as e:
            sys.exit(f"Event {i}: {e}")
    
    # Write back in current format
    with open(events_file, 'w') as f:
        for event in events:
            f.write(json.dumps(to_dict(event)) + '\n')
    
    print(f"{directory.name}: {len(events)} events migrated")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python migrate.py <directory>")
    migrate(Path(sys.argv[1]))
