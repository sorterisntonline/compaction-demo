"""
Specter-like path navigation and transformation for Python data structures.

Inspired by Red Planet Labs' Specter for Clojure.
"""

from dataclasses import dataclass, field, replace
from typing import Any, Callable


class _NONE:
    """Sentinel for filtered-out values."""
    pass

NONE = _NONE()


class ALL:
    """Navigate into all elements of a sequence."""
    pass


class FIRST:
    """Navigate to first element."""
    pass


class LAST:
    """Navigate to last element."""
    pass


def TYPE(*types):
    """Filter to elements of given type(s)."""
    return lambda x: isinstance(x, types)


@dataclass
class Path:
    """A composable path through data structures."""
    steps: tuple = field(default_factory=tuple)
    
    def __getattr__(self, name: str) -> "Path":
        if name.startswith("_") or name == "steps":
            raise AttributeError(name)
        return Path(self.steps + (("attr", name),))
    
    def __getitem__(self, key) -> "Path":
        if key is ALL:
            return Path(self.steps + (("all",),))
        if key is FIRST:
            return Path(self.steps + (("first",),))
        if key is LAST:
            return Path(self.steps + (("last",),))
        if callable(key):
            return Path(self.steps + (("filter", key),))
        if isinstance(key, (int, str)):
            return Path(self.steps + (("key", key),))
        # Otherwise, bind data and return BoundPath
        return BoundPath(key, self)
    
    def map(self, fn: Callable) -> "Path":
        """Transform each element."""
        return Path(self.steps + (("map", fn),))
    
    def select(self, data) -> list:
        """Navigate path and collect all matching values."""
        results = [data]
        for step in self.steps:
            new_results = []
            match step:
                case ("attr", name):
                    for r in results:
                        new_results.append(getattr(r, name))
                case ("key", k):
                    for r in results:
                        new_results.append(r[k])
                case ("all",):
                    for r in results:
                        new_results.extend(r)
                case ("first",):
                    for r in results:
                        if r:
                            new_results.append(r[0])
                case ("last",):
                    for r in results:
                        if r:
                            new_results.append(r[-1])
                case ("filter", pred):
                    for r in results:
                        if pred(r):
                            new_results.append(r)
                case ("map", fn):
                    for r in results:
                        new_results.append(fn(r))
            results = new_results
        return results
    
    def select_one(self, data) -> Any:
        """Select single value, error if not exactly one."""
        results = self.select(data)
        if len(results) != 1:
            raise ValueError(f"Expected 1 result, got {len(results)}")
        return results[0]
    
    def transform(self, data, fn: Callable) -> Any:
        """Navigate path, apply fn to matches, return new root (immutable)."""
        return self._transform(data, 0, fn)
    
    def _transform(self, data, step_idx: int, fn: Callable) -> Any:
        if step_idx >= len(self.steps):
            return fn(data)
        
        step = self.steps[step_idx]
        match step:
            case ("attr", name):
                old_val = getattr(data, name)
                new_val = self._transform(old_val, step_idx + 1, fn)
                if hasattr(data, "__dataclass_fields__"):
                    return replace(data, **{name: new_val})
                else:
                    # Mutable object, create copy
                    import copy
                    new_data = copy.copy(data)
                    setattr(new_data, name, new_val)
                    return new_data
            
            case ("key", k):
                old_val = data[k]
                new_val = self._transform(old_val, step_idx + 1, fn)
                if isinstance(data, dict):
                    return {**data, k: new_val}
                elif isinstance(data, list):
                    return data[:k] + [new_val] + data[k+1:]
                elif isinstance(data, tuple):
                    return data[:k] + (new_val,) + data[k+1:]
            
            case ("all",):
                results = []
                for item in data:
                    new_item = self._transform(item, step_idx + 1, fn)
                    if new_item is not NONE:
                        results.append(new_item)
                return tuple(results) if isinstance(data, tuple) else results
            
            case ("first",):
                if not data:
                    return data
                new_first = self._transform(data[0], step_idx + 1, fn)
                if new_first is NONE:
                    return data[1:] if isinstance(data, list) else data[1:]
                if isinstance(data, list):
                    return [new_first] + list(data[1:])
                return (new_first,) + data[1:]
            
            case ("last",):
                if not data:
                    return data
                new_last = self._transform(data[-1], step_idx + 1, fn)
                if new_last is NONE:
                    return data[:-1] if isinstance(data, list) else data[:-1]
                if isinstance(data, list):
                    return list(data[:-1]) + [new_last]
                return data[:-1] + (new_last,)
            
            case ("filter", pred):
                if not pred(data):
                    return NONE  # Signal removal
                return self._transform(data, step_idx + 1, fn)
        
        return data
    
    def setval(self, data, val) -> Any:
        """Set all matches to val."""
        return self.transform(data, lambda _: val)
    
    def __repr__(self):
        parts = []
        for step in self.steps:
            match step:
                case ("attr", name): parts.append(f".{name}")
                case ("key", k): parts.append(f"[{k!r}]")
                case ("all",): parts.append("[ALL]")
                case ("first",): parts.append("[FIRST]")
                case ("last",): parts.append("[LAST]")
                case ("filter", _): parts.append("[<filter>]")
                case ("map", _): parts.append(".map(<fn>)")
        return "P" + "".join(parts) if parts else "P"


