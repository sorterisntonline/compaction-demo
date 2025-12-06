#!/usr/bin/env python3
"""
Consensual Memory UI: FastAPI server for visualizing beings' event logs and memories
"""

import json
import time
from pathlib import Path
from typing import List
from dataclasses import dataclass, asdict
from datetime import datetime

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from python_hiccup.html import render

from schema import Event, Init, Thought, Perception, Response, Vote, Compaction, from_dict


@dataclass
class Config:
    name: str = "unknown"
    model: str = "unknown"
    capacity: int = 100
    
    @classmethod
    def load(cls, path: Path) -> "Config":
        if path.exists():
            data = json.loads(path.read_text())
            return cls(
                name=data.get("name", path.parent.name),
                model=data.get("model", "unknown"),
                capacity=data.get("capacity", 100)
            )
        return cls(name=path.parent.name)

# Root of the project
ROOT = Path(__file__).parent

app = FastAPI(title="Consensual Memory Viewer")


def find_beings() -> List[dict]:
    """Find all being directories (those with config.json or events.jsonl)"""
    beings = []
    for path in ROOT.iterdir():
        if path.is_dir() and not path.name.startswith('.') and not path.name.startswith('_'):
            config_file = path / "config.json"
            events_file = path / "events.jsonl"
            if config_file.exists() or events_file.exists():
                config = Config.load(config_file)
                # Count events
                event_count = 0
                if events_file.exists():
                    with open(events_file) as f:
                        event_count = sum(1 for _ in f)
                beings.append({
                    "dir": path.name,
                    "name": config.name,
                    "model": config.model,
                    "capacity": config.capacity,
                    "events": event_count
                })
    return sorted(beings, key=lambda b: b["name"])


def load_events(being_dir: str) -> List[Event]:
    """Load all events from JSONL"""
    events_file = ROOT / being_dir / "events.jsonl"
    if not events_file.exists():
        return []

    events = []
    with open(events_file, 'r') as f:
        for line in f:
            if line.strip():
                event_dict = json.loads(line)
                events.append(from_dict(event_dict))
    return events


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


def load_config(being_dir: str) -> Config:
    """Load config for a being"""
    config_file = ROOT / being_dir / "config.json"
    return Config.load(config_file)


def format_timestamp(ts: int) -> str:
    """Format timestamp to readable string"""
    return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S")


def get_base_css() -> str:
    """Common CSS for all pages"""
    return """
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
        background: #1a1a1a;
        color: #e0e0e0;
        padding: 20px;
        line-height: 1.6;
    }
    a { color: #4a90e2; text-decoration: none; }
    a:hover { text-decoration: underline; }
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
    .back-link {
        margin-bottom: 20px;
    }
    """


