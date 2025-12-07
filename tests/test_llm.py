"""Lightweight tests for text helpers in adam.py."""

from adam import format_memory, strip_tags
from schema import Perception, Response, Thought


class TestFormatMemory:
    def test_known_event_types_are_tagged(self):
        assert format_memory(Thought(1, "idea", "t1")) == "<thought>idea</thought>"
        assert format_memory(Perception(1, "ping", "p1")) == "<message>ping</message>"
        assert format_memory(Response(1, "pong", "r1")) == "<response>pong</response>"

    def test_unknown_event_type_returns_none(self):
        class Dummy:
            pass

        assert format_memory(Dummy()) is None


class TestStripTags:
    def test_removes_markup_and_trims(self):
        text = " <thought>hello</thought>\n<response>world</response> "
        assert strip_tags(text) == "hello\nworld"
