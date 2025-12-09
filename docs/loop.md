# Signed Snippets: A Web Architecture

---

> "Let's ponder about hiccup and my web 1.0 approach."

The starting point is refusal. Refusal of the jQuery → Backbone → Angular → React → Next.js escalator. Your `go` endpoint does a POST, performs a side effect, returns a 303 redirect. The browser follows it, does a GET, gets fresh HTML. The server is the source of truth, and every interaction round-trips through it.

Back button works. Refresh works. Curl works. The entire UI is greppable.

Hiccup makes this tenable. HTML as data—nested arrays that map directly to the DOM tree. No template language, no JSX transpilation, no DSL. Functions are your components. `render_event()` returns a list, nest it anywhere. The full power of the host language for composition.

---

> "I'm also thinking about Rama, by Red Planet Labs. The event log + materialized view distinction."

The event log is your semantic layer.

```
Events (truth)
   ↓
Materialized views (derived, rebuildable)
   ↓
Hiccup (derived, ephemeral)
   ↓
HTML (serialized, sent, forgotten)
```

Each layer is a pure function of the one above. The `.jsonl` file is the source of truth. `being.current` and `being.votes` are materialized views—maintained alongside the event log, rebuilt by replaying if needed. Hiccup is derived from those views, rendered once, thrown at the browser. 

The semantic meaning lives in the event log and in your code. The DOM is a disposable projection.

---

> "I think semantic hiccup would be an unnecessary layer."

Correct. You already have three representations: events, materialized views, and the function call hierarchy that generates hiccup. A fourth "semantic tree" would be redundant because you render-and-discard on every request. The semantic structure exists in your code—`render_being_page` → `render_event` → `render_vote_details`—then evaporates. The browser gets flat HTML. Nobody needs to query "find all Events" client-side because the server already did that work.

---

> "What if we had an entire Specter implementation in JS. That reached inside of an in-memory pstate—semantic view of DOM structure. That responded to native DOM events."

This would be cleaner than React. One state atom, domain-shaped not DOM-shaped. Specter paths for navigation and transformation. A pure hiccup function for projection. Diff the hiccup, patch the DOM.

But...

---

> "But this isn't web 1.0... and it doesn't solve the network round trip problem... It's cute..."

Right. We've just reinvented client-side frameworks with better primitives. The round trip remains. The complexity migrates to the client. The server becomes a dumb API.

---

> "Does JS have eval? Does Python? I'm dreaming something wicked."

---

> "You know how forms have callbacks? To a specific route? What if we instead just put the entire Python callback snippet as a string on the form, and have some generic evaluator that just takes form data, splices it into the snippet and evals it."

The mapping is gone.

Traditional web dev has six layers of indirection between button and behavior:

```
Form action="/beings/adam/go" method="POST"
         ↓
URL routing regex
         ↓
Controller dispatch
         ↓
Handler method
         ↓
Parameter binding
         ↓
Authorization check
         ↓
Finally, the actual logic
```

Each one a place to mess up, a place to secure, a place where meaning gets lost.

Signed snippets collapse it to zero:

```html
<form data-snippet="
being = load('adam.jsonl')
receive(being, $message)
redirect('/adam')
" data-sig="a8f3..." data-nonce="x7k2...">
```

The form *is* the behavior. The button says what it does—literally, in code. Not a reference to behavior. The behavior itself.

The server has one route:

```python
@app.post("/do")
async def do(request: Request):
    form = await request.form()
    snippet = form['__snippet__']
    sig = form['__sig__']
    nonce = form['__nonce__']
    
    if not verify(snippet + nonce, sig, SECRET):
        return 403
    
    if not consume_nonce(nonce):
        return 403
    
    env = {k: scrub(v) for k, v in form.items() 
           if not k.startswith('__')}
    
    return eval_snippet(snippet, env)
```

---

> "I think it might even be _more_ secure. If everything is signed, nonces, etc. Like it's centralizing all interactions through one encrypted pipe. Only escaping form data which can be scrubbed."

The threat model inverts.

**Traditional:**
- N routes, each a potential vulnerability
- Parameter binding at each route
- Auth checks scattered everywhere
- CSRF tokens per form
- ORMs, query builders, escaping at every layer

**Signed snippets:**
- One route
- Snippet is signed + nonced by server
- Client can't forge snippets, can't replay them
- Form data is ONLY data—never structure, never code
- One place to scrub, one place to validate

The signed snippet *is* the capability. If you have a valid signature on `delete(being, $id)`, the server authorized that action when it rendered the page. The signature proves provenance.

No route authorization logic. No "can user X do Y to Z?" scattered across handlers. The HTML itself encodes what's permitted. View the page, view your capabilities.

The attack surface is: can you forge a signature, or break the scrubbing. That's it.

---

> "Would this need one Python interpreter sandbox per user session?"

No. The snippets are stateless. They operate on data, not interpreter state.

```python
being = load('adam.jsonl')   # Load from event log
receive(being, $message)      # Append event, save
redirect('/adam')             # Done
```

The event log is the state. The interpreter is just a CPU. Spin up, eval, tear down. Fresh restricted globals each time:

```python
sandbox = {
    'load': load,
    'receive': receive,
    'think': think,
    'redirect': Redirect,
    # ... whitelist
}
```

No persistent state in the interpreter. No per-user process. Same as any stateless web handler, except the handler is inline.

Memory overhead: one dict per request. Garbage collected when the request ends.

You get stateless scaling for free because you already designed for event-sourced state.

---

**What falls out:**

*Capability security without trying.* Server only renders snippets for actions you're allowed to do. If you can see the form, you have the capability.

*Auditability.* What can this page do? View source. Every action is visible. Grep your templates for every capability in the system.

*No semantic gap.* The thing the developer wrote, the thing the browser sends, and the thing the server runs are the same text.

*Serialized closures.* The snippet captures its context at render time. `'adam.jsonl'` is baked in. It's a closure, signed and sent to the client for safekeeping, returned when invoked.

You've made the browser a dumb terminal that holds signed capabilities and returns them with filled-in blanks.

---

**The lineage:**

- Tcl's "everything is a string"
- Lisp sent over the wire
- PHP's original sin, but intentional and sandboxed
- Object-capability security
- Event sourcing
- Hiccup's code-as-data

The web that should have been.