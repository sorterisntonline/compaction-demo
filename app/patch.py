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
    selector = None
    action   = None
    code     = None
    data     = None

    for item in items:
        if isinstance(item, Selector): selector = item.query
        elif isinstance(item, Action): action   = item
        elif isinstance(item, Eval):   code     = item.code
        else:                          data     = item

    if selector:
        safe = selector.replace("\\", "\\\\").replace('"', '\\"')
        sel_js = f'document.querySelector("{safe}")'
    else:
        sel_js = "null"

    if code:
        if code.startswith("=>"):
            body = code.replace("=>", "", 1).strip()
            return f"(($) => {{ {body} }})({sel_js})"
        return code

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
            return _resolve(items)
        return DepthChain(self.depth, items)

    def __str__(self):
        return _resolve(self.items)


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
