// poem2.js — regurgitation

// the model:
// P is a PatchChain with nothing set.
// every [] call either narrows the chain or executes it.
//
// narrowing: P[Selector("...")] → new chain with selector set
//            P[Action]          → new chain with action set
//            P[Eval("...")]     → new chain with code set
//
// executing: P[hiccup_data]     → _generate(data) → JS string
//            str(P)             → _generate()      → JS string
//
// so the "execute" signal is: item is not a DSL type.
// data, None, a string, a hiccup list — anything unrecognized triggers _generate.

// the problem with [None]:
// REMOVE doesn't have a payload. it's complete at [REMOVE].
// but the current design can't tell "chain is done" from "chain is still building."
// it waits for one more [] to know you're serious.
// so you write [None] as a knock on the door that says "i'm done, go."
// that's the wrong knock. REMOVE already said it.

// arbitrary depth fixes this:
// the chain generates when you USE it, not when you close it.
// __str__ already does this — calling str(P[Selector(...)][REMOVE]) works.
// the fix is: make every complete-enough chain self-aware.
// REMOVE is complete with just a selector. it knows that.
// MORPH needs data. it knows that too.
// when _generate is called with no data on a MORPH, warn.
// when _generate is called with no data on a REMOVE, it's fine — that's the whole move.

// so the depth isn't really "arbitrary" in the sense of unlimited nesting.
// it's "resolve when resolved, not when terminated."
// the chain collapses when used in a string context, in a list, in a broadcast call.
// the author doesn't have to say [None] to trigger it.
// they just use it.

// what arbitrary depth also buys:
// P[Selector(...)][REMOVE]                           → works, __str__ resolves it
// P[Selector(...)][PREPEND][data]                    → works, data resolves it
// P[Selector(...)][Eval("=> $.focus()")]             → works, Eval resolves it
// P[Eval("document.title = 'hello'")]                → works, no selector needed
// P[Selector(...)][Action][data][more][stuff][??]    → last non-DSL item wins, or it accumulates
//
// the last case is the edge. "arbitrary" could mean "keep narrowing forever."
// but realistically: the grammar is selector → action → data.
// arbitrary depth means you can stop at any step where the chain is already executable.
// not that you add a fourth or fifth dimension.

// the symmetry of the whole thing:
// server builds P[...][...][...] — a JS string
// browser receives it via SSE exec event
// browser runs eval(e.data)
// browser mutates
// browser submits form via fetch, no redirect expected
// server receives, builds more P[...][...][...]
// loop.
//
// the browser is stateless in the sense that matters.
// it has DOM. it has the live wire. that's all it needs.
// the Python process is the application.
// poem.js is the nervous system, not the brain.
