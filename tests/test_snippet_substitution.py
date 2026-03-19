"""Regression: /do snippet $key replacement must not break longer keys (e.g. $idx vs $id)."""

from app.app import apply_snippet_substitutions, scrub


def test_longest_keys_first_idx_and_id():
    snippet = "f($id, $idx)"
    form = {"id": "1", "idx": "2"}
    out = apply_snippet_substitutions(snippet, form)
    assert out == f"f({scrub('1')}, {scrub('2')})"


def test_wrong_order_would_corrupt(monkeypatch):
    """Document the bug: replacing $id before $idx mangles $idx."""
    snippet = "f($id, $idx)"

    def bad_order(snippet, form_data):
        for key, value in form_data.items():
            snippet = snippet.replace(f"${key}", scrub(value))
        return snippet

    # dict iteration order id before idx would produce broken output
    out = bad_order(snippet, {"id": "1", "idx": "2"})
    assert "$idx" not in out  # placeholder gone
    assert "f('1', '1'" in out or "f(\"1\", \"1\"" in out  # corrupted: '1' + x from idx


def test_apply_snippet_substitutions_still_valid_python():
    out = apply_snippet_substitutions("f($id, $idx)", {"id": "1", "idx": "2"})
    assert out == "f('1', '2')"
    assert eval(f"lambda f: {out}")(lambda a, b: (a, b)) == ("1", "2")
