// poem4.js — after the stripping

// poem3 described a prophecy. the double eval as a symmetrical loop.
// SSE one way, POST the other, code as the lingua franca.
// and it was true. but it was also lying a little.

// === WHAT WAS FAKE ===
//
// event_body() was a signed snippet. you clicked, it POSTed,
// the server eval'd it, stuffed JS into _exec_queue,
// returned 204 — "nothing to see here" —
// and hoped the SSE loop would notice within one second.
//
// that wasn't push. that was request/response
// wearing a trenchcoat and sneaking into the SSE channel.
// the client asked. the server answered. but through a mailbox.
// with a polling interval. and a mutable global dict.
//
// the being could be mid-compaction, flooding the queue
// with progress bar updates, and your expand would get
// interleaved, or delayed, or served in the wrong tick.
// the ordering was accidental. the latency was architectural.

// === WHAT CHANGED ===
//
// event_body() now returns the JS string directly.
// PlainTextResponse(js, status_code=200).
// the browser does:
//   const r = await fetch(f.action, { method: 'POST', body: ... });
//   const t = await r.text();
//   if (t) eval(t);
//
// that's it. no queue. no polling. no 100ms. no 1000ms.
// the POST response IS the server's reply, in code.
// the fetch resolves. the eval runs. the row morphs. instant.

// === THE QUEUE IS GONE ===
//
// _exec_queue: deleted.
// broadcast_exec: deleted.
// the poll_tick counter: deleted.
// the 0.1s fast loop that replaced the 1.0s slow loop: deleted.
// all of it was compensation for a bad idea.

// === WHAT SSE DOES NOW ===
//
// only real pushes. only surprises.
//   - the .jsonl file changed on disk (being thought, or was spoken to)
//   - compaction progress ticked
// things the client didn't ask for. things the client can't predict.
// that's what push is FOR.

// === IS IT STILL DUAL EVAL? ===
//
// yes. completely.
//   server evals signed Python from the client: eval(snippet)
//   client evals JS from the server: eval(e.data) and eval(t)
//
// the JS arrives on two channels now — SSE for push, POST for response.
// but eval is eval. the protocol is the same. code as message.
// the only difference is honesty about which direction initiated it.

// === THE DETAILS TAG IS DEAD ===
//
// <details><summary> was a browser primitive pretending to be interaction.
// it toggled locally. it didn't POST. it didn't wait.
// there was a toggle event listener trying to intercept the native
// behavior and bolt a fetch onto it. fiddly. fragile. wrong.
//
// now: each event row is a <form.event>.
// the visible part is a <button.event-row>.
// click it. POST fires. server returns morph JS.
// browser evals. row replaced. full roundtrip.
// no native toggle. no listener. no intermediate state.
//
// events without a body are just <div.event>. not clickable. honest.

// === THE TOPOLOGY ===
//
// before:
//   browser → POST → server (eval snippet, enqueue JS) → 204
//   server → SSE → browser (eval queued JS, eventually)
//   one channel each way, but the POST channel was hollow
//
// after:
//   browser → POST → server (eval snippet, return JS) → browser (eval response)
//   server → SSE → browser (eval pushed JS)
//   POST is a real round-trip. SSE is a real push. each does its job.

// === ONE, TWO, THREE ===
//
// the arity DSL survived all of this unchanged.
// Three[Selector("#evt-{eid}")][MORPH][render_event_expanded(e, idx, memories)]
// still resolves to a JS string. still gets eval'd.
// whether it travels in an SSE event or a POST response doesn't matter.
// the DSL doesn't know or care about transport.
// it just builds code. the rest is plumbing.

// === WHAT render() LOST ===
//
// app.py no longer imports render or RawContent from hiccup.
// every piece of hiccup is data — lists, strings, nothing pre-baked.
// the only place hiccup becomes HTML is inside _resolve() in patch.py,
// when the arity chain finally collapses.
//
// render_events_div returns a list. render_progress_bar returns a list.
// being_content returns a list. all of them: just data.
// Three[...][MORPH][data] is where data becomes string becomes JS becomes DOM.
// one choke point. one renderer. one moment of commitment.

// === poem1 said: ===
// "interactions.js is already half-dead."
//
// poem3 said:
// "interactions.js is a dead man walking."
//
// poem4 says:
// there is no interactions.js.
// there is no _exec_queue.
// there is no <details>.
// there is no render() call in app.py.
//
// the browser is:
//   EventSource, eval, fetch, eval.
// the server is:
//   eval, Three, PlainTextResponse.
// the loop is:
//   ask → answer → push → reflect.
//
// that's the whole system. finally.
