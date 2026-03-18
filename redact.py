#!/usr/bin/env python3
"""Remove the last message exchange (Perception + everything after) from a being."""
import json
import sys
from pathlib import Path

def redact(path: Path):
    lines = [l for l in path.read_text().splitlines() if l.strip()]

    # Find the last Perception
    last_perception_idx = None
    for i, line in enumerate(lines):
        d = json.loads(line)
        if d.get("type") in ("perception", "message"):
            last_perception_idx = i

    if last_perception_idx is None:
        print("No messages found.")
        return

    removed = lines[last_perception_idx:]
    kept = lines[:last_perception_idx]

    print(f"Removing {len(removed)} event(s):")
    for line in removed:
        d = json.loads(line)
        preview = d.get("content", "")[:80] or str(d)
        print(f"  [{d['type']}] {preview}")

    confirm = input("Redact? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return

    path.write_text("\n".join(kept) + "\n")
    print(f"Done. {path.name} now has {len(kept)} events.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python redact.py beings/ember.jsonl")
        sys.exit(1)
    redact(Path(sys.argv[1]))
