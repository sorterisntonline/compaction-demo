"""
Test suite for app/patch.py
Run with: python -m app.test_patch   (from /Users/tommy/programming/consenusal_memory)
"""

import sys
import traceback

from app.patch import (
    One, Two, Three, Four, Five, Six, Seven, Eight, Nine, Ten,
    Selector, Eval, Action,
    MORPH, PREPEND, APPEND, REMOVE, OUTER,
    DepthChain, _resolve,
)

PASS = 0
FAIL = 0
NOTES = []


def check(label, got, expected):
    global PASS, FAIL
    if got == expected:
        print(f"  PASS  {label}")
        PASS += 1
    else:
        print(f"  FAIL  {label}")
        print(f"        expected: {expected!r}")
        print(f"        got:      {got!r}")
        FAIL += 1


def note(label, observation):
    """Record a surprising / noteworthy behaviour without pass/fail."""
    print(f"  NOTE  {label}")
    print(f"        {observation}")
    NOTES.append((label, observation))


def section(title):
    print(f"\n=== {title} ===")


# ---------------------------------------------------------------------------
# 1. Basic REMOVE (Two-chain)
# ---------------------------------------------------------------------------
section("Basic REMOVE via Two")

result = Two[Selector("#foo")][REMOVE]
check(
    "Two[Selector('#foo')][REMOVE]",
    result,
    'document.querySelector("#foo").remove()',
)

# REMOVE with no selector
result_no_sel = Two[REMOVE][Selector("#foo")]
check(
    "Two[REMOVE][Selector('#foo')] (reversed order)",
    result_no_sel,
    'document.querySelector("#foo").remove()',
)

# ---------------------------------------------------------------------------
# 2. Basic MORPH (Three-chain)
# ---------------------------------------------------------------------------
section("Basic MORPH via Three")

result = Three[Selector("#foo")][MORPH]["<div>hi</div>"]
check(
    "Three[Selector('#foo')][MORPH]['<div>hi</div>']",
    result,
    'Idiomorph.morph(document.querySelector("#foo"), `<div>hi</div>`)',
)

# ---------------------------------------------------------------------------
# 3. PREPEND (Three-chain)
# ---------------------------------------------------------------------------
section("PREPEND via Three")

result = Three[Selector("#foo")][PREPEND]["<div>hi</div>"]
check(
    "Three[Selector('#foo')][PREPEND]['<div>hi</div>']",
    result,
    'Idiomorph.morph(document.querySelector("#foo"), `<div>hi</div>`, {morphStyle: \'prepend\'})',
)

# ---------------------------------------------------------------------------
# 4. APPEND (Three-chain)
# ---------------------------------------------------------------------------
section("APPEND via Three")

result = Three[Selector("#foo")][APPEND]["<div>hello</div>"]
check(
    "Three[Selector('#foo')][APPEND]['<div>hello</div>']",
    result,
    'Idiomorph.morph(document.querySelector("#foo"), `<div>hello</div>`, {morphStyle: \'append\'})',
)

# ---------------------------------------------------------------------------
# 5. OUTER (Three-chain)
# ---------------------------------------------------------------------------
section("OUTER via Three")

result = Three[Selector("#foo")][OUTER]["<div>replaced</div>"]
check(
    "Three[Selector('#foo')][OUTER]['<div>replaced</div>']",
    result,
    'document.querySelector("#foo").outerHTML = `<div>replaced</div>`',
)

# ---------------------------------------------------------------------------
# 6. Eval — lambda form (=> prefix)
# ---------------------------------------------------------------------------
section("Eval with => lambda")

result = Two[Selector("#foo")][Eval("=> $.focus()")]
check(
    "Two[Selector('#foo')][Eval('=> $.focus()')]",
    result,
    '(($) => { $.focus() })(document.querySelector("#foo"))',
)

# ---------------------------------------------------------------------------
# 7. Eval — bare code (no => prefix, One-chain)
# ---------------------------------------------------------------------------
section("Eval bare code via One")

result = One[Eval("document.title = 'yo'")]
check(
    "One[Eval(\"document.title = 'yo'\")]",
    result,
    "document.title = 'yo'",
)

# ---------------------------------------------------------------------------
# 8. Eval bare code — selector ignored?
# ---------------------------------------------------------------------------
section("Eval bare code with selector present")

