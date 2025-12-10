#!/usr/bin/env python3
"""
Todo: ONE TREE TO RULE THEM ALL

Architecture:
- One global hiccup tree containing the entire app
- Events → Specter transforms (incremental mutations)
- URLs → Specter paths (filtered views)
- No intermediate state, just the tree
"""

import time
import uuid
import hmac
import hashlib
import base64
import asyncio
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse, StreamingResponse
from hiccup import render, RawContent
from registry import event, to_dict, from_dict
from specter import (
    transform,
    setval,
    select_one,
    select,
    walker,
    ALL,
    NONE,
    id_pred,
    attr_eq,
    prance,
)
from tree import TreeState, load_log, append_log


# === EVENTS ===

@event
class Add:
    id: str
    text: str
    ts: int


@event  
class Toggle:
    id: str
    ts: int


@event
class Remove:
    id: str
    ts: int


Event = Add | Toggle | Remove


# === STATE ===

ROOT = Path(__file__).parent
LOG = ROOT / "todos.jsonl"
STATE = TreeState()


# === ONE TREE ===

def empty_tree() -> list:
    """The One Tree structure. Snippets stored as data attributes, not baked in."""
    return ['html', {'id': 'root'},
        ['head',
            ['meta', {'charset': 'utf-8'}],
            ['title', 'todos'],
            ['script', {'src': 'https://unpkg.com/idiomorph@0.3.0/dist/idiomorph.min.js'}],
            ['style', RawContent(CSS)]],
        ['body',
            ['div', {'id': 'app'},
                ['h1', 'todos'],
                ['form', {'id': 'add', 'action': '/do', 'method': 'post', 'data-snippet': 'add($text)'},
                    ['textarea', {'name': 'text', 'placeholder': 'what needs doing?', 'rows': '8'}],
                    ['button', 'add']],
                ['ul', {'id': 'list'}],
                ['p', {'class': 'count', 'id': 'count'}, '0 remaining']],
            ['script', RawContent(CLIENT_JS)]]]


# === REDUCER: Specter transforms ===

def apply(tree: list, event) -> list:
    """Apply event to tree using Specter. Returns new tree."""
    match event:
        case Add(id=id, text=text):
            # Create new todo node with snippet as data attribute
            new_item = ['li', {'class': 'todo', 'id': f't-{id}'},
                ['span.text', text],
                ['form.inline', {'action': '/do', 'method': 'post', 'data-snippet': f"toggle('{id}')"},
                    ['button.toggle', '✓']],
                ['form.inline', {'action': '/do', 'method': 'post', 'data-snippet': f"remove('{id}')"},
                    ['button.remove', '×']]]
            
            # Append to #list
            list_node = select_one(['#list'], tree)
            if list_node:
                new_list = list_node + [new_item]
                tree = setval(['#list'], new_list, tree)
            
            # Update count
            tree = update_count(tree)
            
        case Toggle(id=id):
            # Toggle 'done' class
            #TODO this should be a navigator
            def toggle_done(node):
                if not isinstance(node, list) or len(node) < 2:
                    return node
                attrs = node[1] if isinstance(node[1], dict) else {}
                classes = attrs.get('class', '').split()
                if 'done' in classes:
                    classes.remove('done')
                else:
                    classes.append('done')
                new_attrs = {**attrs, 'class': ' '.join(classes)}
                return [node[0], new_attrs] + node[2:]
            
            tree = transform([walker(id_pred(f't-{id}'))], toggle_done, tree)
            tree = update_count(tree)
            
        case Remove(id=id):
            # Remove the node
            tree = setval([walker(id_pred(f't-{id}'))], NONE, tree)
            tree = update_count(tree)
    
    return tree


def update_count(tree: list) -> list:
    """Update the remaining count."""
    list_node = select_one(['#list'], tree)
    if not list_node:
        return tree
    
    # Count non-done items
    items = [c for c in list_node[2:] if isinstance(c, list)]
    remaining = sum(1 for item in items 
                   if 'done' not in (item[1].get('class', '') if len(item) > 1 and isinstance(item[1], dict) else ''))
    
    new_count = ['p', {'class': 'count', 'id': 'count'}, f'{remaining} remaining']
    return setval(['#count'], new_count, tree)


