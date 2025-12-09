#!/usr/bin/env python3
"""
Consensual Memory UI - Signed Snippets
"""

import json
import traceback
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from hiccup import render

from schema import Event, Init, Thought, Perception, Response, Declaration, Vote, Compaction, from_dict
from snippets import snippet_hidden, verify, consume_nonce, eval_snippet

ROOT = Path(__file__).parent
BEINGS_DIR = ROOT

app = FastAPI()
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


# === SNIPPET FUNCTIONS ===

def go(being_file: str, message: str = ''):
    """Send message if present, otherwise think."""
    from adam import load, receive, think
    being = load(BEINGS_DIR / f'{being_file}.jsonl')
    if message.strip():
        receive(being, message)
    else:
        think(being)
    return RedirectResponse(f'/{being_file}', status_code=303)


# Context for eval
CONTEXT = {'go': go}


# === HELPERS ===

def load_events(path: Path) -> list[Event]:
    if not path.exists():
        return []
    events = []
    with open(path) as f:
        for line in f:
            if line.strip():
                events.append(from_dict(json.loads(line)))
    return events


def find_beings() -> list[dict]:
    beings = []
    for path in BEINGS_DIR.glob("*.jsonl"):
        if path.name.startswith('.'):
            continue
        events = load_events(path)
        if not events:
            continue
        init = next((e for e in events if isinstance(e, Init)), None)
        if not init or not init.model:
            continue
        beings.append({
            "file": path.stem,
            "model": init.model,
            "capacity": init.capacity,
            "events": len(events)
        })
    return sorted(beings, key=lambda b: b["events"], reverse=True)


def ts_fmt(ts: int) -> str:
    return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S")


def head(title: str) -> list:
    return ["head",
        ["meta", {"charset": "utf-8"}],
        ["meta", {"name": "viewport", "content": "width=device-width, initial-scale=1"}],
        ["title", title],
        ["link", {"rel": "stylesheet", "href": "/static/style.css"}]
    ]


# === PAGES ===

def index_page() -> str:
    beings = find_beings()
    links = [
        ["a", {"href": f"/{b['file']}"}, f"{b['file']} ({b['model']}, {b['events']} events)"]
        for b in beings
    ] if beings else ["No beings found"]
    
    return render(["html", head("beings"), ["body", ["div.beings", *links]]])


def being_page(being_file: str) -> str:
    path = BEINGS_DIR / f"{being_file}.jsonl"
    events = load_events(path)
    init = next((e for e in events if isinstance(e, Init)), None)
    model = init.model if init else "?"
    
    # Stats
    mem_count = sum(1 for e in events if isinstance(e, (Init, Thought, Perception, Response, Declaration)))
    mem_count -= sum(len(e.released_ids) for e in events if isinstance(e, Compaction) and e.released_ids)
    vote_count = sum(1 for e in events if isinstance(e, Vote))
    
    # Top bar
    top = ["div.top-bar",
        ["a", {"href": "/"}, "←"], " ",
        f"{being_file} ({model}): {len(events)} events, {mem_count} memories, {vote_count} votes"
    ]
    
    # Form - one form, one button
    form = ["form", {"action": "/do", "method": "post"},
        *snippet_hidden(f"go('{being_file}', $message)"),
        ["textarea", {"name": "message", "rows": "8"}],
        ["button", "go"]
    ]
    
    # Events (newest first)
    def render_event(e, i):
        etype = type(e).__name__.lower()
        content = getattr(e, 'content', '') or ''
        preview = content[:80] + "..." if len(content) > 80 else content
        return ["details.event",
            ["summary",
                ["span.event-num", f"{i} "],
                ["span.event-type", f"{etype} "],
                ["span.event-time", f"{ts_fmt(e.timestamp)} "],
                ["span.event-preview", preview]
            ],
            ["div.event-content", content] if content else None
        ]
    
    event_list = [render_event(e, i) for i, e in enumerate(events)]
    event_list.reverse()
    
    return render(["html", head(being_file), ["body", top, form, ["div.events", event_list]]])


# === ROUTES ===

@app.exception_handler(Exception)
async def error_handler(request: Request, exc: Exception):
    return PlainTextResponse(f"Error\n\n{traceback.format_exc()}", status_code=500)


@app.get("/", response_class=HTMLResponse)
async def index():
    return index_page()


@app.get("/{being_file}", response_class=HTMLResponse)
async def view_being(being_file: str):
    if not (BEINGS_DIR / f"{being_file}.jsonl").exists():
        return RedirectResponse("/", status_code=303)
    return being_page(being_file)


@app.post("/do")
async def do(request: Request):
    form = await request.form()
    
    snippet = form.get('__snippet__', '')
    sig = form.get('__sig__', '')
    nonce = form.get('__nonce__', '')
    
    if not all([snippet, sig, nonce]):
        return PlainTextResponse("Missing fields", status_code=400)
    
    if not verify(snippet, nonce, sig):
        return PlainTextResponse("Invalid signature", status_code=403)
    
    if not consume_nonce(nonce):
        return PlainTextResponse("Invalid nonce", status_code=403)
    
    form_data = {k: str(v) for k, v in form.items() if not k.startswith('__')}
    
    try:
        return eval_snippet(snippet, form_data, CONTEXT)
    except Exception as e:
        return PlainTextResponse(str(e), status_code=500)


if __name__ == "__main__":
    import argparse
    import uvicorn
    
    parser = argparse.ArgumentParser()
    parser.add_argument("dir", type=Path, nargs="?", default=ROOT)
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    
    globals()['BEINGS_DIR'] = args.dir.resolve()
    
    print(f"http://localhost:{args.port}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)
