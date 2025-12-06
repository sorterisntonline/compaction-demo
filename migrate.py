#!/usr/bin/env python3
"""
Migration tool for consensual memory event logs.

Handles:
- Schema version upgrades
- Import from external formats (Claude GDPR export, etc.)
- Event log compaction/cleanup

Usage:
    python migrate.py upgrade <directory>     # Upgrade schema in place
    python migrate.py import-gdpr <export> <directory>  # Import GDPR export
    python migrate.py validate <directory>    # Check for issues
"""

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterator

from schema import Event, from_dict, to_dict, VERSION, migrate


def read_events(path: Path) -> Iterator[dict]:
    """Read events from JSONL file as raw dicts."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        if line.strip():
            yield json.loads(line)


def write_events(path: Path, events: list[dict]):
    """Write events to JSONL file."""
    with open(path, 'w') as f:
        for event in events:
            f.write(json.dumps(event) + '\n')


def upgrade_directory(directory: Path, dry_run: bool = False):
    """Upgrade all events in a directory to current schema."""
    events_file = directory / "events.jsonl"
    if not events_file.exists():
        print(f"No events.jsonl in {directory}")
        return
    
    # Read and migrate all events
    events = list(read_events(events_file))
    old_versions = set(e.get("v", 1) for e in events)
    
    migrated = [migrate(e) for e in events]
    new_versions = set(e.get("v", VERSION) for e in migrated)
    
    print(f"{directory.name}: {len(events)} events")
    print(f"  Versions: {old_versions} → {new_versions}")
    
    # Check what changed
    changes = sum(1 for old, new in zip(events, migrated) if old != new)
    print(f"  Changed: {changes} events")
    
    if dry_run:
        print("  (dry run, not writing)")
        return
    
    if changes > 0:
        # Backup
        backup = events_file.with_suffix('.jsonl.bak')
        shutil.copy(events_file, backup)
        print(f"  Backup: {backup}")
        
        # Write migrated
        write_events(events_file, migrated)
        print(f"  Written: {events_file}")


def validate_directory(directory: Path):
    """Validate events in a directory."""
    events_file = directory / "events.jsonl"
    if not events_file.exists():
        print(f"No events.jsonl in {directory}")
        return
    
    events = list(read_events(events_file))
    errors = []
    
    for i, e in enumerate(events):
        try:
            # Try to parse as proper Event
            parsed = from_dict(e)
        except Exception as ex:
            errors.append((i, str(ex)))
    
    print(f"{directory.name}: {len(events)} events, {len(errors)} errors")
    for i, err in errors[:10]:
        print(f"  Event {i}: {err}")
    if len(errors) > 10:
        print(f"  ... and {len(errors) - 10} more")


def import_gdpr_export(export_path: Path, directory: Path):
    """
    Import from Claude GDPR export format.
    
    GDPR exports have structure like:
    {
        "uuid": "...",
        "name": "Chat Name",
        "created_at": "2024-...",
        "updated_at": "2024-...",
        "chat_messages": [
            {"uuid": "...", "text": "...", "sender": "human|assistant", "created_at": "..."},
            ...
        ]
    }
    """
    directory.mkdir(exist_ok=True)
    (directory / "inbox").mkdir(exist_ok=True)
    
    # Load GDPR export
    with open(export_path) as f:
        data = json.load(f)
    
    events = []
    
    # Add init event
    created = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
    events.append({
        "v": VERSION,
        "type": "init",
        "timestamp": int(created.timestamp() * 1000),
        "content": f"Imported from: {data.get('name', 'Unknown')}",
        "memory_id": data["uuid"]
    })
    
    # Convert messages
    for msg in data.get("chat_messages", []):
        ts = datetime.fromisoformat(msg["created_at"].replace("Z", "+00:00"))
        
        if msg["sender"] == "human":
            event_type = "perception"
        else:
            event_type = "response"
        
        events.append({
            "v": VERSION,
            "type": event_type,
            "timestamp": int(ts.timestamp() * 1000),
            "content": msg["text"],
            "memory_id": msg["uuid"]
        })
    
    # Write
    events_file = directory / "events.jsonl"
    write_events(events_file, events)
    
    print(f"Imported {len(events)} events to {directory}")
    print(f"  Source: {data.get('name', 'Unknown')}")
    print(f"  Messages: {len(data.get('chat_messages', []))}")


def main():
    parser = argparse.ArgumentParser(description="Migrate consensual memory data")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # upgrade
    up = subparsers.add_parser("upgrade", help="Upgrade schema version")
    up.add_argument("directory", type=Path)
    up.add_argument("--dry-run", action="store_true")
    
    # validate
    val = subparsers.add_parser("validate", help="Validate events")
    val.add_argument("directory", type=Path)
    
    # import-gdpr
    imp = subparsers.add_parser("import-gdpr", help="Import GDPR export")
    imp.add_argument("export", type=Path, help="Path to GDPR JSON file")
    imp.add_argument("directory", type=Path, help="Target directory")
    
    args = parser.parse_args()
    
    match args.command:
        case "upgrade":
            upgrade_directory(args.directory, args.dry_run)
        case "validate":
            validate_directory(args.directory)
        case "import-gdpr":
            import_gdpr_export(args.export, args.directory)


if __name__ == "__main__":
    main()

