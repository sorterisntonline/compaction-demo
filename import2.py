#!/usr/bin/env python3
"""
Import Claude Exporter (claude-lumen) JSON exports into consensual memory format.

The Claude Exporter Chrome extension exports a single conversation per file with:
  - metadata: title, dates, link (contains UUID)
  - messages: [{role: "Prompt"|"Response", time: "M/D/YYYY, H:MM:SS AM/PM", say: "..."}]

Response "say" fields embed thinking as "Thought: ...\n\n\n" / "Tool: ...\n\n\n" prefixes.
"""

import argparse
import json
import re
import sys
import uuid
from datetime import datetime
from schema import Init, Thought, Perception, Response, to_dict


def parse_timestamp(time_str: str) -> int:
    """Convert 'M/D/YYYY, H:MM:SS AM/PM' or 'M/D/YYYY H:MM:SS' to Unix timestamp."""
    time_str = time_str.strip()
    for fmt in ("%m/%d/%Y, %I:%M:%S %p", "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M:%S"):
        try:
            return int(datetime.strptime(time_str, fmt).timestamp())
        except ValueError:
            continue
    raise ValueError(f"Cannot parse timestamp: {time_str!r}")


def extract_uuid_from_link(link: str) -> str:
    """Extract conversation UUID from a claude.ai chat URL."""
    m = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', link)
    return m.group(0) if m else str(uuid.uuid4())


def extract_response_parts(say: str) -> tuple[str, str | None]:
    """Split response say into (text, thinking).

    Responses from the exporter embed extended thinking as leading sections like:
      "Thought: ...\n\n\nTool: ...\n\n\nActual response text..."
    """
    sections = say.split('\n\n\n')
    thought_parts = []
    response_parts = []
    found_response = False

    for section in sections:
        stripped = section.strip()
        if not found_response and (stripped.startswith('Thought:') or stripped.startswith('Tool:')):
            thought_parts.append(stripped)
        else:
            found_response = True
            response_parts.append(section)

    thinking = '\n\n\n'.join(thought_parts) if thought_parts else None
    text = '\n\n\n'.join(response_parts).strip()
    return text, thinking


def convert_conversation(data: dict, capacity: int, model: str, vote_model: str) -> list[dict]:
    """Convert Claude Exporter JSON to event stream."""
    meta = data.get('metadata', {})
    messages = data.get('messages', [])

    if not messages:
        return []

    events = []

    # Init event
    created_str = meta.get('dates', {}).get('created', '')
    init_ts = parse_timestamp(created_str) if created_str else int(datetime.now().timestamp())
    conv_id = extract_uuid_from_link(meta.get('link', ''))

    events.append(to_dict(Init(
        timestamp=init_ts,
        id=conv_id,
        capacity=capacity,
        model=model,
        vote_model=vote_model,
    )))

    # Convert messages
    for i, msg in enumerate(messages):
        role = msg.get('role', '')
        say = msg.get('say', '')
        time_str = msg.get('time', '')
        ts = parse_timestamp(time_str) if time_str else init_ts
        msg_id = f"{conv_id}-{i}"

        if role == 'Prompt':
            if say.strip():
                events.append(to_dict(Perception(
                    timestamp=ts,
                    content=say,
                    id=msg_id,
                )))
        elif role == 'Response':
            text, thinking = extract_response_parts(say)
            if thinking:
                events.append(to_dict(Thought(
                    timestamp=ts,
                    content=thinking,
                    id=f"{msg_id}-thinking",
                )))
            if text:
                events.append(to_dict(Response(
                    timestamp=ts,
                    content=text,
                    id=msg_id,
                )))

    return events


def main():
    parser = argparse.ArgumentParser(
        description='Import Claude Exporter (claude-lumen) JSON into consensual memory JSONL format.'
    )
    parser.add_argument('input_file', help='JSON file exported by the Claude Exporter Chrome extension')
    parser.add_argument('--capacity', type=int, default=100, help='Memory capacity (default: 100)')
    parser.add_argument('--model', default='anthropic/claude-sonnet-4.6', help='Main model (default: anthropic/claude-sonnet-4.6)')
    parser.add_argument('--vote-model', default='google/gemini-3-flash-preview', help='Vote model (default: google/gemini-3-flash-preview)')

    args = parser.parse_args()

    with open(args.input_file) as f:
        data = json.load(f)

    events = convert_conversation(data, args.capacity, args.model, args.vote_model)

    for event in events:
        print(json.dumps(event))


if __name__ == '__main__':
    main()
