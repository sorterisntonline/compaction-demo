# One Tree

The web has two computers. One thinks. One renders. For twenty years we've been negotiating the gap between them—APIs, state management, serialization, synchronization, frameworks on both ends speaking different languages about the same things.

One Tree says: there is no gap. There is one representation: HTML. It flows down as views. It flows up as actions. The server thinks in HTML. The client renders HTML. The wire carries HTML.

---

**The depot** is an append-only event log. JSONL. The only place writes happen. Immutable truth.

```
{"type": "thought", "id": "abc", "content": "I remember...", "timestamp": 1234}
{"type": "vote", "a_id": "abc", "b_id": "def", "score": 12}
{"type": "compaction", "released_ids": ["def"]}
```

---

**The materialized view** is hiccup—HTML represented as nested data.

```python
['div#app',
  ['div#events',
    ['div.event', {'id': 'abc', 'data-type': 'thought', 'data-ts': '1234'}, 
      'I remember...']],
  ['form', {'data-snippet': "go('adam', $message)", 'data-sig': '...'},
    ['textarea', {'name': 'message'}],
    ['button', 'go']]]
```

This is the pstate. The reducer builds it directly from events:

```python
def apply_event(tree, event):
    match event:
        case Thought(id=id, content=content, timestamp=ts):
            return append(tree, ['div#events'],
                ['div.event', {'id': id, 'data-type': 'thought', 'data-ts': ts}, content])
        case Compaction(released_ids=ids):
            return remove(tree, [f'div#{id}' for id in ids])
```

Reducer in: tree + event. Reducer out: new tree. No intermediate domain objects. The HTML shape *is* the domain model.

---

**Queries** are specter paths. URLs serialize them.

```
GET /adam?type=vote&page=2
```

Becomes:

```python
path = ['div#events', ALL, where(attr('data-type') == 'vote'), slice(20, 40)]
result = select(tree, path)
return ['div#events', *result]
```

The query result is also hiccup. Filtering and pagination don't mutate—they select a subtree. Same shape in, same shape out.

---

**The wire** is HTML. Rendered hiccup down, parsed forms up.

Server to client:
```
SSE: <div id="event-abc" data-type="thought">I remember...</div>
GET: <!doctype html><html>...full page...</html>
```

Client to server:
```
POST /do
<form data-snippet="vote($a, $b, $score)" data-sig="..." data-nonce="...">
  <input name="score" value="12">
  <button data-a="abc" data-b="def">
</form>
```

The server parses the form, extracts values via paths, verifies the signature, evals the snippet. The snippet was authored by the server at render time. The client just held it and sent it back with blanks filled in.

---

**The client** is three lines:

```javascript
new EventSource(location.pathname + '/stream')
  .onmessage = e => Idiomorph.morph(document.body, e.data)
```

Forms POST normally. Server responds with redirect or HTML. SSE pushes updates. The morph library diffs and patches. Focus preserved. Scroll preserved. Event listeners preserved.

The browser is a renderer. That's all.

---

**Writes** flow through signed snippets:

```python
['form', {'action': '/do', 'method': 'post'},
  *snippet_hidden(f"go('{being}', $message)"),
  ['textarea', {'name': 'message'}],
  ['button', 'go']]
```

One route. `/do`. Verify signature, consume nonce, substitute form values, eval. The snippet returns hiccup or a redirect. The reducer appends to the log, updates the tree, broadcasts the patch.

No routing table. No controllers. No parameter binding. No authorization middleware. The signed snippet *is* the capability. If you can see the form, you can do the thing.

---

**The stack:**

```
Depot:              .jsonl (append-only log)
Reducer:            event → tree transform (specter)
Materialized view:  hiccup (HTML as data)
Query:              URL → specter path → subtree
Render:             hiccup → HTML string
Wire:               HTML (both directions)
Client:             morph(document, incoming)
```

No database. No ORM. No API design. No client state. No framework.

---

**Properties:**

*View source tells you everything.* The form carries its behavior. The snippet is right there. Capabilities are visible.

*Refresh works.* GET returns the current materialized view. No client state to reconstruct.

*Back button works.* URLs are queries. Navigation is real.

*Real-time works.* SSE pushes patches. Morph applies them. Same representation as GET.

*Offline doesn't.* The server thinks. That's the trade-off.

---

**The name** comes from the shape: one tree (hiccup) that is the view, the query target, the wire format, and the client state. Parse it, select from it, transform it, render it. All operations on one structure.

HTML was always a tree. We just forgot to treat it like one.