result = Two[Selector("#foo")][Eval("alert(1)")]
# The selector is in items but the code branch just returns the code string.
# Document what actually happens.
note(
    "Two[Selector('#foo')][Eval('alert(1)')] — selector silently dropped",
    f"Got: {result!r}  (selector is ignored; bare Eval always returns raw code)",
)
# Still verify the actual return value is just the code:
check(
    "Two[Selector('#foo')][Eval('alert(1)')] returns bare code",
    result,
    "alert(1)",
)

# ---------------------------------------------------------------------------
# 9. Eval => form with no selector
# ---------------------------------------------------------------------------
section("Eval => form with no selector")

result = Two[Eval("=> console.log($)")][None]   # pad to depth 2
# What is the sel_js when selector is None?
note(
    "Eval => with no Selector — sel_js fallback",
    f"Got: {result!r}",
)

# A more natural single-item chain would be One[Eval("=> ...")] but the =>
# branch uses sel_js, so let's also test Two where the second item is not a Selector:
result2 = Two[Eval("=> $.blur()")][REMOVE]
# Two items, but no Selector — what happens?
note(
    "Two[Eval('=> $.blur()')][REMOVE] — no Selector, action in items",
    f"Got: {result2!r}  (action is in items but code branch fires first)",
)

# ---------------------------------------------------------------------------
# 10. Wrong depth — Two for MORPH (needs data, but Two resolves at 2 items)
# ---------------------------------------------------------------------------
section("Wrong depth: Two for MORPH (missing data arg)")

result = Two[Selector("#bar")][MORPH]
# At depth 2 this resolves immediately. MORPH with no data → html = "".
check(
    "Two[Selector('#bar')][MORPH] resolves with empty html",
    result,
    'Idiomorph.morph(document.querySelector("#bar"), ``)',
)
note(
    "Two used for MORPH resolves prematurely with empty html",
    f"Got: {result!r}",
)

# ---------------------------------------------------------------------------
# 11. Wrong depth — One for REMOVE (resolved before adding selector)
# ---------------------------------------------------------------------------
section("Wrong depth: One for REMOVE (resolves immediately)")

result = One[REMOVE]
# Resolves with depth=1 after first item. No selector → sel_js = "null".
check(
    "One[REMOVE] → null.remove()",
    result,
    "null.remove()",
)
note(
    "One[REMOVE] resolves with 'null' selector",
    f"Got: {result!r}",
)

# ---------------------------------------------------------------------------
# 12. Wrong depth — Four for a REMOVE that only needs Two
# ---------------------------------------------------------------------------
section("Wrong depth: Four for REMOVE (extra args)")

mid = Four[Selector("#baz")][REMOVE]
# Depth=4, only 2 items → still a DepthChain, not yet resolved
check(
    "Four[Selector('#baz')][REMOVE] is still a DepthChain (not resolved)",
    isinstance(mid, DepthChain),
    True,
)
# Add two more items to force resolution
result = mid["extra1"]["extra2"]
# extra1 and extra2 are plain strings → data; last one wins
note(
    "Four[Selector('#baz')][REMOVE]['extra1']['extra2'] — data overrides REMOVE?",
    f"Got: {result!r}  (both extra strings are 'data'; last string wins; REMOVE action present but data also present)",
)

# ---------------------------------------------------------------------------
# 13. Backtick escaping in HTML data
# ---------------------------------------------------------------------------
section("Backtick escaping in HTML data")

result = Three[Selector("#foo")][MORPH]["<div>`tick`</div>"]
check(
    "Backticks in html data are escaped to \\`",
    result,
    r'Idiomorph.morph(document.querySelector("#foo"), `<div>\`tick\`</div>`)',
)

# ---------------------------------------------------------------------------
# 14. ${ escaping in HTML data
# ---------------------------------------------------------------------------
section("${ escaping in HTML data")

result = Three[Selector("#foo")][MORPH]["<div>${x}</div>"]
check(
    "${...} in html data is escaped to \\${",
    result,
    r'Idiomorph.morph(document.querySelector("#foo"), `<div>\${x}</div>`)',
)

# ---------------------------------------------------------------------------
# 15. str() on an unresolved chain
# ---------------------------------------------------------------------------
section("str() on unresolved DepthChain")

