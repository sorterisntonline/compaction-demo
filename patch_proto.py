"""
Prototype: depth-declared PatchChain.

from patch import One, Two, Three, Four

One[REMOVE]                                   # 1 deep — but needs a selector...
Two[Selector("#evt-3")][REMOVE]               # 2 deep — fires on 2nd []
Three[Selector("#events")][PREPEND][hiccup]   # 3 deep — fires on 3rd []
One[Eval("document.title = 'yo'")]            # 1 deep — fires immediately

The number is the declared depth of the path.
When the Nth [] is consumed, the chain resolves to a JS string.
"""

from app.hiccup import render


class Selector:
    def __init__(self, query): self.query = query

class Eval:
    def __init__(self, code): self.code = code

class Action:
    def __init__(self, name): self.name = name

MORPH   = Action("MORPH")
PREPEND = Action("PREPEND")
APPEND  = Action("APPEND")
REMOVE  = Action("REMOVE")
OUTER   = Action("OUTER")


def _resolve(items):
    """Interpret a collected list of items as a JS string."""
    selector = None
    action   = None
    code     = None
    data     = None

    for item in items:
        if isinstance(item, Selector): selector = item.query
        elif isinstance(item, Action): action   = item
        elif isinstance(item, Eval):   code     = item.code
        else:                          data     = item

    sel_js = f"document.querySelector('{selector}')" if selector else "null"

    # Eval path
    if code:
        if code.startswith("=>"):
            body = code.replace("=>", "", 1).strip()
            return f"(($) => {{ {body} }})({sel_js})"
        return code

    # Action path
    html = ""
    if data is not None:
        raw = render(data) if not isinstance(data, str) else data
        html = raw.replace("`", "\\`").replace("${", "\\${")

    if action == MORPH:
        return f"Idiomorph.morph({sel_js}, `{html}`)"
    if action == PREPEND:
        return f"Idiomorph.morph({sel_js}, `{html}`, {{morphStyle: 'prepend'}})"
    if action == APPEND:
        return f"Idiomorph.morph({sel_js}, `{html}`, {{morphStyle: 'append'}})"
    if action == REMOVE:
        return f"{sel_js}.remove()"
    if action == OUTER:
        return f"{sel_js}.outerHTML = `{html}`"

    return "console.warn('unresolved patch chain')"


class DepthChain:
    def __init__(self, depth, items=None):
        self.depth = depth
        self.items = items or []

    def __getitem__(self, item):
        items = self.items + [item]
        if len(items) >= self.depth:
            return _resolve(items)      # returns a plain string from here on
        return DepthChain(self.depth, items)

    def __str__(self):
        return _resolve(self.items)

    def __repr__(self):
        return f"DepthChain({self.depth}, pending={self.items})"


One   = DepthChain(1)
Two   = DepthChain(2)
Three = DepthChain(3)
Four  = DepthChain(4)
Five  = DepthChain(5)
Six   = DepthChain(6)
Seven = DepthChain(7)
Eight = DepthChain(8)
Nine  = DepthChain(9)
Ten   = DepthChain(10)


# === EXPERIMENTS ===

if __name__ == "__main__":

    # Standard 3-deep cases
    print(Three[Selector("#events")][PREPEND]["<div>hello</div>"])
    # → Idiomorph.morph(document.querySelector('#events'), `<div>hello</div>`, {morphStyle: 'prepend'})

    print(Two[Selector("#evt-3")][REMOVE])
    # → document.querySelector('#evt-3').remove()

    print(One[Eval("document.title = 'yo'")])
    # → document.title = 'yo'

    print(Two[Selector("#div")][Eval("=> $.focus()")])
    # → (($) => { $.focus() })(document.querySelector('#div'))

    # What does Four unlock? Selector + Action + Eval + data?
    # Or Selector + Selector + Action + data? (nested query?)
    # Undefined for now — the chain just collects and _resolve does its best.
    print(Four[Selector("#parent")][Selector(".child")][MORPH]["<span>hi</span>"])
    # _resolve sees two selectors — currently takes the last one
    # but could be: querySelector('#parent').querySelector('.child')

    # The import line itself is the schema declaration:
    # from patch_proto import One, Two, Three
    # you are saying: I will use paths of depth 1, 2, and 3 in this file.
    # the number is the arity of the path, not the verb.
