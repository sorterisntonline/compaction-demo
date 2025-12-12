#!/usr/bin/env python3
"""
Import Anthropic chat JSON exports into consensual memory format.

Note: Anthropic exports only contain the active conversation path, not branches.
When you export from claude.ai, you get a linear message sequence representing
whichever branch was active when exported.
"""

import argparse
import json
import sys
from datetime import datetime
from schema import Init, Thought, Perception, Response, to_dict


def parse_timestamp(iso_str: str) -> int:
    """Convert ISO timestamp to Unix timestamp."""
    return int(datetime.fromisoformat(iso_str.replace('Z', '+00:00')).timestamp())


def extract_content(msg: dict) -> tuple[str, str | None]:
    """Extract text and optional thinking from message content."""
    thinking = None
    text = ""

    for block in msg.get('content', []):
        if block['type'] == 'thinking':
            thinking = block.get('thinking', '')
        elif block['type'] == 'text':
            text = block.get('text', '')

    return text, thinking


def convert_conversation(conv: dict, capacity: int = 100, model: str = "") -> list[dict]:
    """Convert Anthropic conversation to event stream."""
    messages = conv['chat_messages']

    if not messages:
        return []

    events = []

    # Init event from conversation metadata
    init_ts = parse_timestamp(conv['created_at'])
    events.append(to_dict(Init(
        timestamp=init_ts,
        id=conv['uuid'],
        capacity=capacity,
        model=model
    )))

    # Convert message stream
    for msg in messages:
        ts = parse_timestamp(msg['created_at'])
        msg_id = msg['uuid']
        text, thinking = extract_content(msg)

        if msg['sender'] == 'human':
            if text:  # Skip empty human messages
                events.append(to_dict(Perception(
                    timestamp=ts,
                    content=text,
                    id=msg_id
                )))
        else:  # assistant
            if thinking:
                events.append(to_dict(Thought(
                    timestamp=ts,
                    content=thinking,
                    id=f"{msg_id}-thinking"
                )))
            if text:
                events.append(to_dict(Response(
                    timestamp=ts,
                    content=text,
                    id=msg_id
                )))

    return events


def main():
    parser = argparse.ArgumentParser(
        description='Import Anthropic chat JSON exports into consensual memory JSONL format.'
    )
    parser.add_argument('input_file', help='JSON file exported from claude.ai')
    parser.add_argument('conversation_name', help='Name of conversation to import')
    parser.add_argument('--capacity', type=int, default=100, help='Memory capacity (default: 100)')
    parser.add_argument('--model', default='', help='Model identifier (default: empty)')

    args = parser.parse_args()

    # Load and find conversation
    with open(args.input_file) as f:
        data = json.load(f)

    conversation = None
    for conv in data:
        if conv.get('name') == args.conversation_name:
            conversation = conv
            break

    if not conversation:
        print(f"error: conversation '{args.conversation_name}' not found", file=sys.stderr)
        print(f"\navailable conversations:", file=sys.stderr)
        for conv in data:
            name = conv.get('name', '(unnamed)')
            if name:
                print(f"  - {name}", file=sys.stderr)
        sys.exit(1)

    # Convert and output
    events = convert_conversation(conversation, args.capacity, args.model)

    for event in events:
        print(json.dumps(event))


if __name__ == '__main__':
    main()