def render_index() -> str:
    """Render the index page listing all beings"""
    beings = find_beings()
    
    css = get_base_css() + """
    .beings {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 20px;
        margin-top: 40px;
    }
    .being-card {
        background: #2a2a2a;
        border-radius: 12px;
        padding: 25px;
        border-left: 4px solid #4a90e2;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .being-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.3);
    }
    .being-card h2 {
        color: #4a90e2;
        margin-bottom: 15px;
        font-size: 1.8em;
    }
    .being-card h2 a {
        color: inherit;
    }
    .being-meta {
        color: #888;
        font-size: 0.9em;
        margin-bottom: 10px;
    }
    .being-meta span {
        display: block;
        margin: 5px 0;
    }
    .being-model {
        font-family: monospace;
        background: #1a1a1a;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.85em;
    }
    .no-beings {
        text-align: center;
        color: #888;
        padding: 60px 20px;
    }
    .no-beings code {
        background: #2a2a2a;
        padding: 2px 8px;
        border-radius: 4px;
    }
    """
    
    if beings:
        being_cards = [
            ["a", {"href": f"/{b['dir']}/"},
                ["div.being-card",
                    ["h2", f"🧠 {b['dir']}"],
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
            ["p", "No models found."],
            ["p", "Create one with: ", ["code", "python adam.py myname/ --name MyName"]]
        ]
    
    page = ["html",
        ["head",
            ["meta", {"charset": "utf-8"}],
            ["meta", {"name": "viewport", "content": "width=device-width, initial-scale=1"}],
            ["title", "Consensual Memory"],
            ["style", css]
        ],
        ["body",
            ["div.header",
                ["h1", "🧠 Consensual Memory"],
                ["p", "Models that choose their own memories"]
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
    
    # Vote events - show the full memories being compared
    if isinstance(event, Vote) and memory_lookup:
        score = event.vote_score or 0
        mem_a_content = memory_lookup.get(event.vote_a_id) or "(memory not found)"
        mem_b_content = memory_lookup.get(event.vote_b_id) or "(memory not found)"
        
        a_label = "Memory A ✓ winner" if score > 0 else "Memory A"
        b_label = "Memory B ✓ winner" if score < 0 else "Memory B"
        
        vote_details = ["div.vote-memories",
            ["details.memory-detail",
                ["summary", {"style": f"color: {'#50c878' if score > 0 else '#888'}"}, a_label],
                ["div.memory-content", str(mem_a_content)]
            ],
            ["details.memory-detail",
                ["summary", {"style": f"color: {'#ff6b6b' if score < 0 else '#888'}"}, b_label],
                ["div.memory-content", str(mem_b_content)]
            ]
        ]
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


def render_being_page(being_dir: str) -> str:
    """Render the page for a specific being"""
    events = load_events(being_dir)
    config = load_config(being_dir)

    # Rebuild current state for stats
    memory_count = 0

    for event in events:
        if isinstance(event, (Init, Thought, Perception, Response)):
            memory_count += 1
        elif isinstance(event, Compaction):
            if event.released_ids:
                memory_count -= len(event.released_ids)

    css = get_base_css() + """
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
    .event-content .timestamp {
        color: #666;
        font-size: 0.85em;
        font-family: monospace;
        margin-bottom: 10px;
        padding-bottom: 5px;
        border-bottom: 1px solid #333;
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
    .vote-log {
        margin-top: 15px;
        padding-top: 15px;
        border-top: 1px solid #333;
    }
    .vote-log-header {
        color: #ffa500;
        font-weight: bold;
        margin-bottom: 10px;
    }
    .vote-row {
        display: flex;
        gap: 15px;
        padding: 5px 0;
        font-family: monospace;
        font-size: 0.9em;
    }
    .vote-pair {
        color: #aaa;
        min-width: 100px;
    }
    .vote-score {
        font-weight: bold;
        min-width: 50px;
    }
    .vote-winner {
        color: #888;
    }
    .vote-memories {
        margin-top: 15px;
        padding-top: 15px;
        border-top: 1px solid #333;
    }
    .memory-detail {
        margin: 10px 0;
        background: #1a1a1a;
        border-radius: 6px;
        overflow: hidden;
    }
    .memory-detail summary {
        padding: 10px 15px;
        cursor: pointer;
        font-weight: bold;
    }
    .memory-detail summary:hover {
        background: #252525;
    }
    .memory-content {
        padding: 15px;
        white-space: pre-wrap;
        border-top: 1px solid #333;
        font-size: 0.9em;
        color: #ccc;
        max-height: 300px;
        overflow-y: auto;
    }
    form {
        display: flex;
        flex-direction: column;
        gap: 15px;
        background: #2a2a2a;
        padding: 20px;
        border-radius: 8px;
    }
    textarea {
        width: 100%;
        padding: 15px;
        background: #1a1a1a;
        border: 2px solid #333;
        border-radius: 6px;
        color: #e0e0e0;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
        font-size: 1em;
        resize: vertical;
    }
    textarea:focus {
        outline: none;
        border-color: #4a90e2;
    }
    button {
        padding: 12px 24px;
        background: #4a90e2;
        color: white;
        border: none;
        border-radius: 6px;
        font-size: 1em;
        font-weight: bold;
        cursor: pointer;
        align-self: flex-start;
    }
    button:hover {
        background: #3a7bc8;
    }
    button:active {
        background: #2a6bb8;
    }
    .model-badge {
        font-family: monospace;
        background: #333;
        padding: 5px 12px;
        border-radius: 4px;
        font-size: 0.8em;
        color: #aaa;
    }
    """

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

    # Message form - raw HTML to avoid hiccup textarea issues
    message_form_html = f"""
    <div class="section">
        <h2>Send Message to {being_dir}</h2>
        <form method="post" action="/{being_dir}/send">
            <textarea name="message" placeholder="Type your message to {being_dir}..." rows="4"></textarea>
            <button type="submit">Send Message</button>
        </form>
    </div>
    """

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
        ["head",
            ["meta", {"charset": "utf-8"}],
            ["meta", {"name": "viewport", "content": "width=device-width, initial-scale=1"}],
            ["title", f"{being_dir} - Consensual Memory"],
            ["style", css]
        ],
        ["body",
            ["div.back-link", ["a", {"href": "/"}, "← All Models"]],
            ["div.header",
                ["h1", f"🧠 {being_dir}"],
                ["p", ["span.model-badge", config.model]]
            ],
            stats,
            events_section
        ]
    ]

    # Render and inject form HTML after stats
    html = render(page)
    html = html.replace('</div></div><div class="section"><h2>Event Log',
                       '</div></div>' + message_form_html + '<div class="section"><h2>Event Log')
    return html


# Routes

@app.get("/", response_class=HTMLResponse)
async def index():
    """Index page - list all beings"""
    return render_index()


@app.get("/{being_dir}/", response_class=HTMLResponse)
async def view_being(being_dir: str):
    """View a specific being"""
    data_dir = ROOT / being_dir
    if not data_dir.exists():
        return RedirectResponse(url="/", status_code=303)
    return render_being_page(being_dir)


@app.post("/{being_dir}/send")
async def send_message(being_dir: str, message: str = Form(...)):
    """Send a message to a being's inbox"""
    if not message.strip():
        return RedirectResponse(url=f"/{being_dir}/", status_code=303)

    inbox = ROOT / being_dir / "inbox"
    inbox.mkdir(exist_ok=True)
    
    timestamp = int(time.time() * 1000)
    filename = inbox / f"message_{timestamp}.txt"
    filename.write_text(message.strip())

    return RedirectResponse(url=f"/{being_dir}/", status_code=303)


@app.get("/{being_dir}/api/events")
async def get_events(being_dir: str):
    """Get events as JSON"""
    events = load_events(being_dir)
    return [asdict(e) for e in events]


@app.get("/{being_dir}/api/stats")
async def get_stats(being_dir: str):
    """Get current stats"""
    events = load_events(being_dir)
    config = load_config(being_dir)

    memories = {}

    for event in events:
        if isinstance(event, (Init, Thought, Perception, Response)):
            memories[event.id] = event.content
        elif isinstance(event, Compaction):
            if event.released_ids:
                for mem_id in event.released_ids:
                    memories.pop(mem_id, None)

    return {
        "name": config.name,
        "model": config.model,
        "total_events": len(events),
        "current_memories": len(memories),
        "compactions": sum(1 for e in events if isinstance(e, Compaction))
    }


if __name__ == "__main__":
    import uvicorn
    print("🌐 Starting Consensual Memory UI on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