def load_tree():
    """Load tree from event log."""
    STATE.tree = empty_tree()
    events = load_log(LOG, from_dict)
    for event in events:
        STATE.tree = apply(STATE.tree, event)


# === SIGNING ===

SECRET = hashlib.sha256(f"todo-{uuid.uuid4()}".encode()).digest()
_nonces: dict[str, float] = {}


def nonce() -> str:
    n = uuid.uuid4().hex
    _nonces[n] = time.time() + 3600
    return n


def consume(n: str) -> bool:
    return _nonces.pop(n, None) is not None


def sign(code: str, n: str) -> str:
    return base64.urlsafe_b64encode(hmac.new(SECRET, f"{code}|{n}".encode(), hashlib.sha256).digest()).decode()


def verify(code: str, n: str, sig: str) -> bool:
    return hmac.compare_digest(sign(code, n), sig)


def snippet_hidden(code: str) -> list:
    """Generate snippet hidden fields with fresh nonce."""
    n = nonce()
    return [
        ['input', {'type': 'hidden', 'name': '__snippet__', 'value': code}],
        ['input', {'type': 'hidden', 'name': '__sig__', 'value': sign(code, n)}],
        ['input', {'type': 'hidden', 'name': '__nonce__', 'value': n}],
    ]


def inject_snippets(tree: list) -> list:
    """Walk tree and inject fresh signed snippets from data-snippet attributes."""
    def inject(node):
        if not isinstance(node, list) or len(node) < 2:
            return node
        
        attrs = node[1] if isinstance(node[1], dict) else {}
        snippet_code = attrs.get('data-snippet')
        
        if snippet_code and node[0] == 'form':
            # This is a form with a snippet - inject hidden fields
            children = node[2:] if isinstance(node[1], dict) else node[1:]
            new_children = list(snippet_hidden(snippet_code)) + children
            return [node[0], attrs, *new_children]
        
        # Recurse into children
        start = 2 if isinstance(node[1], dict) else 1
        children = node[start:]
        new_children = [inject(c) if isinstance(c, list) else c for c in children]
        
        result = [node[0]]
        if isinstance(node[1], dict):
            result.append(node[1])
        result.extend(new_children)
        return result
    
    return inject(tree)


# === ACTIONS (called via snippets) ===

def add(text: str):
    if text.strip():
        e = Add(uuid.uuid4().hex[:8], text.strip(), int(time.time() * 1000))
        append_log(LOG, e, to_dict)
        STATE.tree = apply(STATE.tree, e)
        STATE.notify('app')
    return RedirectResponse('/', 303)


def toggle(id: str):
    e = Toggle(id, int(time.time() * 1000))
    append_log(LOG, e, to_dict)
    STATE.tree = apply(STATE.tree, e)
    STATE.notify('app')
    return RedirectResponse('/', 303)


def remove(id: str):
    e = Remove(id, int(time.time() * 1000))
    append_log(LOG, e, to_dict)
    STATE.tree = apply(STATE.tree, e)
    STATE.notify('app')
    return RedirectResponse('/', 303)


# === STYLES & CLIENT ===

