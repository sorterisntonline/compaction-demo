"""
Test suite for app/patch.py
Run with: python -m app.test_patch   (from /Users/tommy/programming/consenusal_memory)
"""

import sys
import traceback

from app.patch import (
    One, Two, Three, Four, Five, Six, Seven, Eight, Nine, Ten,
    Selector, Eval, Action,
    MORPH, PREPEND, APPEND, REMOVE, OUTER, CLASSES, ADD, TOGGLE,
    DepthChain, _resolve,
)

PASS = 0
FAIL = 0


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


def check_raises(label, fn, error_substr=None):
    global PASS, FAIL
    try:
        fn()
        print(f"  FAIL  {label}")
        print(f"        expected: ValueError")
        print(f"        got:      no exception")
        FAIL += 1
    except ValueError as e:
        if error_substr and error_substr not in str(e):
            print(f"  FAIL  {label}")
            print(f"        expected error containing: {error_substr!r}")
            print(f"        got: {e!r}")
            FAIL += 1
        else:
            print(f"  PASS  {label}")
            PASS += 1


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
    'document.querySelector("#foo")?.remove()',
)

# ---------------------------------------------------------------------------
# 2. Reversed order is now an error
# ---------------------------------------------------------------------------
section("Reversed order rejected")

check_raises(
    "Two[REMOVE][Selector('#foo')] — Selector after Action is rejected",
    lambda: Two[REMOVE][Selector("#foo")],
    "Selector must come before actions",
)

# ---------------------------------------------------------------------------
# 3. Basic MORPH (Three-chain)
# ---------------------------------------------------------------------------
section("Basic MORPH via Three")

result = Three[Selector("#foo")][MORPH]["<div>hi</div>"]
check(
    "Three[Selector('#foo')][MORPH]['<div>hi</div>']",
    result,
    'Idiomorph.morph(document.querySelector("#foo"), `<div>hi</div>`)',
)

# ---------------------------------------------------------------------------
# 4. MORPH without Selector is rejected
# ---------------------------------------------------------------------------
section("MORPH requires Selector")

check_raises(
    "Two[MORPH][data] — MORPH requires Selector",
    lambda: Two[MORPH],
    "MORPH requires a Selector before it",
)

# ---------------------------------------------------------------------------
# 5. PREPEND (Three-chain)
# ---------------------------------------------------------------------------
section("PREPEND via Three")

result = Three[Selector("#foo")][PREPEND]["<div>hi</div>"]
check(
    "Three[Selector('#foo')][PREPEND]['<div>hi</div>']",
    result,
    'document.querySelector("#foo").insertAdjacentHTML(\'afterbegin\', `<div>hi</div>`)',
)

# ---------------------------------------------------------------------------
# 6. APPEND (Three-chain)
# ---------------------------------------------------------------------------
section("APPEND via Three")

result = Three[Selector("#foo")][APPEND]["<div>hello</div>"]
check(
    "Three[Selector('#foo')][APPEND]['<div>hello</div>']",
    result,
    'document.querySelector("#foo").insertAdjacentHTML(\'beforeend\', `<div>hello</div>`)',
)

# ---------------------------------------------------------------------------
# 7. OUTER (Three-chain)
# ---------------------------------------------------------------------------
section("OUTER via Three")

result = Three[Selector("#foo")][OUTER]["<div>replaced</div>"]
check(
    "Three[Selector('#foo')][OUTER]['<div>replaced</div>']",
    result,
    'document.querySelector("#foo").outerHTML = `<div>replaced</div>`',
)

# ---------------------------------------------------------------------------
# 8. CLASSES + ADD (Four-chain)
# ---------------------------------------------------------------------------
section("CLASSES + ADD via Four")

result = Four[Selector("#foo")][CLASSES][ADD]["active"]
check(
    "Four[Selector('#foo')][CLASSES][ADD]['active']",
    result,
    "document.querySelector(\"#foo\")?.classList.add('active')",
)

# ---------------------------------------------------------------------------
# 9. CLASSES + REMOVE (Four-chain)
# ---------------------------------------------------------------------------
section("CLASSES + REMOVE via Four")

result = Four[Selector("#foo")][CLASSES][REMOVE]["active"]
check(
    "Four[Selector('#foo')][CLASSES][REMOVE]['active']",
    result,
    "document.querySelector(\"#foo\")?.classList.remove('active')",
)

# ---------------------------------------------------------------------------
# 10. CLASSES + TOGGLE (Four-chain)
# ---------------------------------------------------------------------------
section("CLASSES + TOGGLE via Four")

