# Plan: routing through content negotiation

The app currently scatters routing across ~10 FastAPI decorators that all do nearly the same thing. FastAPI provides Pydantic validation, OpenAPI docs, dependency injection — none of which this app uses. Everything it touches (`Request`, `Response`, `StreamingResponse`, `StaticFiles`) is Starlette.

Replace the router with content negotiation on a raw ASGI app. Drop FastAPI entirely.

## The dispatch

One URL. Three behaviors. Method + Accept header determine what you get.

```
GET  /ember                            → shell HTML
GET  /ember   Accept: text/event-stream → SSE stream for /ember
POST /ember                            → verify sig, eval snippet, return JS
GET  /static/*                         → files from disk
```

The entire router is an if statement:

```python
static = StaticFiles(directory=...)

async def app(scope, receive, send):
    if scope["type"] != "http":
        return

    path, method = scope["path"], scope["method"]
    request = Request(scope, receive)

    if path.startswith("/static"):
        scope["path"] = path[7:]
        await static(scope, receive, send)
        return

    if method == "POST":
        r = await do(request)
    elif "text/event-stream" in request.headers.get("accept", ""):
        r = await sse(request, path)
    else:
        r = HTMLResponse(shell_html())

    await r(scope, receive, send)
```

No framework. No decorator routing. No `/do`. No `/sse` suffix paths.

## The shell

`shell_html()` no longer takes an `sse_path` parameter. The EventSource connects to the current URL:

```js
const es = new EventSource(location.pathname);
```

Forms post to the current URL (default when `action` is omitted):

```html
<form method="post">...</form>
```

`signer.snippet_hidden(...)` still embeds the signed Python snippet. The server doesn't care what path the POST arrives on — it verifies the signature and evals the snippet regardless.

## The pages table

Inside the SSE handler, a regex table resolves the path to content:

```python
PAGES = [
    (r"^/$",                     lambda:   ("beings",       index_content())),
    (r"^/git$",                  lambda:   ("git",          git_content())),
    (r"^/(?P<b>[^/]+)/config$",  lambda b: (f"{b} config",  config_content(b))),
    (r"^/(?P<b>[^/]+)$",         lambda b: (b,              being_content(b))),
]

def resolve(path):
    for pattern, handler in PAGES:
        m = re.match(pattern, path)
        if m:
            return handler(**m.groupdict())
    return None
```

The table is the shape of the app. Read it top to bottom and you know every screen.

## The SSE handler

One SSE endpoint replaces four:

```python
async def sse(request, path):
    async def stream():
        session_id = uuid.uuid4().hex
        resolved = resolve(path)
        if not resolved:
            return

        title, content = resolved

        # Auth gate: paint login once, wait silently
        if not _is_authed(request, session_id):
            yield from paint("login", _login_form(session_id))
            while not _is_authed(request, session_id):
                await asyncio.sleep(1)

        # Paint the resolved page
        yield from paint(title, content)

        # Being pages enter the command loop
        being = get_being_if_exists(path)
        if being:
            async for ev in command_loop(request, being):
                yield ev

    return StreamingResponse(stream(), media_type="text/event-stream", headers=NO_CACHE)
```

`paint` replaces `_push_initial_page`:

```python
def paint(title, body):
    yield exec_event(One[Eval(f"document.title = {json.dumps(title)}")])
    yield exec_event(Three[Selector("head")][MORPH][_head_content(title)])
    yield exec_event(Three[Selector("#app")][MORPH][["div#app", body]])
```

## The snippet contract

Every snippet handler returns a JS string. No `PlainTextResponse`. No status codes. No `RedirectResponse`. The `/do` handler (now just the POST branch) wraps the result:

```python
async def do(request):
    form = await request.form()
    try:
        snippet = signer.verify_snippet(form)
        js = eval(snippet)
        if not isinstance(js, str):
            js = "/* noop */"
        return PlainTextResponse(js, status_code=200)
    except SnippetExecutionError as e:
        return PlainTextResponse(f"console.error({json.dumps(e.message)})", status_code=200)
    except Exception as e:
        return PlainTextResponse(f"console.error({json.dumps(str(e))})", status_code=200)
```

Snippet handlers become pure:

```python
def go(being_file, message=''):
    get_being(being_file, BEINGS_DIR).commands.put_nowait(
        ("receive", message) if message.strip() else ("think",))
    return Four[Selector('form.go-form button[type="submit"]')][CLASSES][ADD]['sending']

def save_git_config(url):
    git_config_path().write_text(json.dumps({"url": url}))
    return One[Eval("location.assign('/git')")]

def redact(being_file):
    # ... file mutation ...
    return One[Eval("location.reload()")]
```

## Navigation

Client-side navigation via `history.pushState` + SSE reconnect:

```python
def navigate(path):
    return One[Eval(f"history.pushState(null,'','{path}'); es.close(); es = new EventSource('{path}')")]
```

Or simpler: `location.assign(path)`. Full page reload. The shell is tiny so there's no perceptual cost. Start with `location.assign`, add pushState later if it matters.

## What gets deleted

- `fastapi` dependency (and its transitive deps: pydantic, etc.)
- All `@app.get` / `@app.post` decorators
- `/do` as a URL concept
- `/sse`, `/git/sse`, `/{being}/sse`, `/{being}/config/sse` — four endpoints become one
- `_stream_auth_then_initial`
- `_shell_page`
- `PlainTextResponse` wrappers inside snippet handlers
- `RedirectResponse` import and usage

## What remains

- `starlette` (Request, Response, StreamingResponse, StaticFiles)
- `uvicorn`
- `evaleval` (Signer, patch DSL, exec_event, shell_html, hiccup)
- The ASGI dispatch (an if statement)
- The PAGES table (a list of tuples)
- The snippet handlers (functions returning JS strings)
- The SSE loop (resolve, auth gate, paint, optional command loop)

## Open questions

- Should `shell_html()` be updated in evaleval to use `location.pathname` as the default SSE path and drop the `sse_path` parameter? Or keep it configurable?
- The index SSE loop currently polls for new beings every 2s. Keep this as a special case in the command loop, or drop it?
- Error rendering: should snippet errors morph a toast/banner into the DOM instead of `console.error`?
