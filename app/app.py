#!/usr/bin/env python3
"""
Consensual Memory UI - Signed Snippets + poem.js
"""

import asyncio
import json
import hmac
import hashlib
import uuid
import time
import base64
import traceback
import os
import subprocess
import shutil
import threading
from pathlib import Path
from datetime import datetime

# Compaction progress: being_file -> {current, total, phase} or None when done
_compaction_progress: dict[str, dict | None] = {}
# Pending exec JS strings to push over SSE: being_file -> [js, ...]
_exec_queue: dict[str, list] = {}


def broadcast_exec(being_file: str, *js_strings: str):
    q = _exec_queue.setdefault(being_file, [])
    q.extend(js_strings)

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from app.hiccup import render, RawContent
from app.state import get_app_state
from app.patch import One, Three, Selector, Eval, MORPH
from schema import Event, Init, Thought, Perception, Response, Declaration, Vote, Compaction, from_dict

ROOT = Path(__file__).parent.parent
BEINGS_DIR = ROOT


# === AUTH (inside SSE stream) ===

def _auth_token() -> str:
    password = os.getenv("PASSWORD", "")
    return hashlib.sha256(f"auth|{password}".encode()).hexdigest() if password else ""

_authed_sessions: set[str] = set()

def _is_authed(request: Request, session_id: str) -> bool:
    token = _auth_token()
    if not token:
        return True
    if request.cookies.get("session") == token:
        return True
    return session_id in _authed_sessions

app = FastAPI()
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

