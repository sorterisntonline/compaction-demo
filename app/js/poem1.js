// poem1.js — initial reactions

// First reaction: relief.
// P[Selector("#events")][PREPEND][data]
// reads like a sentence. like an instruction you'd give out loud.
// "prepend this to #events." done.

// Second reaction: recognition.
// this is what htmx always wanted to be when it grew up —
// not attributes scattered across HTML,
// but intent concentrated in one place, in Python,
// where you can reason about it.

// Third reaction: the REMOVE case is elegant in a way that's almost funny.
// P[Selector(f"#evt-{idx}")][REMOVE][None]
// the [None] at the end is honest.
// most DSLs would hide it. this one makes you say it.
// "remove this. with nothing."

// Fourth reaction: the Eval lambda is the escape hatch done right.
// P[Selector("#div")][Eval("=> $.style.width = '100px'")]
// $ is the selected element. you're writing JS but it's tethered.
// it can't float free and mutate something you didn't aim at.

// Fifth reaction (the one that matters):
// interactions.js is already half-dead.
// the toggle/expand logic, the copy-to-clipboard,
// all of it could become P[...][...][...] calls
// living in Python, next to the data that motivates them.
// the JS file shrinks to just: listen, eval, submit.
// three lines. a dumb terminal.

// the thing that gives me pause:
// the backtick escaping in _generate() is load-bearing and fragile.
// safe_html = str(html).replace("`", "\\`").replace("${", "\\${")
// one weird unicode lookalike and you have an injection.
// the DSL is beautiful. the string boundary is not.
// that seam wants a proper templating approach, not replace().

// but overall: yes.
// this is the right shape.
// Python holds the state, holds the intent, holds the structure.
// the browser holds nothing except a live wire to here.