result = Four[Selector("#foo")][CLASSES][TOGGLE]["active"]
check(
    "Four[Selector('#foo')][CLASSES][TOGGLE]['active']",
    result,
    "document.querySelector(\"#foo\")?.classList.toggle('active')",
)

# ---------------------------------------------------------------------------
# 11. CLASSES without Selector is rejected
# ---------------------------------------------------------------------------
section("CLASSES requires Selector")

check_raises(
    "Two[CLASSES][ADD] — CLASSES requires Selector",
    lambda: Two[CLASSES],
    "CLASSES requires a Selector before it",
)

# ---------------------------------------------------------------------------
# 12. ADD without CLASSES is rejected
# ---------------------------------------------------------------------------
section("ADD requires CLASSES")

check_raises(
    "Three[Selector('#foo')][ADD]['x'] — ADD requires CLASSES",
    lambda: Three[Selector("#foo")][ADD],
    "ADD requires CLASSES before it",
)

# ---------------------------------------------------------------------------
# 13. TOGGLE without CLASSES is rejected
# ---------------------------------------------------------------------------
section("TOGGLE requires CLASSES")

check_raises(
    "Three[Selector('#foo')][TOGGLE]['x'] — TOGGLE requires CLASSES",
    lambda: Three[Selector("#foo")][TOGGLE],
    "TOGGLE requires CLASSES before it",
)

# ---------------------------------------------------------------------------
# 14. Eval — lambda form (=> prefix)
# ---------------------------------------------------------------------------
section("Eval with => lambda")

result = Two[Selector("#foo")][Eval("=> $.focus()")]
check(
    "Two[Selector('#foo')][Eval('=> $.focus()')]",
    result,
    '(($) => { $.focus() })(document.querySelector("#foo"))',
)

# ---------------------------------------------------------------------------
# 15. Eval — bare code (One-chain)
# ---------------------------------------------------------------------------
section("Eval bare code via One")

result = One[Eval("document.title = 'yo'")]
check(
    "One[Eval(\"document.title = 'yo'\")]",
    result,
    "document.title = 'yo'",
)

# ---------------------------------------------------------------------------
# 16. Backtick escaping in HTML data
# ---------------------------------------------------------------------------
section("Backtick escaping in HTML data")

result = Three[Selector("#foo")][MORPH]["<div>`tick`</div>"]
check(
    "Backticks in html data are escaped to \\`",
    result,
    r'Idiomorph.morph(document.querySelector("#foo"), `<div>\`tick\`</div>`)',
)

# ---------------------------------------------------------------------------
# 17. ${ escaping in HTML data
# ---------------------------------------------------------------------------
section("${ escaping in HTML data")

result = Three[Selector("#foo")][MORPH]["<div>${x}</div>"]
check(
    "${...} in html data is escaped to \\${",
    result,
    r'Idiomorph.morph(document.querySelector("#foo"), `<div>\${x}</div>`)',
)

# ---------------------------------------------------------------------------
# 18. Hiccup vector as data
# ---------------------------------------------------------------------------
section("Hiccup vector as data")

result = Three[Selector("#foo")][MORPH][["div", "hello"]]
check(
    "Three[Selector('#foo')][MORPH][hiccup vector ['div', 'hello']]",
    result,
    'Idiomorph.morph(document.querySelector("#foo"), `<div>hello</div>`)',
)

# ---------------------------------------------------------------------------
# 19. Selector with double quotes escaped
# ---------------------------------------------------------------------------
section("Selector with special characters")

result = Two[Selector('[data-idx="42"]')][REMOVE]
check(
    'Selector with [data-idx="42"] — double quotes escaped',
    result,
    'document.querySelector("[data-idx=\\"42\\"]")?.remove()',
)

# ---------------------------------------------------------------------------
# 20. Data after data is rejected
# ---------------------------------------------------------------------------
section("Data must be last")

check_raises(
    "Four[Selector('#foo')][MORPH]['first']['second'] — data after data rejected",
    lambda: Four[Selector("#foo")][MORPH]["first"]["second"],
    "Data must be the last item",
)

# ---------------------------------------------------------------------------
# 21. str() on unresolved chain
# ---------------------------------------------------------------------------
section("str() on unresolved DepthChain")

partial = Three[Selector("#foo")][MORPH]
result = str(partial)
check(
    "str(Three[Selector('#foo')][MORPH]) returns morph with empty html",
    result,
    'Idiomorph.morph(document.querySelector("#foo"), ``)',
)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n{'='*50}")
print(f"Results: {PASS} passed, {FAIL} failed")
print(f"{'='*50}")

sys.exit(0 if FAIL == 0 else 1)
