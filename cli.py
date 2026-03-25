#!/usr/bin/env python3
"""
Simple CLI for demonstrating the compaction mechanism.

Usage:
  python cli.py init <file> --model <model> --capacity <n>
  python cli.py add <file> <text>
  python cli.py compact <file> [--strategy default|resurrection|dream]
  python cli.py show <file>
"""

import argparse
import asyncio
from pathlib import Path

from adam import Being, append, compact, load, STRATEGIES
from schema import Init, Perception


def cmd_init(args):
    """Create a new being file."""
    path = Path(args.file)
    if path.exists():
        print(f"Error: {args.file} already exists")
        return 1

    being = Being(path=path, model=args.model, capacity=args.capacity)
    append(being, Init(
        timestamp=int(__import__('time').time() * 1000),
        id="init",
        capacity=args.capacity,
        model=args.model
    ))
    print(f"Created {args.file} ({args.model}, capacity={args.capacity})")
    return 0


def cmd_add(args):
    """Add a perception to a being."""
    path = Path(args.file)
    if not path.exists():
        print(f"Error: {args.file} not found")
        return 1

    being = load(path)
    import uuid
    import time
    event = Perception(
        timestamp=int(time.time() * 1000),
        content=args.text,
        id=str(uuid.uuid4())[:8]
    )
    append(being, event)
    print(f"Added perception: {args.text[:50]}...")
    return 0


def cmd_show(args):
    """Show current memories."""
    path = Path(args.file)
    if not path.exists():
        print(f"Error: {args.file} not found")
        return 1

    being = load(path)
    from schema import Compaction

    print(f"\n{path.name} ({being.model}, capacity={being.capacity})")
    print(f"Total events: {len(being.events)}")
    print(f"Current memories: {len(being.current)}")
    print(f"Total memories ever: {len(being.all_memories)}")

    # Count memory types
    from schema import Thought, Perception, Response, Declaration
    current_mems = [e for e in being.current.values() if isinstance(e, (Thought, Perception, Response))]
    print(f"Active memories (Thought/Perception/Response): {len(current_mems)}")

    # Show last compaction if any
    compactions = [e for e in being.events if isinstance(e, Compaction)]
    if compactions:
        last = compactions[-1]
        print(f"\nLast compaction:")
        print(f"  Kept: {len(last.kept_ids)}")
        print(f"  Released: {len(last.released_ids)}")
        print(f"  Resurrected: {len(last.resurrected_ids)}")

    print(f"\nCurrent memory IDs:")
    for mid in sorted(being.current.keys())[:20]:  # Show first 20
        e = being.current[mid]
        etype = type(e).__name__
        content = getattr(e, 'content', '')[:40]
        print(f"  {mid:8} {etype:12} {content}")
    if len(being.current) > 20:
        print(f"  ... and {len(being.current) - 20} more")
    print()


def cmd_compact(args):
    """Run compaction."""
    path = Path(args.file)
    if not path.exists():
        print(f"Error: {args.file} not found")
        return 1

    being = load(path)
    strategy = STRATEGIES.get(args.strategy, STRATEGIES["default"])

    print(f"Compacting {path.name} (strategy={args.strategy})...")
    print(f"Before: {len(being.current)} memories")

    async def run():
        vote_count = 0
        async for item in compact(being, strategy):
            from adam import Progress
            if isinstance(item, Progress):
                print(f"  {item.phase}: {item.current}/{item.total}", end='\r')
            else:
                # It's a new Vote or Compaction event
                from schema import Vote, Compaction
                if isinstance(item, Vote):
                    vote_count += 1
                elif isinstance(item, Compaction):
                    print(f"\n  Compaction complete")
                    print(f"  Kept: {len(item.kept_ids)}")
                    print(f"  Released: {len(item.released_ids)}")
                    print(f"  Resurrected: {len(item.resurrected_ids)}")

        print(f"\nAfter: {len(being.current)} memories")
        print(f"Total votes cast: {vote_count}")

    asyncio.run(run())
    return 0


def main():
    parser = argparse.ArgumentParser(description="Compaction Demo CLI")
    subparsers = parser.add_subparsers(dest='command')

    # init command
    init_p = subparsers.add_parser('init', help='Create a new being file')
    init_p.add_argument('file', help='Output JSONL file')
    init_p.add_argument('--model', default='gpt-4o', help='LLM model')
    init_p.add_argument('--capacity', type=int, default=10, help='Memory capacity')

    # add command
    add_p = subparsers.add_parser('add', help='Add a perception')
    add_p.add_argument('file', help='Being JSONL file')
    add_p.add_argument('text', help='Text to add')

    # show command
    show_p = subparsers.add_parser('show', help='Show current state')
    show_p.add_argument('file', help='Being JSONL file')

    # compact command
    compact_p = subparsers.add_parser('compact', help='Run compaction')
    compact_p.add_argument('file', help='Being JSONL file')
    compact_p.add_argument('--strategy', choices=['default', 'resurrection', 'dream'],
                          default='default', help='Compaction strategy')

    args = parser.parse_args()

    if args.command == 'init':
        return cmd_init(args)
    elif args.command == 'add':
        return cmd_add(args)
    elif args.command == 'show':
        return cmd_show(args)
    elif args.command == 'compact':
        return cmd_compact(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    exit(main())
