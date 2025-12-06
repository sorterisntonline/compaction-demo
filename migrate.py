#!/usr/bin/env python3
"""
Migrate event logs to current schema version.

Usage: python migrate.py <input> <output>
"""

import argparse
import json
from pathlib import Path

from schema import from_dict, to_dict


def migrate(src: Path, dst: Path):
    """Migrate events from src to dst. Never modifies source."""
    if src.resolve() == dst.resolve():
        raise SystemExit("Output must be different from input")
    
    events_file = src / "events.jsonl"
    if not events_file.exists():
        raise SystemExit(f"No events.jsonl in {src}")
    
    # Parse all events first (validates before writing anything)
    events = []
    for i, line in enumerate(events_file.read_text().splitlines()):
        if line.strip():
            try:
                events.append(from_dict(json.loads(line)))
            except Exception as e:
                raise SystemExit(f"Event {i}: {e}")
    
    # Write to destination
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "inbox").mkdir(exist_ok=True)
    
    with open(dst / "events.jsonl", 'w') as f:
        for event in events:
            f.write(json.dumps(to_dict(event)) + '\n')
    
    print(f"{len(events)} events: {src} → {dst}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Migrate events to current schema")
    p.add_argument("input", type=Path, help="Source directory")
    p.add_argument("output", type=Path, help="Destination directory (must be different)")
    args = p.parse_args()
    
    migrate(args.input, args.output)