CSS = """
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { 
        font-family: 'Garamond', 'Georgia', 'Times New Roman', serif;
        background: #000; 
        color: #ccc; 
        line-height: 1.4;
        font-size: 24px;
    }
    h1 { display: none; }
    #add { margin: 0; padding: 0; }
    #add textarea { 
        width: 100%;
        padding: 0;
        background: #000; 
        color: #ccc; 
        border: none;
        border-bottom: 1px solid #ccc;
        font-family: 'Garamond', 'Georgia', 'Times New Roman', serif;
        font-size: 24px;
        line-height: 1.4;
        height: calc(8 * 1.4em);
        resize: none;
    }
    #add textarea:focus { outline: none; }
    #add button { 
        width: 100%;
        padding: 30px;
        background: #ccc;
        color: #000;
        border: 6px solid;
        border-color: #000 #ccc #ccc #000;
        font-family: 'Garamond', 'Georgia', 'Times New Roman', serif;
        font-size: 28px;
        cursor: pointer;
    }
    #add button:hover { opacity: 0.9; }
    #add button:active { border-color: #ccc #000 #000 #ccc; }
    ul { list-style: none; border-top: 1px solid #ccc; }
    li { 
        padding: 1px;
        border-bottom: 1px solid #ccc; 
        font-size: 18px;
        display: flex;
        align-items: center;
    }
    li:hover { background: #1a1a1a; }
    li.done .text { text-decoration: line-through; color: #888; }
    .text { flex: 1; }
    .inline { display: inline; margin: 0; padding: 0; }
    button.toggle, button.remove { 
        background: none; 
        border: none; 
        cursor: pointer; 
        font-size: 18px; 
        padding: 4px 8px;
        color: #888;
    }
    button.toggle:hover { color: #8f8; }
    button.remove:hover { color: #f88; }
    .count { 
        padding: 1px;
        font-size: 18px;
        color: #888; 
        border-bottom: 1px solid #ccc;
    }
"""

CLIENT_JS = """
    const es = new EventSource('/stream');
    es.onmessage = e => Idiomorph.morph(document.getElementById('app'), e.data, {morphStyle: 'innerHTML'});
    es.onerror = () => setTimeout(() => location.reload(), 3000);
"""


# === APP ===

app = FastAPI()


@app.on_event("startup")
def startup():
    load_tree()
    events = load_log(LOG, from_dict)
    print(f"🌳 ONE TREE loaded with {len(events)} events")


def render_slice(specter_path: list, title: str = 'Slice'):
    """Pure slice - just render what's at the path."""
    print(f"Rendering slice: {specter_path}")
    sliced = prance(STATE.tree, specter_path)
    
    # Wrap in minimal HTML shell
    wrapped = ['html',
        ['head',
            ['meta', {'charset': 'utf-8'}],
            ['title', title],
            ['script', {'src': 'https://unpkg.com/idiomorph@0.3.0/dist/idiomorph.min.js'}],
            ['style', RawContent(CSS)]],
        ['body',
            sliced,
            ['script', RawContent(CLIENT_JS)]]]
    
    tree_with_snippets = inject_snippets(wrapped)
    return render(tree_with_snippets)


@app.get("/stream")
async def stream():
    """SSE endpoint - streams #app updates."""
    q = asyncio.Queue()
    
    def listener(html):
        try:
            q.put_nowait(html)
        except:
            pass
    
    STATE.listeners.append(listener)
    
    async def gen():
        try:
            while True:
                try:
                    html = await asyncio.wait_for(q.get(), timeout=30)
                    yield f"data: {html}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            STATE.listeners.remove(listener)
    
    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/do")
async def do(request: Request):
    """Execute signed snippet."""
    form = await request.form()
    
    snippet = form.get('__snippet__', '')
    sig = form.get('__sig__', '')
    nonce_val = form.get('__nonce__', '')
    
    if not all([snippet, sig, nonce_val]):
        return PlainTextResponse("Missing fields", 400)
    
    if not verify(snippet, nonce_val, sig):
        return PlainTextResponse("Invalid signature", 403)
    
    if not consume(nonce_val):
        return PlainTextResponse("Expired nonce", 403)
    
    # Substitute $vars
    for k, v in form.items():
        if not k.startswith('__'):
            snippet = snippet.replace(f'${k}', repr(str(v)))
    
    return eval(snippet)


def url_to_path(url_path: str) -> list:
    """Translate URL path segments into a Specter path of #ids."""
    segments = [seg for seg in url_path.split('/') if seg]
    return [f'#{seg}' for seg in segments]


@app.get("/{full_path:path}", response_class=HTMLResponse)
def route(full_path: str):
    """Single route handler - parses URL into Specter path and prances the tree."""
    path = full_path.strip('/')
    return render_slice(url_to_path(path), title="/" + path if path else "root")


if __name__ == "__main__":
    import uvicorn
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="Enable autoreload (uvicorn reload)")
    args = parser.parse_args()
    
    print(f"🌳 http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)
