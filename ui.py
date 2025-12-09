#!/usr/bin/env python3
"""
Consensual Memory UI: FastAPI server for visualizing beings' event logs and memories
"""

import json
from pathlib import Path
from typing import List
from dataclasses import asdict
from datetime import datetime

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from hiccup import render, RawContent
import traceback

from schema import Event, Init, Thought, Perception, Response, Declaration, Vote, Compaction, from_dict

# Root of the project
ROOT = Path(__file__).parent
BEINGS_DIR = ROOT  # Set via CLI

app = FastAPI(title="Consensual Memory Viewer")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Show full stack trace for any unhandled exception"""
    tb = traceback.format_exc()
    return PlainTextResponse(
        content=f"Internal Server Error\n\n{tb}",
        status_code=500
    )


def get_model(init: Init) -> str:
    """Get model from Init event, error if missing."""
    if init is None:
        raise ValueError("No Init event found")
    model = getattr(init, 'model', '')
    if not model:
        raise ValueError(f"Init event missing 'model' field")
    return model


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
        model = get_model(init)
        capacity = getattr(init, 'capacity', 100) if init else 100
        beings.append({
            "file": path.stem,
            "path": path.name,
            "model": model,
            "capacity": capacity,
            "events": len(events)
        })
    return sorted(beings, key=lambda b: b["events"], reverse=True)


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
    return load_events_from_path(BEINGS_DIR / being_file)


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




def load_script(filename: str) -> str:
    """Load a script snippet from snippets directory."""
    return (ROOT / "snippets" / filename).read_text()


def html_head(title: str) -> list:
    """Common HTML head."""
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
        being_links = [
            ["a", {"href": f"/{b['file']}"},
             f"{b['file']} ({b['model']}, {b['events']} events, {b['capacity']} capacity)"]
            for b in beings
        ]
        content = ["div.beings", *being_links]
    else:
        content = ["div.beings", "no beings"]
    
    page = ["html",
        html_head("beings"),
        ["body", content]
    ]
    
    return render(page)


def render_event(event: Event, idx: int, memory_lookup: dict = None) -> list:
    """Render a single event using hiccup with collapsible details"""

    etype = event_type(event)
    
    content_text = event_content(event) or "(empty)"
    preview = content_text[:80] + "..." if len(content_text) > 80 else content_text

    summary = ["summary.event-summary",
        ["span.event-num", f"{idx} "],
        ["span.event-type", f"{etype} "],
        ["span.event-time", f"{format_timestamp(event.timestamp)} "],
        ["span.event-preview", preview]
    ]

    content_div = ["div.event-content", content_text]

    parts = [content_div]
    
    # Vote events - show reasoning and the memories being compared
    if isinstance(event, Vote) and memory_lookup:
        score = event.vote_score or 0
        reasoning = getattr(event, 'reasoning', '') or ''
        mem_a_content = memory_lookup.get(event.vote_a_id) or "(memory not found)"
        mem_b_content = memory_lookup.get(event.vote_b_id) or "(memory not found)"
        
        a_label = "a (winner)" if score > 0 else "a"
        b_label = "b (winner)" if score < 0 else "b"
        
        vote_details = ["div.vote-memories",
            ["div.vote-reasoning", reasoning] if reasoning else None,
            ["details.memory-detail",
                ["summary", a_label],
                ["div.memory-content", str(mem_a_content)]
            ],
            ["details.memory-detail",
                ["summary", b_label],
                ["div.memory-content", str(mem_b_content)]
            ]
        ]
        # Filter out None
        vote_details = [x for x in vote_details if x is not None]
        parts.append(vote_details)
    
    if isinstance(event, Compaction):
        kept = len(event.kept_ids) if event.kept_ids else 0
        released = len(event.released_ids) if event.released_ids else 0

        meta = ["div.event-meta", f"kept {kept}, released {released}"]
        parts.append(meta)

    return ["details.event", {"id": f"event-{idx}"}, summary, *parts]


def render_being_page(being_file: str) -> str:
    """Render the page for a specific being"""
    events = load_events(being_file + ".jsonl")
    init = next((e for e in events if isinstance(e, Init)), None)
    model = get_model(init)

    # Rebuild current state for stats
    memory_count = 0

    for event in events:
        if isinstance(event, (Init, Thought, Perception, Response, Declaration)):
            memory_count += 1
        elif isinstance(event, Compaction):
            if event.released_ids:
                memory_count -= len(event.released_ids)

    vote_count = sum(1 for e in events if isinstance(e, Vote))
    compaction_count = sum(1 for e in events if isinstance(e, Compaction))
    
    # Single sentence stats
    stats_sentence = f"{being_file} ({model}): {len(events)} events, {memory_count} memories, {vote_count} votes, {compaction_count} compactions"
    
    top_bar = ["div.top-bar",
        ["span.back-link", ["a", {"href": "/"}, "←"], " "],
        ["span", stats_sentence]
    ]

    # Build memory lookup for vote events (id -> content)
    memory_lookup = {}
    for e in events:
        if isinstance(e, (Init, Thought, Perception, Response, Declaration)):
            memory_lookup[e.id] = e.content

    # Reverse event list - newest first
    event_list = [render_event(e, i, memory_lookup) for i, e in enumerate(events)]
    event_list.reverse()

    message_form = [
        ["form", {"action": f"/{being_file}/go", "method": "post"},
            ["textarea", {"name": "message", "placeholder": "", "rows": "8"}],
            ["button", {"type": "submit"}, "go"]
        ],
        ["script", RawContent(load_script("interactions.js"))]
    ]

    memories_link = ["div.memories-link",
        ["a", {"href": f"/{being_file}/memories"}, "view all memories →"]
    ]

    page = ["html",
        html_head(f"{being_file}"),
        ["body",
            top_bar,
            message_form,
            ["div.events", event_list],
            memories_link
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
    events_path = BEINGS_DIR / (being_file + ".jsonl")
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
    model = get_model(init)

    memories = {}

    for event in events:
        if isinstance(event, (Init, Thought, Perception, Response, Declaration)):
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


@app.post("/{being_file}/go", response_class=HTMLResponse)
async def go(being_file: str, message: str = Form("")):
    """Send message if text present, otherwise trigger thought"""
    from adam import load, receive, think
    
    events_path = BEINGS_DIR / (being_file + ".jsonl")
    if not events_path.exists():
        return RedirectResponse(url="/", status_code=303)
    
    being = load(events_path)
    if message.strip():
        receive(being, message)
    else:
        think(being)
    return RedirectResponse(url=f"/{being_file}", status_code=303)


def render_memories_page(being_file: str) -> str:
    """Render a page showing all memories (current + compacted) with different colors"""
    from adam import load
    from consensual_memory.rank import rank_from_comparisons
    
    events_path = BEINGS_DIR / (being_file + ".jsonl")
    being = load(events_path)
    
    # Get current memory IDs
    current_ids = set(being.current.keys())
    
    # Get all memories (Thought, Perception, Response only)
    all_mems = []
    for e in being.events:
        if isinstance(e, (Thought, Perception, Response)):
            all_mems.append(e)
    
    # Build comparisons from all votes
    id_to_mem = {m.id: m for m in all_mems}
    all_ids = set(id_to_mem.keys())
    edges = []
    comparisons = []
    for (low_id, high_id), score in being.votes.items():
        if low_id in id_to_mem and high_id in id_to_mem:
            edges.append((low_id, high_id))
            comparisons.append((id_to_mem[low_id], id_to_mem[high_id], score))
    
    # Find connected components - only rank the main one
    from adam import find_components
    components = find_components(all_ids, edges)
    components.sort(key=len, reverse=True)
    main_component = set(components[0]) if components else set()
    
    # Only include memories in the main connected component
    connected_mems = [m for m in all_mems if m.id in main_component]
    connected_comparisons = [(a, b, s) for a, b, s in comparisons 
                             if a.id in main_component and b.id in main_component]
    orphan_mems = [m for m in all_mems if m.id not in main_component]
    
    # Rank connected memories
    if connected_comparisons:
        ranked_mems = rank_from_comparisons(connected_mems, connected_comparisons)
    else:
        ranked_mems = sorted(connected_mems, key=lambda m: m.timestamp, reverse=True)
    
    # Sort orphans by timestamp
    orphan_mems.sort(key=lambda m: m.timestamp, reverse=True)
    
    # Count stats
    current_count = sum(1 for m in all_mems if m.id in current_ids)
    compacted_count = len(all_mems) - current_count
    budget = being.capacity // 2
    
    top_bar = ["div.top-bar",
        ["span.back-link", ["a", {"href": f"/{being_file}"}, "←"], " "],
        ["span", f"{being_file}: {len(all_mems)} total ({current_count} current, {compacted_count} compacted) | {len(connected_mems)} connected, {len(orphan_mems)} orphaned | budget: {budget}"]
    ]
    
    def render_memory(m, rank=None):
        is_current = m.id in current_ids
        status_class = "memory-current" if is_current else "memory-compacted"
        status_label = "current" if is_current else "compacted"
        mtype = type(m).__name__.lower()
        
        content_preview = m.content[:100] + "..." if len(m.content) > 100 else m.content
        
        rank_span = ["span.memory-rank", f"#{rank} "] if rank else ["span.memory-rank", "— "]
        
        return ["details", {"class": f"memory-item {status_class}"},
            ["summary",
                rank_span,
                ["span.memory-status", f"[{status_label}] "],
                ["span.memory-type", f"{mtype} "],
                ["span.memory-time", f"{format_timestamp(m.timestamp)} "],
                ["span.memory-preview", content_preview]
            ],
            ["div.memory-full", m.content],
            ["div.memory-id", f"id: {m.id[:8]}..."]
        ]
    
    # Render connected memories in rank order
    memory_list = []
    if ranked_mems:
        memory_list.append(["div.section-header", f"ranked ({len(ranked_mems)} in main component)"])
        for rank, m in enumerate(ranked_mems, 1):
            memory_list.append(render_memory(m, rank))
    
    # Render orphaned memories (not connected to main vote graph)
    if orphan_mems:
        memory_list.append(["div.section-header", f"orphaned ({len(orphan_mems)} disconnected from vote graph)"])
        for m in orphan_mems:
            memory_list.append(render_memory(m, None))
    
    page = ["html",
        html_head(f"{being_file} memories"),
        ["body",
            top_bar,
            ["div.memories-list", memory_list]
        ]
    ]
    
    return render(page)


@app.get("/{being_file}/memories", response_class=HTMLResponse)
async def view_memories(being_file: str):
    """View all memories for a being (current + compacted)"""
    events_path = BEINGS_DIR / (being_file + ".jsonl")
    if not events_path.exists():
        return RedirectResponse(url="/", status_code=303)
    return render_memories_page(being_file)


if __name__ == "__main__":
    import argparse
    import sys
    import uvicorn
    
    parser = argparse.ArgumentParser()
    parser.add_argument("dir", type=Path, nargs="?", default=ROOT, help="Directory containing .jsonl files")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    
    # Reassign module-level variable
    globals()['BEINGS_DIR'] = args.dir.resolve()
    
    print(f"🌐 Starting Consensual Memory UI on http://localhost:{args.port}")
    print(f"📁 Serving beings from {BEINGS_DIR}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)
