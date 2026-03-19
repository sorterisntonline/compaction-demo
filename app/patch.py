from app.hiccup import render


class Selector:
    def __init__(self, query): self.query = query

class Eval:
    def __init__(self, code): self.code = code

class Action:
    def __init__(self, name, requires=None):
        self.name = name
        self.requires = requires  # Selector or Action that must precede this

MORPH   = Action("MORPH", requires=Selector)
PREPEND = Action("PREPEND", requires=Selector)
APPEND  = Action("APPEND", requires=Selector)
REMOVE  = Action("REMOVE")
OUTER   = Action("OUTER", requires=Selector)
CLASSES = Action("CLASSES", requires=Selector)
ADD     = Action("ADD", requires=CLASSES)
TOGGLE  = Action("TOGGLE", requires=CLASSES)


def _validate_step(items):
    item = items[-1]
    prior = items[:-1]

    prior_actions = [x for x in prior if isinstance(x, Action)]
    has_selector = any(isinstance(x, Selector) for x in prior)
    prior_data = [x for x in prior if not isinstance(x, (Selector, Action, Eval))]

    # Data must be last — nothing comes after data
    if prior_data:
        raise ValueError(f"Data must be the last item in the chain")

    # Selector must come before any actions
    if isinstance(item, Selector) and prior_actions:
        raise ValueError(f"Selector must come before actions, not after {prior_actions[-1].name}")

    # Action requires check
    if isinstance(item, Action) and item.requires is not None:
        if item.requires is Selector:
            if not has_selector:
                raise ValueError(f"{item.name} requires a Selector before it")
        elif isinstance(item.requires, Action):
            if item.requires not in prior_actions:
                raise ValueError(f"{item.name} requires {item.requires.name} before it")


def _resolve(items):
    selector = None
    actions  = []
    code     = None
    data     = None

    for item in items:
        if isinstance(item, Selector): selector = item.query
        elif isinstance(item, Action): actions.append(item)
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

    if CLASSES in actions:
        if REMOVE in actions:
            return f"{sel_js}?.classList.remove('{data}')"
        if ADD in actions:
            return f"{sel_js}?.classList.add('{data}')"
        if TOGGLE in actions:
            return f"{sel_js}?.classList.toggle('{data}')"

    action = actions[0] if actions else None

    if action == MORPH:
        return f"Idiomorph.morph({sel_js}, `{html}`)"
    if action == PREPEND:
        return f"{sel_js}.insertAdjacentHTML('afterbegin', `{html}`)"
    if action == APPEND:
        return f"{sel_js}.insertAdjacentHTML('beforeend', `{html}`)"
    if action == REMOVE:
        return f"{sel_js}?.remove()"
    if action == OUTER:
        return f"{sel_js}.outerHTML = `{html}`"

    return "console.warn('unresolved patch chain')"


class DepthChain:
    def __init__(self, depth, items=None):
        self.depth = depth
        self.items = items or []

    def __getitem__(self, item):
        items = self.items + [item]
        _validate_step(items)
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
