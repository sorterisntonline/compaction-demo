"""Tests for LLM integration."""

import pytest

from consensual_memory.llm import make_llm_voter
from consensual_memory.memory import Memory


class TestMakeLLMVoter:
    def test_basic_voting(self):
        """Test basic voting with mock LLM."""

        def mock_llm(prompt):
            return "25"

        voter = make_llm_voter(mock_llm)
        mem_a = Memory("A")
        mem_b = Memory("B")

        score = voter(mem_a, mem_b)
        assert score == 25

    def test_negative_score(self):
        """Test with negative score."""

        def mock_llm(prompt):
            return "-30"

        voter = make_llm_voter(mock_llm)
        mem_a = Memory("A")
        mem_b = Memory("B")

        score = voter(mem_a, mem_b)
        assert score == -30

    def test_clamping_positive(self):
        """Test that scores are clamped to max +50."""

        def mock_llm(prompt):
            return "100"

        voter = make_llm_voter(mock_llm)
        mem_a = Memory("A")
        mem_b = Memory("B")

        score = voter(mem_a, mem_b)
        assert score == 50

    def test_clamping_negative(self):
        """Test that scores are clamped to min -50."""

        def mock_llm(prompt):
            return "-100"

        voter = make_llm_voter(mock_llm)
        mem_a = Memory("A")
        mem_b = Memory("B")

        score = voter(mem_a, mem_b)
        assert score == -50

    def test_invalid_response(self):
        """Test handling of invalid LLM response."""

        def mock_llm(prompt):
            return "not a number"

        voter = make_llm_voter(mock_llm)
        mem_a = Memory("A")
        mem_b = Memory("B")

        score = voter(mem_a, mem_b)
        assert score == 0  # Should default to 0

    def test_prompt_includes_memories(self):
        """Test that prompt includes memory content."""
        captured_prompt = []

        def mock_llm(prompt):
            captured_prompt.append(prompt)
            return "10"

        voter = make_llm_voter(mock_llm)
        mem_a = Memory("Important memory A")
        mem_b = Memory("Important memory B")

        voter(mem_a, mem_b)

        assert len(captured_prompt) == 1
        prompt = captured_prompt[0]
        assert "Important memory A" in prompt
        assert "Important memory B" in prompt

    def test_whitespace_handling(self):
        """Test that whitespace in response is handled."""

        def mock_llm(prompt):
            return "  15  \n"

        voter = make_llm_voter(mock_llm)
        mem_a = Memory("A")
        mem_b = Memory("B")

        score = voter(mem_a, mem_b)
        assert score == 15


class TestAnthropicVoter:
    def test_import_error(self):
        """Test that missing anthropic package raises helpful error."""
        # This test assumes anthropic might not be installed
        # In production, it would be in dependencies
        try:
            from consensual_memory.llm import AnthropicVoter

            # If import succeeds, that's fine - skip this test
            pytest.skip("anthropic package is installed")
        except ImportError as e:
            assert "anthropic" in str(e).lower()

    def test_voter_creation_with_key(self):
        """Test creating voter with explicit API key."""
        try:
            from consensual_memory.llm import AnthropicVoter

            # This will fail without valid key, but tests the constructor
            voter = AnthropicVoter(api_key="test_key")
            assert voter.model == "claude-3-5-sonnet-20241022"
        except ImportError:
            pytest.skip("anthropic package not installed")

    def test_voter_custom_model(self):
        """Test creating voter with custom model."""
        try:
            from consensual_memory.llm import AnthropicVoter

            voter = AnthropicVoter(api_key="test_key", model="claude-3-opus-20240229")
            assert voter.model == "claude-3-opus-20240229"
        except ImportError:
            pytest.skip("anthropic package not installed")
