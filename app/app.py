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
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from app.state import get_app_state, get_being, evict_being
from app.patch import One, Three, Four, Selector, Eval, MORPH, PREPEND, CLASSES, ADD, REMOVE
from schema import Event, Init, Thought, Perception, Response, Declaration, Vote, Compaction, from_dict
from adam import Progress, STRATEGIES

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
es.addEventListener('exec', e => {
  eval(e.data);
});
document.addEventListener('submit', async e => {
  e.preventDefault();
  const f = e.target;
  try {
    const r = await fetch(f.action, { method: 'POST', body: new URLSearchParams(new FormData(f)) });
    const t = await r.text();
    if (t) eval(t);
  } catch (err) {
    console.error(err);
  }
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


def apply_snippet_substitutions(snippet: str, form_data: dict[str, str]) -> str:
    """Replace $key placeholders; longest keys first so $idx is not broken by $id."""
    for key, value in sorted(form_data.items(), key=lambda x: len(x[0]), reverse=True):
        snippet = snippet.replace(f"${key}", scrub(value))
    return snippet


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
    token = _auth_token()
    if not token:
        return PlainTextResponse("", status_code=204)
    if hashlib.sha256(f"auth|{password}".encode()).hexdigest() != token:
        return PlainTextResponse("", status_code=204)
    _authed_sessions.add(session_id)
    resp = PlainTextResponse("", status_code=204)
    resp.set_cookie("session", token, httponly=True, samesite="lax")
    return resp


# === SNIPPETS (called from /do via signed eval) ===

def go(being_file: str, message: str = ''):
    being = get_being(being_file, BEINGS_DIR)
    if message.strip():
        being.commands.put_nowait(("receive", message))
    else:
        being.commands.put_nowait(("think",))
    js = Four[Selector('form.go-form button[type="submit"]')][CLASSES][ADD]['sending']
    return PlainTextResponse(str(js), status_code=200)


def copy_to_clipboard(being_file: str, idx: int):
    events = get_being(being_file, BEINGS_DIR).events
    if idx < 0 or idx >= len(events):
        return PlainTextResponse("", status_code=404)
    e = events[idx]
    text = _event_copy_text(e)
    if text is None:
        return PlainTextResponse("", status_code=204)
    js = One[Eval(f"void navigator.clipboard.writeText({json.dumps(text)})")]
    return PlainTextResponse(str(js), status_code=200)


def compact_async(being_file: str, strategy: str = "default"):
    being = get_being(being_file, BEINGS_DIR)
    if not being.declaration:
        return PlainTextResponse(
            f"No declaration. {being_file} must write !declaration before compaction.",
            status_code=400,
        )
    being.commands.put_nowait(("compact", strategy))
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
    evict_being(being_file)
    return PlainTextResponse("location.reload()", status_code=200)


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

def find_beings() -> list[dict]:
    beings = []
    for path in BEINGS_DIR.glob("*.jsonl"):
        if path.name.startswith('.'):
            continue
        try:
            being = get_being(path.stem, BEINGS_DIR)
        except Exception:
            continue
        if not being.model:
            continue
        beings.append({"file": path.stem, "model": being.model, "capacity": being.capacity, "events": len(being.events)})
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


def _build_memories(being) -> dict:
    return {e.id: (i, e) for i, e in enumerate(being.events) if getattr(e, 'id', None)}


# === RENDER HELPERS ===

def _event_copy_text(e: Event) -> str | None:
    match e:
        case Vote(reasoning=r) if r:
            return r
        case _ if (content := getattr(e, "content", "") or ""):
            return content
        case _:
            return None


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


def _copy_control(being_file: str | None, idx: int | None) -> list:
    if being_file is not None and idx is not None:
        return [
            "form",
            {
                "action": "/do",
                "method": "post",
                "class": "copy-form",
                "data-reset": "false",
            },
            *snippet_hidden(f"copy_to_clipboard({json.dumps(being_file)}, {idx})"),
            ["button", {"type": "submit", "class": "copy-btn", "aria-label": "Copy to clipboard"}, "⧉"],
        ]
    return ["span", {"class": "copy-btn"}, "⧉"]


def _event_body_html(
    e: Event, memories: dict, being_file: str | None = None, idx: int | None = None
) -> list | None:
    cc = _copy_control(being_file, idx)
    match e:
        case Vote(reasoning=r) if r:
            return ["div.event-content", cc, r]

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
            return ["div.event-content", cc, content]

        case _:
            return None


def _event_summary(e: Event, i: int, etype: str, memories: dict) -> list:
    match e:
        case Vote():
            score_str = f"{e.vote_score:+d}"
            body = ["span",
                _mem_link(e.vote_a_id, memories), f" {score_str} vs ",
                _mem_link(e.vote_b_id, memories),
            ]
        case Compaction():
            body = ["span.event-preview",
                f"↓{len(e.released_ids)} kept {len(e.kept_ids)}"
                + (f" ↑{len(e.resurrected_ids)}" if e.resurrected_ids else "")]
        case _:
            content = getattr(e, 'content', '') or ''
            body = ["span.event-preview", content[:80] + ("…" if len(content) > 80 else "")]
    return ["span.event-summary",
        ["span.event-num", f"{i} "],
        ["span.event-type", f"{etype} "],
        ["span.event-time", f"{ts_fmt(e.timestamp)} "],
        body,
    ]


def render_event(e: Event, i: int, memories: dict = None, being_file: str = None) -> list:
    memories = memories or {}
    etype = type(e).__name__.lower()
    eid = getattr(e, 'id', None)

    attrs = {"data-idx": str(i)}
    if eid:
        attrs["id"] = f"evt-{eid}"

    summary = _event_summary(e, i, etype, memories)
    has_body = _event_body_html(e, memories, being_file, i) is not None

    if has_body and being_file:
        return ["form.event.expandable", {**attrs, "action": "/do", "method": "post"},
            *snippet_hidden(f"event_body('{being_file}', {i})"),
            ["button.event-row", {"type": "submit"}, summary],
        ]

    return ["div.event", attrs, summary]


def render_event_expanded(e: Event, i: int, memories: dict = None, being_file: str = None) -> list:
    memories = memories or {}
    etype = type(e).__name__.lower()
    eid = getattr(e, 'id', None)

    attrs = {"data-idx": str(i)}
    if eid:
        attrs["id"] = f"evt-{eid}"

    summary = _event_summary(e, i, etype, memories)
    body = _event_body_html(e, memories, being_file, i)
    collapse = ["form.collapse-form", {"action": "/do", "method": "post"},
        *snippet_hidden(f"event_collapse('{being_file}', {i})"),
        ["button.event-close", {"type": "submit"}, "✕"],
    ] if being_file else None
    return ["div.event.expanded", attrs, summary, collapse, body]


def event_body(being_file: str, idx: int):
    events = get_being(being_file, BEINGS_DIR).events
    if idx < 0 or idx >= len(events):
        return PlainTextResponse("", status_code=404)
    e = events[idx]
    memories = {ev.id: (j, ev) for j, ev in enumerate(events) if getattr(ev, 'id', None)}
    body = _event_body_html(e, memories, being_file, idx)
    if body is None:
        return PlainTextResponse("", status_code=200)
    js = Three[Selector(f'[data-idx="{idx}"]')][MORPH][
        render_event_expanded(e, idx, memories, being_file)
    ]
    return PlainTextResponse(js, status_code=200)


def event_collapse(being_file: str, idx: int):
    events = get_being(being_file, BEINGS_DIR).events
    if idx < 0 or idx >= len(events):
        return PlainTextResponse("", status_code=404)
    e = events[idx]
    memories = {ev.id: (j, ev) for j, ev in enumerate(events) if getattr(ev, 'id', None)}
    js = Three[Selector(f'[data-idx="{idx}"]')][MORPH][render_event(e, idx, memories, being_file)]
    return PlainTextResponse(js, status_code=200)


def render_events_div(being_file: str) -> list:
    being = get_being(being_file, BEINGS_DIR)
    memories = _build_memories(being)
    event_list = [render_event(e, i, memories, being_file) for i, e in enumerate(being.events)]
    event_list.reverse()
    return ["div#events.events", event_list]


def exec_event(js: str) -> str:
    lines = ["event: exec"]
    for line in js.split('\n'):
        lines.append(f"data: {line}")
    lines += ["", ""]
    return "\n".join(lines)


def _push_initial_page(title: str, body_content: list):
    yield exec_event(One[Eval(f"document.title = {json.dumps(title)}")])
    yield exec_event(Three[Selector("head")][MORPH][_head_content(title)])
    yield exec_event(Three[Selector("body")][MORPH][["body", body_content]])


async def _stream_auth_then_initial(request: Request, session_id: str, title: str, body_content: list):
    while not _is_authed(request, session_id):
        for ev in _push_initial_page("login", _login_form(session_id)):
            yield ev
        await asyncio.sleep(1)
    for ev in _push_initial_page(title, body_content):
        yield ev


def render_progress_bar(current: int, total: int, phase: str) -> list:
    pct = int(100 * current / total) if total else 0
    return [
        "div#compaction-progress.compaction-progress",
        ["div.progress-bar", ["div.progress-fill", {"style": f"width: {pct}%"}]],
        ["span.progress-text", f"{phase} {current}/{total}"],
    ]


# === EXECUTE: SSE generator runs commands directly ===

def _go_form(being_file: str) -> list:
    return ["form", {"action": "/do", "method": "post", "class": "go-form"},
        *snippet_hidden(f"go('{being_file}', $message)"),
        ["textarea", {"name": "message", "rows": "8"}],
        ["button", {"type": "submit"}, "go"],
    ]


async def execute(being, being_file: str, cmd):
    from adam import think, receive, compact

    match cmd:
        case ("think",):
            async for event in think(being):
                memories = _build_memories(being)
                idx = len(being.events) - 1
                rendered = render_event(event, idx, memories, being_file)
                yield exec_event(Three[Selector("#events")][PREPEND][rendered])

        case ("receive", msg):
            async for event in receive(being, msg):
                memories = _build_memories(being)
                idx = len(being.events) - 1
                rendered = render_event(event, idx, memories, being_file)
                yield exec_event(Three[Selector("#events")][PREPEND][rendered])

        case ("compact", strategy_name):
            strategy = STRATEGIES.get(strategy_name, STRATEGIES["default"])
            async for item in compact(being, strategy):
                if isinstance(item, Progress):
                    bar = render_progress_bar(item.current, item.total, item.phase)
                    yield exec_event(Three[Selector("#compaction-progress")][MORPH][bar])
                else:
                    memories = _build_memories(being)
                    idx = len(being.events) - 1
                    rendered = render_event(item, idx, memories, being_file)
                    yield exec_event(Three[Selector("#events")][PREPEND][rendered])
            yield exec_event(Three[Selector("#compaction-progress")][MORPH][["div#compaction-progress.compaction-progress"]])

    # Fresh go form with new nonce + remove sending state
    yield exec_event(Three[Selector("form.go-form")][MORPH][_go_form(being_file)])


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
    being = get_being(being_file, BEINGS_DIR)
    events = being.events
    init = next((e for e in events if isinstance(e, Init)), None)
    model = init.model if init else "?"

    mem_count = sum(1 for e in events if isinstance(e, (Init, Thought, Perception, Response, Declaration)))
    mem_count -= sum(len(e.released_ids) for e in events if isinstance(e, Compaction) and e.released_ids)
    vote_count = sum(1 for e in events if isinstance(e, Vote))

    top = ["div.top-bar",
        ["a", {"href": "/"}, "←"], " ",
        f"{being_file} ({model}): {len(events)} events, {mem_count} memories, {vote_count} votes"
    ]

    form = _go_form(being_file)

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

    events_div = render_events_div(being_file)

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
    session_id = uuid.uuid4().hex

    async def generate():
        async for ev in _stream_auth_then_initial(request, session_id, "git", git_content()):
            yield ev

    return StreamingResponse(generate(), media_type="text/event-stream", headers=_sse_headers())


@app.get("/{being_file}/config/sse")
async def sse_config(being_file: str, request: Request):
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
    if being_file in ("git", "login", "do", "sse", "static"):
        return PlainTextResponse("not found", status_code=404)
    path = BEINGS_DIR / f"{being_file}.jsonl"
    if not path.exists():
        return PlainTextResponse("not found", status_code=404)
    session_id = uuid.uuid4().hex

    async def generate():
        async for ev in _stream_auth_then_initial(request, session_id, being_file, being_content(being_file)):
            yield ev

        being = get_being(being_file, BEINGS_DIR)
        while True:
            try:
                cmd = await asyncio.wait_for(being.commands.get(), timeout=5.0)
            except asyncio.TimeoutError:
                if await request.is_disconnected():
                    break
                continue
            async for ev in execute(being, being_file, cmd):
                yield ev
            if await request.is_disconnected():
                break

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
    snippet = apply_snippet_substitutions(snippet, form_data)

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
