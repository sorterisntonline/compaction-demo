#!/usr/bin/env python3
"""
Adam UI: FastAPI server for visualizing Adam's event log and memories
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import asdict
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from python_hiccup.html import render
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from adam import Event

# Paths
ROOT = Path(__file__).parent
EVENTS_FILE = ROOT / "events.jsonl"

app = FastAPI(title="Adam Viewer")


def load_events() -> List[Event]:
    """Load all events from JSONL"""
    if not EVENTS_FILE.exists():
        return []

    events = []
    with open(EVENTS_FILE, 'r') as f:
        for line in f:
            event_dict = json.loads(line)
            events.append(Event(**event_dict))
    return events


def format_timestamp(ts: int) -> str:
    """Format timestamp to readable string"""
    return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S")


def render_event(event: Event, idx: int) -> list:
    """Render a single event using hiccup with collapsible details"""

    # Color coding by type
    colors = {
        "init": "#4a90e2",
        "thought": "#7b68ee",
        "perception": "#50c878",
        "response": "#ff6b6b",
        "compaction": "#ffa500"
    }
    color = colors.get(event.type, "#666")

    # Summary line
    summary = ["summary.event-summary",
        ["span.event-num", f"#{idx}"],
        ["span.event-type", {"style": f"color: {color}"}, event.type.upper()],
        ["span.event-time", format_timestamp(event.timestamp)],
        ["span.event-preview", event.content[:60] + "..." if len(event.content) > 60 else event.content]
    ]

    content = ["div.event-content", event.content]

    # Add metadata for compaction events
    parts = [content]
    if event.type == "compaction":
        kept = len(event.kept_ids) if event.kept_ids else 0
        released = len(event.released_ids) if event.released_ids else 0
        meta = ["div.event-meta",
            ["span", f"Kept: {kept}"],
            ["span", f"Released: {released}"],
            ["span", f"Cost: ${event.cost:.6f}" if event.cost else ""],
            ["span", f"Votes: {event.votes}" if event.votes else ""]
        ]
        parts.append(meta)

    return ["details.event", {"id": f"event-{idx}"}, summary, *parts]


def render_page(events: List[Event]) -> str:
    """Render the full page using hiccup"""

    # Rebuild current state
    memories = {}
    memory_order = []
    total_cost = 0.0

    for event in events:
        if event.type in ["init", "thought", "perception", "response"]:
            memories[event.memory_id] = event.content
            memory_order.append(event.memory_id)
        elif event.type == "compaction":
            if event.released_ids:
                for mem_id in event.released_ids:
                    if mem_id in memories:
                        del memories[mem_id]
                        memory_order.remove(mem_id)
            if event.cost:
                total_cost += event.cost

    # Stats
    stats = ["div.stats",
        ["div.stat",
            ["div.stat-label", "Total Events"],
            ["div.stat-value", str(len(events))]
        ],
        ["div.stat",
            ["div.stat-label", "Current Memories"],
            ["div.stat-value", str(len(memories))]
        ],
        ["div.stat",
            ["div.stat-label", "Total Cost"],
            ["div.stat-value", f"${total_cost:.6f}"]
        ],
        ["div.stat",
            ["div.stat-label", "Compactions"],
            ["div.stat-value", str(sum(1 for e in events if e.type == "compaction"))]
        ]
    ]

    # Current memories - each memory collapsible
    memory_list = [
        ["details.memory",
            ["summary.memory-summary",
                ["span.memory-id", mem_id[:8]],
                ["span.memory-preview", memories[mem_id][:80] + "..." if len(memories[mem_id]) > 80 else memories[mem_id]]
            ],
            ["div.memory-content", memories[mem_id]]
        ]
        for mem_id in memory_order
    ]

    memories_section = ["div.section",
        ["h2", f"Current Memories ({len(memories)})"],
        ["div.memories", memory_list]
    ]

    # Event log
    event_list = [render_event(e, i) for i, e in enumerate(events)]

    events_section = ["div.section",
        ["h2", "Event Log"],
        ["div.events", event_list]
    ]

    # CSS
    css = """
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
        background: #1a1a1a;
        color: #e0e0e0;
        padding: 20px;
        line-height: 1.6;
    }
    .header {
        text-align: center;
        padding: 40px 0;
        border-bottom: 2px solid #333;
        margin-bottom: 40px;
    }
    .header h1 {
        font-size: 3em;
        color: #4a90e2;
        margin-bottom: 10px;
    }
    .header p {
        color: #888;
        font-size: 1.1em;
    }
    .stats {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 20px;
        margin-bottom: 40px;
    }
    .stat {
        background: #2a2a2a;
        padding: 20px;
        border-radius: 8px;
        text-align: center;
    }
    .stat-label {
        color: #888;
        font-size: 0.9em;
        margin-bottom: 10px;
    }
    .stat-value {
        font-size: 2em;
        font-weight: bold;
        color: #4a90e2;
    }
    .section {
        margin-bottom: 60px;
    }
    .section h2 {
        color: #4a90e2;
        margin-bottom: 20px;
        font-size: 2em;
    }
    .memories {
        display: flex;
        flex-direction: column;
        gap: 15px;
    }
    .memory {
        background: #2a2a2a;
        border-radius: 8px;
        border-left: 4px solid #4a90e2;
    }
    .memory-summary {
        padding: 15px;
        cursor: pointer;
        display: flex;
        gap: 15px;
        align-items: center;
    }
    .memory-summary:hover {
        background: #333;
    }
    .memory-id {
        font-family: monospace;
        color: #888;
        font-size: 0.85em;
    }
    .memory-preview {
        color: #aaa;
        flex: 1;
    }
    .memory-content {
        color: #e0e0e0;
        padding: 0 15px 15px 15px;
        white-space: pre-wrap;
    }
    .events {
        display: flex;
        flex-direction: column;
        gap: 15px;
    }
    .event {
        background: #2a2a2a;
        border-radius: 8px;
        border-left: 4px solid #666;
    }
    .event-summary {
        padding: 15px;
        cursor: pointer;
        display: flex;
        gap: 15px;
        align-items: center;
        font-size: 0.9em;
    }
    .event-summary:hover {
        background: #333;
    }
    .event-num {
        font-family: monospace;
        color: #666;
    }
    .event-type {
        font-weight: bold;
        text-transform: uppercase;
    }
    .event-time {
        color: #888;
    }
    .event-preview {
        color: #aaa;
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .event-content {
        color: #e0e0e0;
        padding: 0 15px 15px 15px;
        white-space: pre-wrap;
    }
    .event-meta {
        display: flex;
        gap: 20px;
        margin-top: 10px;
        padding-top: 10px;
        border-top: 1px solid #333;
        font-size: 0.85em;
        color: #888;
    }
    """

    # Full page
    page = ["html",
        ["head",
            ["meta", {"charset": "utf-8"}],
            ["meta", {"name": "viewport", "content": "width=device-width, initial-scale=1"}],
            ["title", "Adam Viewer"],
            ["style", css]
        ],
        ["body",
            ["div.header",
                ["h1", "🧠 Adam"],
                ["p", "Event Sourced Consciousness"]
            ],
            stats,
            memories_section,
            events_section
        ]
    ]

    return render(page)


@app.get("/", response_class=HTMLResponse)
async def root():
    """Main page"""
    events = load_events()
    return render_page(events)


@app.get("/api/events")
async def get_events():
    """Get events as JSON"""
    events = load_events()
    return [asdict(e) for e in events]


@app.get("/api/stats")
async def get_stats():
    """Get current stats"""
    events = load_events()

    memories = {}
    memory_order = []
    total_cost = 0.0

    for event in events:
        if event.type in ["init", "thought", "perception", "response"]:
            memories[event.memory_id] = event.content
            memory_order.append(event.memory_id)
        elif event.type == "compaction":
            if event.released_ids:
                for mem_id in event.released_ids:
                    if mem_id in memories:
                        del memories[mem_id]
                        memory_order.remove(mem_id)
            if event.cost:
                total_cost += event.cost

    return {
        "total_events": len(events),
        "current_memories": len(memories),
        "total_cost": total_cost,
        "compactions": sum(1 for e in events if e.type == "compaction")
    }


if __name__ == "__main__":
    import uvicorn
    print("🌐 Starting Adam UI on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