SHELL_HTML = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body>
<script type="module">
import { Idiomorph } from 'https://unpkg.com/idiomorph@0.3.0/dist/idiomorph.esm.js';
window.Idiomorph = Idiomorph;
const ssePath = (location.pathname || '/').replace(/\\/$/, '') + '/sse';
const es = new EventSource(ssePath);
es.addEventListener('exec', e => eval(e.data));
document.addEventListener('submit', async e => {
  e.preventDefault();
  const f = e.target;
  await fetch(f.action, { method: 'POST', body: new URLSearchParams(new FormData(f)) });
  if (f.dataset.reset !== 'false') f.reset();
});
</script>
</body>
</html>"""

def get_css_hash() -> str:
    css_path = Path(__file__).parent / "static" / "style.css"
    if css_path.exists():
        return hashlib.sha256(css_path.read_bytes()).hexdigest()[:8]
    return "dev"

CSS_HASH = get_css_hash()


# === SIGNING ===

SECRET = hashlib.sha256(f"snippets-{uuid.uuid4()}".encode()).digest()
_nonces: dict[str, float] = {}
NONCE_TTL = 3600
_last_nonce_clean: float = 0.0


def _clean_nonces():
    # Rate-limit the scan to once per minute — calling this inside generate_nonce()
    # was O(|_nonces|) per call, making a page with thousands of events O(n²).
    global _last_nonce_clean
    now = time.time()
    if now - _last_nonce_clean < 60:
        return
    _last_nonce_clean = now
    for n in [n for n, exp in _nonces.items() if exp < now]:
        del _nonces[n]


def generate_nonce() -> str:
    _clean_nonces()
    nonce = uuid.uuid4().hex
    _nonces[nonce] = time.time() + NONCE_TTL
    return nonce


def consume_nonce(nonce: str) -> bool:
    _clean_nonces()
    if nonce in _nonces:
        del _nonces[nonce]
        return True
    return False


def sign(code: str, nonce: str) -> str:
    msg = f"{code}|{nonce}".encode()
    return base64.urlsafe_b64encode(hmac.new(SECRET, msg, hashlib.sha256).digest()).decode()


def verify(code: str, nonce: str, sig: str) -> bool:
    return hmac.compare_digest(sign(code, nonce), sig)


def scrub(value: str) -> str:
    return repr(value)


def snippet_hidden(code: str) -> list:
    nonce = generate_nonce()
    sig = sign(code, nonce)
    return [
        ["input", {"type": "hidden", "name": "__snippet__", "value": code}],
        ["input", {"type": "hidden", "name": "__sig__", "value": sig}],
        ["input", {"type": "hidden", "name": "__nonce__", "value": nonce}],
    ]


# === GIT CONFIG ===

DEFAULT_GIT_URL = "https://gitlab.com/thmorriss/family.git"

def git_config_path() -> Path:
    return BEINGS_DIR / ".git-config.json"

def load_git_config() -> dict:
    p = git_config_path()
    if p.exists():
        return json.loads(p.read_text())
    return {"url": DEFAULT_GIT_URL}

def save_git_config(url: str):
    git_config_path().write_text(json.dumps({"url": url}))
    return RedirectResponse("/git", status_code=303)


def login(password: str, session_id: str):
    """Called from signed snippet. Verifies password, marks session authed, sets cookie."""
    token = _auth_token()
    if not token:
        return PlainTextResponse("", status_code=204)
    if hashlib.sha256(f"auth|{password}".encode()).hexdigest() != token:
        return PlainTextResponse("", status_code=204)
    _authed_sessions.add(session_id)
    resp = PlainTextResponse("", status_code=204)
    resp.set_cookie("session", token, httponly=True, samesite="lax")
    return resp


# === SNIPPETS ===

def go(being_file: str, message: str = ''):
    from adam import load, receive, think
    being = load(BEINGS_DIR / f'{being_file}.jsonl')

    def run():
        if message.strip():
            receive(being, message)
        else:
            think(being)

    threading.Thread(target=run, daemon=True).start()
    return PlainTextResponse("", status_code=204)


def compact_async(being_file: str, strategy: str = "default"):
    from adam import load, compact, STRATEGIES

    path = BEINGS_DIR / f"{being_file}.jsonl"
    if not path.exists():
        return PlainTextResponse(f"Being {being_file} not found", status_code=404)
    being = load(path)
    if not being.declaration:
        return PlainTextResponse(
            f"No declaration. {being_file} must write !declaration before compaction.",
            status_code=400,
        )
    strategy_obj = STRATEGIES.get(strategy, STRATEGIES["default"])

    def run():
        try:
            def on_progress(current, total, phase):
                _compaction_progress[being_file] = {"current": current, "total": total, "phase": phase}

            _compaction_progress[being_file] = {"current": 0, "total": 1, "phase": "Starting"}
            compact(being, strategy_obj, on_progress=on_progress)
        finally:
            _compaction_progress.pop(being_file, None)

    threading.Thread(target=run, daemon=True).start()
    return PlainTextResponse("", status_code=204)


def redact(being_file: str):
    path = BEINGS_DIR / f'{being_file}.jsonl'
    lines = [l for l in path.read_text().splitlines() if l.strip()]
    last_idx = None
    for i, line in enumerate(lines):
        if json.loads(line).get('type') in ('perception', 'message'):
            last_idx = i
    if last_idx is None:
        return PlainTextResponse('Nothing to redact.', status_code=400)
    path.write_text('\n'.join(lines[:last_idx]) + '\n')
    return PlainTextResponse("", status_code=204)


def git_push():
    git = shutil.which('git')
    if not git:
        return PlainTextResponse('git not found', status_code=500)

    token = os.getenv('GITLAB_TOKEN', '')
    if not token:
        return PlainTextResponse('GITLAB_TOKEN not set', status_code=500)

    cfg = load_git_config()
    url = cfg['url']
    auth_url = url.replace('https://', f'https://oauth2:{token}@')

    d = str(BEINGS_DIR)
    def run(*args):
        return subprocess.run([git, '-C', d] + list(args), capture_output=True, text=True)

    if not (BEINGS_DIR / '.git').exists():
        run('init')
        run('config', 'user.email', 'app@fly.io')
        run('config', 'user.name', 'consensual-memory')
        (BEINGS_DIR / '.gitignore').write_text('logs/\n')

    run('add', '--all')
    result = run('commit', '-m', 'sync from fly.io')
    if result.returncode != 0 and 'nothing to commit' not in (result.stdout + result.stderr):
        return PlainTextResponse(f'commit failed:\n{result.stdout}\n{result.stderr}', status_code=500)

    result = run('push', auth_url, 'HEAD:fly-sync', '--force')
    if result.returncode != 0:
        return PlainTextResponse(f'push failed:\n{result.stdout}\n{result.stderr}', status_code=500)
    return PlainTextResponse(f'pushed to {url} (fly-sync)', status_code=200)


def update_config(being_file: str, **kwargs):
    app_state = get_app_state()
    for key, value in kwargs.items():
        if value:
            app_state.set_config(being_file, key, value)
    return PlainTextResponse("", status_code=204)


# === HELPERS ===

def load_events(path: Path) -> list[Event]:
    if not path.exists():
        return []
    events = []
    with open(path) as f:
        for line in f:
            if line.strip():
                event = from_dict(json.loads(line))
                if event is not None:
                    events.append(event)
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
        beings.append({"file": path.stem, "model": init.model, "capacity": init.capacity, "events": len(events)})
    return sorted(beings, key=lambda b: b["events"], reverse=True)


def ts_fmt(ts: int) -> str:
    return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S")


def _head_content(title: str) -> list:
    return ["head",
        ["meta", {"charset": "utf-8"}],
        ["meta", {"name": "viewport", "content": "width=device-width, initial-scale=1"}],
        ["title", title],
        ["link", {"rel": "stylesheet", "href": f"/static/style.css?v={CSS_HASH}"}],
    ]


# === RENDER HELPERS ===

def _mem_link(mid: str, memories: dict) -> list:
    """memories: {id: (index, event)}"""
    entry = memories.get(mid)
    if entry:
        idx, m = entry
        content = getattr(m, 'content', '') or ''
        preview = (content[:35] + "…") if content else mid[:8]
        label = f"#{idx} {preview}"
    else:
        label = mid[:8]
    return ["a", {"href": f"#evt-{mid}", "class": "mem-link"}, label]


def _event_body_html(e: Event, memories: dict) -> list | None:
    """Renders just the expandable body for an event (no <details> wrapper)."""
    match e:
        case Vote(reasoning=r) if r:
            return ["div.event-content", ["span.copy-btn", "⧉"], r]

        case Compaction():
            def sorted_ids(ids):
                return sorted(ids, key=lambda mid: memories[mid][0] if mid in memories else 9999)
            def section(label, ids):
                if not ids:
                    return None
                return ["div.compaction-section",
                    ["span.compaction-label", label],
                    *[_mem_link(mid, memories) for mid in sorted_ids(ids)],
                ]
            return ["div.event-content",
                section("kept", e.kept_ids),
                section("released", e.released_ids),
                section("resurrected", e.resurrected_ids),
            ]

        case _ if (content := getattr(e, 'content', '') or ''):
            return ["div.event-content", ["span.copy-btn", "⧉"], content]

        case _:
            return None


def render_event(e: Event, i: int, memories: dict = None, being_file: str = None) -> list:
    """Compact summary-only initial render.  Body loads lazily: the hidden expand
    form posts via fetch to /do; event_body() returns the HTML fragment directly."""
    memories = memories or {}
    etype = type(e).__name__.lower()
    eid = getattr(e, 'id', None)

    attrs = {"data-idx": str(i)}
    if eid:
        attrs["id"] = f"evt-{eid}"

    match e:
        case Vote():
            score_str = f"{e.vote_score:+d}"
            summary_body = ["span",
                _mem_link(e.vote_a_id, memories), f" {score_str} vs ",
                _mem_link(e.vote_b_id, memories),
            ]
        case Compaction():
            summary_body = ["span.event-preview",
                f"↓{len(e.released_ids)} kept {len(e.kept_ids)}"
                + (f" ↑{len(e.resurrected_ids)}" if e.resurrected_ids else "")]
        case _:
            content = getattr(e, 'content', '') or ''
            summary_body = ["span.event-preview", content[:80] + ("…" if len(content) > 80 else "")]

    has_body = _event_body_html(e, memories) is not None
    expand = (["form.expand-form", {"action": "/do", "method": "post"},
                   *snippet_hidden(f"event_body('{being_file}', {i})")] if has_body and being_file else None)

    return ["details.event", attrs,
        ["summary",
            ["span.event-num", f"{i} "],
            ["span.event-type", f"{etype} "],
            ["span.event-time", f"{ts_fmt(e.timestamp)} "],
            summary_body,
        ],
        expand,
    ]


def render_event_expanded(e: Event, i: int, memories: dict = None) -> list:
    """Full event render with body inline — used when morphing after lazy expand."""
    memories = memories or {}
    etype = type(e).__name__.lower()
    eid = getattr(e, 'id', None)
    attrs = {"data-idx": str(i), "open": ""}
    if eid:
        attrs["id"] = f"evt-{eid}"

    match e:
        case Vote():
            score_str = f"{e.vote_score:+d}"
            summary_body = ["span",
                _mem_link(e.vote_a_id, memories), f" {score_str} vs ",
                _mem_link(e.vote_b_id, memories),
            ]
        case Compaction():
            summary_body = ["span.event-preview",
                f"↓{len(e.released_ids)} kept {len(e.kept_ids)}"
                + (f" ↑{len(e.resurrected_ids)}" if e.resurrected_ids else "")]
        case _:
            content = getattr(e, 'content', '') or ''
            summary_body = ["span.event-preview", content[:80] + ("…" if len(content) > 80 else "")]

    body = _event_body_html(e, memories)
    return ["details.event", attrs,
        ["summary",
            ["span.event-num", f"{i} "],
            ["span.event-type", f"{etype} "],
            ["span.event-time", f"{ts_fmt(e.timestamp)} "],
            summary_body,
        ],
        body,
    ]


def event_body(being_file: str, idx: int):
    """/do snippet target: pushes event body via SSE exec, returns 204."""
    events = load_events(BEINGS_DIR / f"{being_file}.jsonl")
    if idx < 0 or idx >= len(events):
        return PlainTextResponse("", status_code=404)
    e = events[idx]
    eid = getattr(e, 'id', None)
    if not eid:
        return PlainTextResponse("", status_code=204)
    memories = {ev.id: (j, ev) for j, ev in enumerate(events) if getattr(ev, 'id', None)}
    body = _event_body_html(e, memories)
    if body is None:
        return PlainTextResponse("", status_code=204)
    broadcast_exec(being_file,
        Three[Selector(f"#evt-{eid}")][MORPH][render_event_expanded(e, idx, memories)],
    )
    return PlainTextResponse("", status_code=204)


def render_events_div(being_file: str) -> str:
    events = load_events(BEINGS_DIR / f"{being_file}.jsonl")
    memories = {e.id: (i, e) for i, e in enumerate(events) if getattr(e, 'id', None)}
    event_list = [render_event(e, i, memories, being_file) for i, e in enumerate(events)]
    event_list.reverse()
    return render(["div#events.events", event_list])


def exec_event(js: str) -> str:
    lines = ["event: exec"]
    for line in js.split('\n'):
        lines.append(f"data: {line}")
    lines += ["", ""]
    return "\n".join(lines)


def _push_initial_page(title: str, body_content: list):
    """Yield exec events to paint the full page."""
    yield exec_event(One[Eval(f"document.title = {json.dumps(title)}")])
    yield exec_event(Three[Selector("head")][MORPH][_head_content(title)])
    yield exec_event(Three[Selector("body")][MORPH][["body", body_content]])


async def _stream_auth_then_initial(request: Request, session_id: str, title: str, body_content: list):
    """Common SSE prelude: show login until authed, then paint the initial page."""
    while not _is_authed(request, session_id):
        for ev in _push_initial_page("login", _login_form(session_id)):
            yield ev
        await asyncio.sleep(1)
    for ev in _push_initial_page(title, body_content):
        yield ev


def render_progress_bar(current: int, total: int, phase: str) -> str:
    pct = int(100 * current / total) if total else 0
    return render(
        [
            "div#compaction-progress.compaction-progress",
            ["div.progress-bar", ["div.progress-fill", {"style": f"width: {pct}%"}]],
            ["span.progress-text", f"{phase} {current}/{total}"],
        ]
    )


# === CONTENT BUILDERS (body only, for SSE push) ===

def _login_form(session_id: str) -> list:
    return ["div.beings",
        ["form", {"action": "/do", "method": "post"},
            *snippet_hidden("login($password, $session_id)"),
            ["input", {"type": "hidden", "name": "session_id", "value": session_id}],
            ["input", {"type": "password", "name": "password", "placeholder": "password", "autofocus": "true"}],
            ["button", "enter"],
        ],
    ]


def index_content() -> list:
    beings = find_beings()
    links = []
    if beings:
        for b in beings:
            links.append(["div.being-row",
                ["a.being-link", {"href": f"/{b['file']}"}, f"{b['file']} ({b['model']}, {b['events']} events)"],
                " ",
                ["a.config-link", {"href": f"/{b['file']}/config"}, "config"]
            ])
    else:
        links = ["No beings found"]
    git_link = ["a.config-link", {"href": "/git"}, "git"]
    return ["div.beings", ["div.top-bar", git_link], *links]


def being_content(being_file: str) -> list:
    path = BEINGS_DIR / f"{being_file}.jsonl"
    events = load_events(path)
    init = next((e for e in events if isinstance(e, Init)), None)
    model = init.model if init else "?"

    mem_count = sum(1 for e in events if isinstance(e, (Init, Thought, Perception, Response, Declaration)))
    mem_count -= sum(len(e.released_ids) for e in events if isinstance(e, Compaction) and e.released_ids)
    vote_count = sum(1 for e in events if isinstance(e, Vote))

    top = ["div.top-bar",
        ["a", {"href": "/"}, "←"], " ",
        f"{being_file} ({model}): {len(events)} events, {mem_count} memories, {vote_count} votes"
    ]

    form = ["form", {"action": "/do", "method": "post"},
        *snippet_hidden(f"go('{being_file}', $message)"),
        ["textarea", {"name": "message", "rows": "8"}],
        ["button", "go"]
    ]

    redact_form = ["form", {"action": "/do", "method": "post", "style": "display:inline"},
        *snippet_hidden(f"redact('{being_file}')"),
        ["button", {"onclick": "return confirm('redact last message?')"}, "↩ redact"]
    ]

    push_form = ["form", {"action": "/do", "method": "post", "style": "display:inline"},
        *snippet_hidden("git_push()"),
        ["button", "⬆ push git"]
    ]

    compact_form = ["form", {"action": "/do", "method": "post", "style": "display:inline"},
        *snippet_hidden(f"compact_async('{being_file}', $strategy)"),
        ["select", {"name": "strategy"},
            ["option", {"value": "default"}, "default"],
            ["option", {"value": "resurrection"}, "resurrection"],
            ["option", {"value": "dream"}, "dream"],
        ],
        ["button", "🗜️ compact"]
    ]

    events_div = RawContent(render_events_div(being_file))

    return [
        top,
        ["div", redact_form, " ", push_form, " ", compact_form],
        ["div#compaction-progress.compaction-progress"],
        form,
        events_div,
    ]


def git_content() -> list:
    cfg = load_git_config()
    token_set = bool(os.getenv('GITLAB_TOKEN', ''))

    url_form = ["form", {"action": "/do", "method": "post"},
        *snippet_hidden("save_git_config($url)"),
        ["input", {"type": "url", "name": "url", "value": cfg['url'], "placeholder": "https://gitlab.com/user/repo.git"}],
        ["span.token-status", "token ✓" if token_set else "token ✗ (set GITLAB_TOKEN)"],
        ["button", "save"]
    ]

    push_form = ["form", {"action": "/do", "method": "post"},
        *snippet_hidden("git_push()"),
        ["button", "⬆ push git"]
    ]

    top = ["div.top-bar", ["a", {"href": "/"}, "←"], " git"]
    return [top, url_form, push_form]


def config_content(being_file: str) -> list:
    app_state = get_app_state()
    colors = app_state.get_colors(being_file)

    top = ["div.top-bar",
        ["a", {"href": "/"}, "←"], " ",
        ["a", {"href": f"/{being_file}"}, being_file], " config"
    ]

    form = ["form", {"action": "/do", "method": "post"},
        *snippet_hidden(f"update_config('{being_file}', primary_color=$primary_color, secondary_color=$secondary_color)"),
        ["div.config-section",
            ["label", "Primary Color:"],
            ["input", {"type": "color", "name": "primary_color", "value": colors["primary"]}]
        ],
        ["div.config-section",
            ["label", "Secondary Color:"],
            ["input", {"type": "color", "name": "secondary_color", "value": colors["secondary"]}]
        ],
        ["button", "save config"]
    ]

    return [top, form]


# === ROUTES ===

@app.exception_handler(Exception)
async def error_handler(request: Request, exc: Exception):
    return PlainTextResponse(f"Error\n\n{traceback.format_exc()}", status_code=500)


def _sse_headers():
    return {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@app.get("/sse")
async def sse_index(request: Request):
    """SSE for index page at /."""
    session_id = uuid.uuid4().hex

    async def generate():
        async for ev in _stream_auth_then_initial(request, session_id, "beings", index_content()):
            yield ev
        last_count = len(find_beings())
        while True:
            if await request.is_disconnected():
                break
            await asyncio.sleep(2)
            beings = find_beings()
            if len(beings) != last_count:
                last_count = len(beings)
                for ev in _push_initial_page("beings", index_content()):
                    yield ev

    return StreamingResponse(generate(), media_type="text/event-stream", headers=_sse_headers())


@app.get("/git/sse")
async def sse_git(request: Request):
    """SSE for git config page at /git."""
    session_id = uuid.uuid4().hex

    async def generate():
        async for ev in _stream_auth_then_initial(request, session_id, "git", git_content()):
            yield ev

    return StreamingResponse(generate(), media_type="text/event-stream", headers=_sse_headers())


@app.get("/{being_file}/config/sse")
async def sse_config(being_file: str, request: Request):
    """SSE for config page at /{being_file}/config."""
    if not (BEINGS_DIR / f"{being_file}.jsonl").exists():
        return PlainTextResponse("not found", status_code=404)
    session_id = uuid.uuid4().hex

    async def generate():
        async for ev in _stream_auth_then_initial(
            request, session_id, f"{being_file} config", config_content(being_file)
        ):
            yield ev

    return StreamingResponse(generate(), media_type="text/event-stream", headers=_sse_headers())


@app.get("/{being_file}/sse")
async def sse_being(being_file: str, request: Request):
    """SSE for being page at /{being_file}."""
    if being_file in ("git", "login", "do", "sse", "static"):
        return PlainTextResponse("not found", status_code=404)
    path = BEINGS_DIR / f"{being_file}.jsonl"
    if not path.exists():
        return PlainTextResponse("not found", status_code=404)
    session_id = uuid.uuid4().hex

    async def generate():
        async for ev in _stream_auth_then_initial(request, session_id, being_file, being_content(being_file)):
            yield ev

        last_mtime = 0.0
        last_progress = None
        while True:
            if await request.is_disconnected():
                break
            try:
                mtime = path.stat().st_mtime if path.exists() else 0.0
                if mtime != last_mtime:
                    last_mtime = mtime
                    html = render_events_div(being_file)
                    yield exec_event(Three[Selector("#events")][MORPH][html])

                progress = _compaction_progress.get(being_file)
                if progress != last_progress:
                    last_progress = progress
                    if progress:
                        bar_html = render_progress_bar(
                            progress["current"], progress["total"], progress["phase"]
                        )
                    else:
                        bar_html = render(["div#compaction-progress.compaction-progress"])
                    yield exec_event(Three[Selector("#compaction-progress")][MORPH][bar_html])

                queue = _exec_queue.pop(being_file, [])
                for js in queue:
                    yield exec_event(js)

            except Exception:
                pass
            await asyncio.sleep(0.15 if being_file in _compaction_progress else 1.0)

    return StreamingResponse(generate(), media_type="text/event-stream", headers=_sse_headers())


@app.get("/")
async def shell_root():
    return HTMLResponse(SHELL_HTML)


@app.get("/git")
async def shell_git():
    return HTMLResponse(SHELL_HTML)


@app.get("/{being_file}/config")
async def shell_config(being_file: str):
    if not (BEINGS_DIR / f"{being_file}.jsonl").exists():
        return PlainTextResponse("not found", status_code=404)
    return HTMLResponse(SHELL_HTML)


@app.get("/{being_file}")
async def shell_being(being_file: str):
    if being_file in ("git", "login", "do", "sse", "static"):
        return PlainTextResponse("not found", status_code=404)
    if not (BEINGS_DIR / f"{being_file}.jsonl").exists():
        return PlainTextResponse("not found", status_code=404)
    return HTMLResponse(SHELL_HTML)


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
    for key, value in form_data.items():
        snippet = snippet.replace(f'${key}', scrub(value))

    try:
        return eval(snippet)
    except Exception as e:
        return PlainTextResponse(str(e), status_code=500)


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("dir", type=Path, nargs="?", default=ROOT)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    globals()['BEINGS_DIR'] = args.dir.resolve()

    print(f"http://localhost:{args.port}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)
