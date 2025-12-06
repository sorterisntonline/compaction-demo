#!/usr/bin/env python3
"""
Migrate event logs to current schema.

Usage: python migrate.py <dir> [output]
"""

import argparse
import json
from pathlib import Path

from schema import from_dict, to_dict


def migrate(src: Path, dst: Path = None):
    """Migrate events. In-place if dst is None."""
    dst = dst or src
    events_file = src / "events.jsonl"
    if not events_file.exists():
        raise SystemExit(f"No events.jsonl in {src}")
    
    # Parse all first (validate before writing)
    events = []
    for i, line in enumerate(events_file.read_text().splitlines()):
        if line.strip():
            try:
                events.append(from_dict(json.loads(line)))
            except Exception as e:
                raise SystemExit(f"Event {i}: {e}")
    
    # Write
    dst.mkdir(parents=True, exist_ok=True)
    with open(dst / "events.jsonl", 'w') as f:
        for e in events:
            f.write(json.dumps(to_dict(e)) + '\n')
    
    print(f"{len(events)} events migrated" + (f" → {dst}" if dst != src else ""))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("dir", type=Path)
    p.add_argument("output", type=Path, nargs="?")
    args = p.parse_args()
    migrate(args.dir, args.output)
