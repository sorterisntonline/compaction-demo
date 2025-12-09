# Signed Snippets Implementation

## Architecture

```
Form (contains snippet)  →  /do endpoint  →  verify sig  →  consume nonce  →  eval in sandbox
     ↓                                                                              ↓
   signed by server                                                          whitelist only
   at render time                                                            form data scrubbed
```

## Files

### `snippets.py` - Core module

```python
# Signing
sign(snippet, nonce) -> base64 signature
verify(snippet, nonce, sig) -> bool

# Nonces
generate_nonce() -> hex string (stored with 1hr TTL)
consume_nonce(nonce) -> bool (True if valid, removes it)

# Execution
scrub(value) -> escaped string (prevents injection)
eval_snippet(snippet, form_data, sandbox) -> SnippetResult

# Form generation
signed_form(action, snippet, fields, button_text) -> hiccup
```

### `ui2.py` - Web server

**One route: `/do`**

```python
@app.post("/do")
async def do(request):
    # 1. Extract signed parts
    snippet = form['__snippet__']
    sig = form['__sig__']
    nonce = form['__nonce__']
    
    # 2. Verify signature
    if not verify(snippet, nonce, sig):
        return 403
    
    # 3. Consume nonce (prevents replay)
    if not consume_nonce(nonce):
        return 403
    
    # 4. Execute in sandbox
    form_data = {k: v for k, v in form if not k.startswith('__')}
    result = eval_snippet(snippet, form_data, SANDBOX)
    
    return result.redirect or result.html
```

**Sandbox whitelist:**
```python
SANDBOX = {
    'load': _load,
    'receive': _receive,
    'think': _think,
    'compact': _compact,
    'Redirect': Redirect,
}
```

## Example: Message Form

Server renders:
```html
<form action="/do" method="post">
  <input type="hidden" name="__snippet__" value="
being = load('whale.jsonl')
msg = $message
if msg.strip():
    receive(being, msg)
else:
    think(being)
__result__ = Redirect('/whale')
" />
  <input type="hidden" name="__sig__" value="ZEqBn3Z56v8FNlJEg..." />
  <input type="hidden" name="__nonce__" value="a6da9586692d47b2..." />
  <textarea name="message"></textarea>
  <button type="submit">go</button>
</form>
```

When submitted:
1. `$message` is replaced with scrubbed form value
2. Signature verified against snippet+nonce
3. Nonce consumed
4. Snippet executed in sandbox
5. Redirect returned

## Security Properties

| Threat | Mitigation |
|--------|------------|
| Forge snippet | HMAC-SHA256 signature |
| Replay request | Nonce consumed on first use |
| Inject via form data | Values scrubbed (quotes escaped) |
| Access builtins | `__builtins__ = {}` |
| Import modules | Not in sandbox whitelist |
| File access | Not in sandbox whitelist |

## Test Results

```
1. Index page...           ✓
2. Being page structure... ✓ (forms contain snippet/sig/nonce)
3. Valid execution...      ✓ (303 redirect)
4. Replay attack...        ✓ (403 - nonce consumed)
5. Forged signature...     ✓ (403 - invalid)
6. Injection scrubbing...  ✓ (becomes literal string)
7. Missing params...       ✓ (400 - rejected)
```

## Running

```bash
# Start server on port 8001
python ui2.py opus --port 8001

# Original server still available
python ui.py opus --port 8000
```

## View Source

The "view snippet" feature shows exactly what code will run:

```
▼ view snippet
being = load('whale.jsonl')
msg = $message
if msg.strip():
    receive(being, msg)
else:
    think(being)
__result__ = Redirect('/whale')
```

No semantic gap. What you see is what runs.

