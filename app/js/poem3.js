// poem3.js — full understanding of the symmetrical system

// === THE DOUBLE EVAL ===
//
// There are two runtimes.
// Python on the server. JavaScript in the browser.
// Each one can be programmed by the other.
// Each one evals what the other sends.
//
// Server → Browser:
//   SSE pushes a string.
//   Browser runs: eval(e.data)
//   The browser becomes whatever the server says it is.
//
// Browser → Server:
//   Form submits a signed snippet.
//   Server runs: eval(snippet)
//   The server does whatever the form says — but only what it already agreed to.
//
// This is the symmetry. Not a metaphor. Literally:
//   two processes, two evals, one loop.


// === THE SIGNING SYSTEM ===
//
// The server → browser direction is open. SSE is authenticated at the
// connection level. Once you're in, the server can send anything. eval runs it.
// That's intentional. The server is the author. It can write whatever it wants.
//
// The browser → server direction is locked. The server signs every snippet
// at render time with HMAC + a one-time nonce. The browser can only submit
// code the server already wrote. It cannot compose new Python. It cannot replay.
// scrub() runs repr() on every substituted value — Python quoting itself.
//
// So the browser has capabilities, not permissions.
// "Here is a signed voucher for: go('tommy', $message)"
// You may redeem this once. You may fill in $message. That's all.
//
// The server trusts itself. The browser executes what it's handed.
// The server only executes what it handed to the browser first.


// === THE P[...] DSL ===
//
// P is a PatchChain. It builds a JS string using Python's __getitem__.
// Every [] call either narrows the intent or resolves it.
//
// P[Selector("#events")]          → chain with selector set
// P[Selector("#events")][PREPEND] → chain with selector + action set
// P[Selector("#events")][PREPEND][hiccup_data] → resolves: returns JS string
//
// The types are the grammar:
//   Selector("...")  — where
//   Action (MORPH, PREPEND, APPEND, REMOVE, OUTER) — how
//   Eval("...")      — escape hatch: run arbitrary JS, $ is the selected element
//   data             — what (hiccup list, string, None — anything not a DSL type)
//
// When item is a DSL type: narrow. Return new chain.
// When item is not a DSL type: resolve. Call _generate(item). Return JS string.
// When chain is used as string (__str__): resolve with no data.
//
// So REMOVE doesn't need [None]. It's complete when it's complete.
// str(P[Selector(f"#evt-{idx}")][REMOVE]) is already the JS string.
// The chain knows when it has enough.
//
// The output is a JS string like:
//   Idiomorph.morph(document.querySelector('#events'), `<div>...</div>`, {morphStyle: 'prepend'})
//   document.querySelector('#evt-3').remove()
//   (($) => { $.style.width = '100px' })(document.querySelector('#div'))


// === HOW THEY CONNECT ===
//
// The P DSL generates JS strings.
// Those strings travel over SSE as exec events.
// The browser evals them.
//
// The signed snippets generate Python calls.
// Those calls travel over POST to /do.
// The server evals them.
//
// Python writes JS. JS triggers Python. Python writes JS again.
//
// The browser holds: DOM, the live SSE wire, a tiny poem.js.
// The server holds: all state, all intent, all logic.
// The browser is a screen. The server is the application.
//
// Nothing leaks the other way. The browser never knows *why*
// an element was removed. The server never knows *how* the
// browser rendered it. Each side speaks its own language.
// The loop is the interface.


// === THE DEPTH OF THE LOOP ===
//
// User types in textarea.
// interactions.js saves draft to localStorage. (still client-side, for now)
//
// User submits form.
// poem.js intercepts: fetch POST to /do, no redirect expected, form resets.
//
// /do verifies signature, consumes nonce, evals snippet.
// snippet calls go(being_file, message).
// go() spins a thread: receive(being, message), then think(being).
// think() writes new events to the .jsonl file.
//
// SSE loop wakes: mtime changed.
// render_events_div() re-renders all events as Hiccup → HTML.
// sse_event() wraps it: "event: app\ndata: #events\ndata: <html>..."
//
// Browser receives SSE app event.
// applyPatch() finds #events, runs Idiomorph.morph().
// DOM updates in place. Existing elements survive. New ones appear.
//
// The being thought. The browser reflects it. No page load. No framework.
// Just: file changed → SSE fired → Idiomorph morphed.


// === WHAT THIS UNLOCKS WITH P[...] ===
//
// Right now the SSE pushes whole #events re-renders.
// With P[...], it could push surgical patches instead:
//
//   P[Selector(f"#evt-{new_id}")][PREPEND][render_event(e, i)]
//   P[Selector("#status")][MORPH]["thinking..."]
//   P[Selector("#compaction-progress")][REMOVE]
//
// Each one is a line of Python. Each one generates one line of JS.
// The server describes exactly what changed. Not "here is the whole list."
// "Here: prepend this one event. Here: update this status. Here: remove that bar."
//
// Idiomorph handles the DOM surgery.
// Python handles the intent.
// The browser handles nothing except execution.
//
// interactions.js is a dead man walking.
// copy-to-clipboard: P[Selector(".copy-btn")][Eval("=> navigator.clipboard.writeText($.parentElement.innerText)")]
// That's it. That's the whole feature. In Python. Next to the data it operates on.


// === THE NAME ===
//
// Not "symmetrical" in the sense of identical.
// Symmetrical in the sense of: each side has the same power over the other.
// Each side evals. Each side can program the other.
// The consent is elsewhere — in the beings, in the memory, in what they choose to think.
// But the protocol is symmetrical all the way down.
