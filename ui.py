#!/usr/bin/env python3
"""
Consensual Memory UI: FastAPI server for visualizing beings' event logs and memories
"""

import json
from pathlib import Path
from typing import List
from dataclasses import asdict
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from python_hiccup.html import render

from schema import Event, Init, Thought, Perception, Response, Vote, Compaction, from_dict

# Root of the project
ROOT = Path(__file__).parent
BEINGS_DIR = ROOT  # Set via CLI

app = FastAPI(title="Consensual Memory Viewer")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


def find_beings() -> List[dict]:
    """Find all .jsonl files in beings directory"""
    beings = []
    for path in BEINGS_DIR.glob("*.jsonl"):
        if path.name.startswith('.'):
            continue
        events = load_events_from_path(path)
        if not events:
            continue
        # Get model/capacity from Init event
        init = next((e for e in events if isinstance(e, Init)), None)
        model = getattr(init, 'model', 'unknown') if init else 'unknown'
        capacity = getattr(init, 'capacity', 100) if init else 100
        beings.append({
            "file": path.stem,
            "path": path.name,
            "model": model or 'unknown',
            "capacity": capacity,
            "events": len(events)
        })
    return sorted(beings, key=lambda b: b["file"])


def load_events_from_path(path: Path) -> List[Event]:
    """Load all events from JSONL file"""
    if not path.exists():
        return []
    events = []
    with open(path, 'r') as f:
        for line in f:
            if line.strip():
                event_dict = json.loads(line)
                events.append(from_dict(event_dict))
    return events


def load_events(being_file: str) -> List[Event]:
    """Load events by filename"""
    return load_events_from_path(ROOT / being_file)


def event_type(event: Event) -> str:
    """Get event type as string."""
    return type(event).__name__.lower()


def event_content(event: Event) -> str:
    """Get event content if it has one."""
    if hasattr(event, 'content'):
        return event.content
    return ""


def event_id(event: Event) -> str:
    """Get event id if it has one."""
    if hasattr(event, 'id'):
        return event.id
    return ""


def format_timestamp(ts: int) -> str:
    """Format timestamp to readable string"""
    return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S")


def html_head(title: str) -> list:
    """Common HTML head with external CSS."""
    return ["head",
        ["meta", {"charset": "utf-8"}],
        ["meta", {"name": "viewport", "content": "width=device-width, initial-scale=1"}],
        ["title", title],
        ["link", {"rel": "stylesheet", "href": "/static/style.css"}]
    ]


def render_index() -> str:
    """Render the index page listing all beings"""
    beings = find_beings()
    
    if beings:
        being_cards = [
            ["a", {"href": f"/{b['file']}"},
                ["div.being-card",
                    ["h2", f"🧠 {b['file']}"],
                    ["div.being-meta",
                        ["span", ["span.being-model", b['model']]],
                        ["span", f"📊 {b['events']} events | capacity {b['capacity']}"]
                    ]
                ]
            ]
            for b in beings
        ]
        content = ["div.beings", *being_cards]
    else:
        content = ["div.no-beings",
            ["p", "No beings found."],
            ["p", "Create one with: ", ["code", "python adam.py myname.jsonl"]]
        ]
    
    page = ["html",
        html_head("Consensual Memory"),
        ["body",
            ["div.header",
                ["h1", "🧠 Consensual Memory"],
                ["p", "Beings that choose their own memories"]
            ],
            content
        ]
    ]
    
    return render(page)


def render_event(event: Event, idx: int, memory_lookup: dict = None) -> list:
    """Render a single event using hiccup with collapsible details"""

    colors = {
        "init": "#4a90e2",
        "thought": "#7b68ee",
        "perception": "#50c878",
        "response": "#ff6b6b",
        "compaction": "#ffa500",
        "vote": "#e066ff"
    }
    etype = event_type(event)
    color = colors.get(etype, "#666")
    
    content_text = event_content(event) or "(empty)"
    preview = content_text[:60] + "..." if len(content_text) > 60 else content_text

    summary = ["summary.event-summary",
        ["span.event-num", f"#{idx}"],
        ["span.event-type", {"style": f"color: {color}"}, etype.upper()],
        ["span.event-time", format_timestamp(event.timestamp)],
        ["span.event-preview", preview]
    ]

    # Add timestamp to the content as well
    content_div = ["div.event-content",
        ["div.timestamp", format_timestamp(event.timestamp)],
        ["div", content_text]
    ]

    parts = [content_div]
    
    # Vote events - show reasoning and the memories being compared
    if isinstance(event, Vote) and memory_lookup:
        score = event.vote_score or 0
        reasoning = getattr(event, 'reasoning', '') or ''
        mem_a_content = memory_lookup.get(event.vote_a_id) or "(memory not found)"
        mem_b_content = memory_lookup.get(event.vote_b_id) or "(memory not found)"
        
        a_label = "Memory A ✓ winner" if score > 0 else "Memory A"
        b_label = "Memory B ✓ winner" if score < 0 else "Memory B"
        
        vote_details = ["div.vote-memories",
            ["div.vote-reasoning", reasoning] if reasoning else None,
            ["details.memory-detail",
                ["summary", {"style": f"color: {'#50c878' if score > 0 else '#888'}"}, a_label],
                ["div.memory-content", str(mem_a_content)]
            ],
            ["details.memory-detail",
                ["summary", {"style": f"color: {'#ff6b6b' if score < 0 else '#888'}"}, b_label],
                ["div.memory-content", str(mem_b_content)]
            ]
        ]
        # Filter out None
        vote_details = [x for x in vote_details if x is not None]
        parts.append(vote_details)
    
    if isinstance(event, Compaction):
        kept = len(event.kept_ids) if event.kept_ids else 0
        released = len(event.released_ids) if event.released_ids else 0

        meta = ["div.event-meta",
            ["span", f"Kept: {kept}"],
            ["span", f"Released: {released}"]
        ]
        parts.append(meta)

    return ["details.event", {"id": f"event-{idx}"}, summary, *parts]