@dataclass
class BoundPath:
    """A path bound to specific data. Reads left-to-right: P[data].attr[ALL].select()"""
    data: Any
    path: Path
    
    def __getattr__(self, name: str) -> "BoundPath":
        if name.startswith("_") or name in ("data", "path"):
            raise AttributeError(name)
        return BoundPath(self.data, Path(self.path.steps + (("attr", name),)))
    
    def __getitem__(self, key) -> "BoundPath":
        if key is ALL:
            return BoundPath(self.data, Path(self.path.steps + (("all",),)))
        if key is FIRST:
            return BoundPath(self.data, Path(self.path.steps + (("first",),)))
        if key is LAST:
            return BoundPath(self.data, Path(self.path.steps + (("last",),)))
        if callable(key):
            return BoundPath(self.data, Path(self.path.steps + (("filter", key),)))
        return BoundPath(self.data, Path(self.path.steps + (("key", key),)))
    
    def map(self, fn: Callable) -> "BoundPath":
        return BoundPath(self.data, Path(self.path.steps + (("map", fn),)))
    
    def select(self) -> list:
        return self.path.select(self.data)
    
    def select_one(self) -> Any:
        return self.path.select_one(self.data)
    
    def transform(self, fn: Callable) -> Any:
        return self.path.transform(self.data, fn)
    
    def setval(self, val) -> Any:
        return self.path.setval(self.data, val)
    
    def __repr__(self):
        return f"BoundPath({self.data!r}, {self.path!r})"


# Convenient entry point
P = Path()


# --- Tests ---

def test_select_attr():
    @dataclass
    class Point:
        x: int
        y: int
    
    p = Point(3, 4)
    assert P.x.select(p) == [3]
    assert P.y.select(p) == [4]
    print("✓ select_attr")


def test_select_key():
    d = {"a": 1, "b": 2}
    assert P["a"].select(d) == [1]
    
    lst = [10, 20, 30]
    assert P[1].select(lst) == [20]
    print("✓ select_key")


def test_select_all():
    lst = [1, 2, 3]
    assert P[ALL].select(lst) == [1, 2, 3]
    
    nested = [[1, 2], [3, 4]]
    assert P[ALL][ALL].select(nested) == [1, 2, 3, 4]
    print("✓ select_all")


def test_select_nested():
    @dataclass
    class Person:
        name: str
        age: int
    
    people = [Person("alice", 30), Person("bob", 25)]
    assert P[ALL].name.select(people) == ["alice", "bob"]
    assert P[ALL].age.select(people) == [30, 25]
    print("✓ select_nested")