partial = Three[Selector("#foo")][MORPH]   # only 2 items, depth=3 → DepthChain
result = str(partial)
# __str__ calls _resolve(self.items) — MORPH with no data → html = ""
check(
    "str(Three[Selector('#foo')][MORPH]) returns unresolved warn or morph with empty html",
    result,
    'Idiomorph.morph(document.querySelector("#foo"), ``)',
)
note(
    "str() on unresolved Three chain (missing data) returns morph with empty html",
    f"Got: {result!r}  — no warning is emitted; silent empty-morph",
)

# repr form — DepthChain has no __repr__, so Python uses default
partial2 = Three[Selector("#foo")]
repr_result = repr(partial2)
note(
    "repr() of unresolved DepthChain (1 item)",
    f"Got: {repr_result!r}",
)

# ---------------------------------------------------------------------------
# 16. Chaining beyond declared depth (result is a string, not DepthChain)
# ---------------------------------------------------------------------------
section("Chaining beyond declared depth")

resolved = Two[Selector("#foo")][REMOVE]   # → str
assert isinstance(resolved, str), "sanity: resolved should be str"

try:
    beyond = resolved["extra"]
    note(
        "str['extra'] after resolution — Python treats it as string indexing",
        f"Got: {beyond!r}  (str subscript with non-int key raises TypeError ... or does it?)",
    )
except TypeError as e:
    note(
        "str['extra'] after resolution raises TypeError",
        f"TypeError: {e}",
    )
except Exception as e:
    note(
        "str['extra'] after resolution raises unexpected exception",
        f"{type(e).__name__}: {e}",
    )

# ---------------------------------------------------------------------------
# 17. Hiccup data (non-str data) rendered through hiccup.render
# ---------------------------------------------------------------------------
section("Hiccup vector as data")

result = Three[Selector("#foo")][MORPH][["div", "hello"]]
check(
    "Three[Selector('#foo')][MORPH][hiccup vector ['div', 'hello']]",
    result,
    'Idiomorph.morph(document.querySelector("#foo"), `<div>hello</div>`)',
)

# ---------------------------------------------------------------------------
# 18. Selector with special characters
# ---------------------------------------------------------------------------
section("Selector with special characters")

result = Two[Selector("[data-id='42']")][REMOVE]
check(
    "Selector with attribute selector [data-id='42']",
    result,
    'document.querySelector("[data-id=\'42\']").remove()',
)
note(
    "Selector with single quotes — they are NOT escaped in sel_js",
    f"Got: {result!r}  (single quotes inside querySelector string not escaped)",
)

# ---------------------------------------------------------------------------
# 18b. Selector with double quotes (the bug that broke event expand)
# ---------------------------------------------------------------------------
section("Selector with double quotes in attribute value")

result = Two[Selector('[data-idx="42"]')][REMOVE]
check(
    'Selector with [data-idx="42"] — double quotes escaped',
    result,
    'document.querySelector("[data-idx=\\"42\\"]").remove()',
)

# ---------------------------------------------------------------------------
# 19. Multiple Selectors in one chain — last one wins?
# ---------------------------------------------------------------------------
section("Multiple Selectors in one chain")

result = Three[Selector("#foo")][Selector("#bar")][REMOVE]
# Both selectors are in items; the loop assigns selector = item.query each time
# so the last one should win
check(
    "Three[Sel('#foo')][Sel('#bar')][REMOVE] — last selector wins",
    result,
    'document.querySelector("#bar").remove()',
)
note(
    "Multiple Selectors: last one silently wins; no error raised",
    f"Got: {result!r}",
)

# ---------------------------------------------------------------------------
# 20. No selector, no action, no code — fallback path
# ---------------------------------------------------------------------------
section("Fallback: no selector, no action, no code")

result = One[None]
# None goes to the `else` branch → data = None; no action → falls through to warn
note(
    "One[None] — None is treated as data (data branch); falls through to warn",
    f"Got: {result!r}",
)

result2 = One["stray string"]
note(
    "One['stray string'] — string treated as data, no action → falls through to warn",
    f"Got: {result2!r}",
)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n{'='*50}")
print(f"Results: {PASS} passed, {FAIL} failed, {len(NOTES)} notes")
print(f"{'='*50}")

if NOTES:
    print("\nNoteworthy / Surprising Behaviors:")
    for label, obs in NOTES:
        print(f"  - {label}")
        print(f"    {obs}")

sys.exit(0 if FAIL == 0 else 1)