def render_being_page(being_file: str) -> str:
    """Render the page for a specific being"""
    events = load_events(being_file + ".jsonl")
    init = next((e for e in events if isinstance(e, Init)), None)
    model = getattr(init, 'model', 'unknown') if init else 'unknown'

    # Rebuild current state for stats
    memory_count = 0

    for event in events:
        if isinstance(event, (Init, Thought, Perception, Response)):
            memory_count += 1
        elif isinstance(event, Compaction):
            if event.released_ids:
                memory_count -= len(event.released_ids)

    vote_count = sum(1 for e in events if isinstance(e, Vote))
    
    stats = ["div.stats",
        ["div.stat",
            ["div.stat-label", "Total Events"],
            ["div.stat-value", str(len(events))]
        ],
        ["div.stat",
            ["div.stat-label", "Current Memories"],
            ["div.stat-value", str(memory_count)]
        ],
        ["div.stat",
            ["div.stat-label", "Cached Votes"],
            ["div.stat-value", str(vote_count)]
        ],
        ["div.stat",
            ["div.stat-label", "Compactions"],
            ["div.stat-value", str(sum(1 for e in events if isinstance(e, Compaction)))]
        ]
    ]

    # Build memory lookup for vote events (id -> content)
    memory_lookup = {}
    for e in events:
        if isinstance(e, (Init, Thought, Perception, Response)):
            memory_lookup[e.id] = e.content

    # Reverse event list - newest first
    event_list = [render_event(e, i, memory_lookup) for i, e in enumerate(events)]
    event_list.reverse()

    events_section = ["div.section",
        ["h2", "Event Log"],
        ["div.events", event_list]
    ]

    page = ["html",
        html_head(f"{being_file} - Consensual Memory"),
        ["body",
            ["div.back-link", ["a", {"href": "/"}, "← All Beings"]],
            ["div.header",
                ["h1", f"🧠 {being_file}"],
                ["p", ["span.model-badge", model]]
            ],
            stats,
            events_section
        ]
    ]

    return render(page)


# Routes

@app.get("/", response_class=HTMLResponse)
async def index():
    """Index page - list all beings"""
    return render_index()


@app.get("/{being_file}", response_class=HTMLResponse)
async def view_being(being_file: str):
    """View a specific being"""
    events_path = ROOT / (being_file + ".jsonl")
    if not events_path.exists():
        return RedirectResponse(url="/", status_code=303)
    return render_being_page(being_file)


@app.get("/{being_file}/api/events")
async def get_events(being_file: str):
    """Get events as JSON"""
    events = load_events(being_file + ".jsonl")
    return [asdict(e) for e in events]


@app.get("/{being_file}/api/stats")
async def get_stats(being_file: str):
    """Get current stats"""
    events = load_events(being_file + ".jsonl")
    init = next((e for e in events if isinstance(e, Init)), None)
    model = getattr(init, 'model', 'unknown') if init else 'unknown'

    memories = {}

    for event in events:
        if isinstance(event, (Init, Thought, Perception, Response)):
            memories[event.id] = event.content
        elif isinstance(event, Compaction):
            if event.released_ids:
                for mem_id in event.released_ids:
                    memories.pop(mem_id, None)

    return {
        "file": being_file,
        "model": model,
        "total_events": len(events),
        "current_memories": len(memories),
        "compactions": sum(1 for e in events if isinstance(e, Compaction))
    }


if __name__ == "__main__":
    import argparse
    import uvicorn
    
    parser = argparse.ArgumentParser()
    parser.add_argument("dir", type=Path, nargs="?", default=ROOT, help="Directory containing .jsonl files")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    
    # Update module-level variable in this module's namespace
    import sys
    sys.modules[__name__].BEINGS_DIR = args.dir.resolve()
    
    print(f"🌐 Starting Consensual Memory UI on http://localhost:{args.port}")
    print(f"📁 Serving beings from {BEINGS_DIR}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)