def test_select_filter():
    nums = [1, 2, 3, 4, 5]
    assert P[ALL][lambda x: x > 3].select(nums) == [4, 5]
    
    @dataclass
    class Item:
        name: str
        price: int
    
    items = [Item("apple", 1), Item("laptop", 1000), Item("book", 20)]
    assert P[ALL][lambda i: i.price > 10].name.select(items) == ["laptop", "book"]
    print("✓ select_filter")


def test_transform_attr():
    @dataclass
    class Point:
        x: int
        y: int
    
    p = Point(3, 4)
    p2 = P.x.transform(p, lambda x: x * 2)
    assert p2 == Point(6, 4)
    assert p == Point(3, 4)  # original unchanged
    print("✓ transform_attr")


def test_transform_key():
    d = {"a": 1, "b": 2}
    d2 = P["a"].transform(d, lambda x: x + 10)
    assert d2 == {"a": 11, "b": 2}
    assert d == {"a": 1, "b": 2}  # original unchanged
    print("✓ transform_key")


def test_transform_all():
    lst = [1, 2, 3]
    lst2 = P[ALL].transform(lst, lambda x: x * 2)
    assert lst2 == [2, 4, 6]
    print("✓ transform_all")


def test_transform_nested():
    @dataclass
    class Person:
        name: str
        age: int
    
    @dataclass 
    class Team:
        members: list
    
    team = Team([Person("alice", 30), Person("bob", 25)])
    team2 = P.members[ALL].age.transform(team, lambda a: a + 1)
    
    assert team2.members[0].age == 31
    assert team2.members[1].age == 26
    assert team.members[0].age == 30  # original unchanged
    print("✓ transform_nested")


def test_setval():
    @dataclass
    class Config:
        debug: bool
        level: int
    
    cfg = Config(False, 5)
    cfg2 = P.debug.setval(cfg, True)
    assert cfg2.debug == True
    assert cfg.debug == False
    print("✓ setval")


def test_first_last():
    lst = [1, 2, 3]
    assert P[FIRST].select(lst) == [1]
    assert P[LAST].select(lst) == [3]
    
    lst2 = P[FIRST].transform(lst, lambda x: x * 10)
    assert lst2 == [10, 2, 3]
    
    lst3 = P[LAST].transform(lst, lambda x: x * 10)
    assert lst3 == [1, 2, 30]
    print("✓ first_last")


def test_filter_transform():
    # Filter should remove non-matching items during transform
    lst = [1, 2, 3, 4, 5]
    result = P[ALL][lambda x: x > 2].transform(lst, lambda x: x * 10)
    assert result == [30, 40, 50], f"Got {result}"
    print("✓ filter_transform")


def test_repr():
    assert repr(P.members[ALL].age) == "P.members[ALL].age"
    assert repr(P[FIRST]) == "P[FIRST]"
    assert repr(P) == "P"
    print("✓ repr")


def test_bound_path():
    @dataclass
    class Team:
        members: list
    
    @dataclass
    class Person:
        name: str
        age: int
    
    team = Team([Person("alice", 30), Person("bob", 25)])
    
    # Left-to-right: P[data].path.select()
    names = P[team].members[ALL].name.select()
    assert names == ["alice", "bob"]
    
    ages = P[team].members[ALL].age.select()
    assert ages == [30, 25]
    
    # Transform works too
    team2 = P[team].members[ALL].age.transform(lambda a: a + 1)
    assert team2.members[0].age == 31
    assert team.members[0].age == 30  # original unchanged
    
    print("✓ bound_path")


if __name__ == "__main__":
    test_select_attr()
    test_select_key()
    test_select_all()
    test_select_nested()
    test_select_filter()
    test_transform_attr()
    test_transform_key()
    test_transform_all()
    test_transform_nested()
    test_setval()
    test_first_last()
    test_filter_transform()
    test_repr()
    test_bound_path()
    print("\n✅ All tests passed!")

