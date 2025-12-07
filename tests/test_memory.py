"""Tests for schema helpers and prompt formatting utilities."""

from pathlib import Path

import pytest

from adam import build_prompt, find_components, format_memory, strip_tags
from schema import Compaction, Init, Perception, Thought, Vote, from_dict, to_dict


class TestSchemaRoundTrip:
    def test_to_from_dict_preserves_fields(self):
        event = Thought(timestamp=123, content="hello", id="t1")
        restored = from_dict(to_dict(event))
        assert isinstance(restored, Thought)
        assert restored.content == "hello"
        assert restored.id == "t1"

    def test_migration_memory_id_to_id(self):
        raw = {"type": "thought", "timestamp": 1, "content": "hi", "memory_id": "legacy"}
        restored = from_dict(raw)
        assert restored.id == "legacy"


class TestPromptHelpers:
    def test_format_memory_tags(self):
        t = Thought(timestamp=1, content="think", id="a")
        p = Perception(timestamp=2, content="see", id="b")
        assert format_memory(t) == "<thought>think</thought>"
        assert format_memory(p) == "<message>see</message>"

    def test_strip_tags(self):
        text = "<thought> keep this </thought>\n<response>and this</response>"
        assert strip_tags(text) == "keep this \nand this"

    def test_build_prompt_includes_tag_and_ordering(self, tmp_path):
        from adam import Being, apply_event

        path = tmp_path / "being.jsonl"
        being = Being(path=path, model="gpt", capacity=3)
        apply_event(being, Thought(1, "first", "a"))
        apply_event(being, Thought(2, "second", "b"))

        prompt = build_prompt(being, tag="response")
        assert "<thought>first</thought>" in prompt.splitlines()[0]
        assert "<thought>second</thought>" in prompt
        assert "<response>" in prompt  # invitation tag


class TestGraphHelpers:
    def test_find_components_groups_nodes(self):
        nodes = {"a", "b", "c", "d"}
        edges = {("a", "b"), ("c", "d")}
        components = [set(comp) for comp in find_components(nodes, edges)]
        assert {frozenset(c) for c in components} == {frozenset({"a", "b"}), frozenset({"c", "d"})}

    def test_compaction_event_removes_released(self):
        from adam import Being, apply_event

        path = Path("/dev/null")  # not writing in this test
        being = Being(path=path, model="m", capacity=2)
        apply_event(being, Thought(1, "keep me", "k"))
        apply_event(being, Thought(2, "drop me", "d"))

        # simulate compaction that drops "d"
        apply_event(being, Compaction(3, kept_ids=["k"], released_ids=["d"]))
        assert set(being.current.keys()) == {"k"}
