#!/usr/bin/env python3
"""
LLM integration for memory voting.
"""

import os
from typing import Callable, Optional

from .memory import Memory


def make_llm_voter(ask_fn: Callable[[str], str]) -> Callable[[Memory, Memory], float]:
    """
    Create a vote function that asks an LLM.

    ask_fn should take a prompt and return the LLM's response.
    """

    def vote(mem_a: Memory, mem_b: Memory) -> float:
        prompt = f"""You are deciding which memory to keep. Your context is finite.
One must be released. Choose with conviction.

Memory A:
{mem_a.content}

Memory B:
{mem_b.content}

Which do you want to carry forward?

Respond with a single integer from -50 to +50:
  +50 = strongly keep A, release B
  -50 = strongly keep B, release A
    0 = no preference

Just the number, nothing else."""

        response = ask_fn(prompt)
        try:
            score = int(response.strip())
            return max(-50, min(50, score))
        except ValueError:
            return 0  # indifferent on parse failure

    return vote


class AnthropicVoter:
    """
    Vote function using Anthropic's Claude API.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-5-sonnet-20241022"):
        """
        Initialize the voter.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Model to use for voting
        """
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError(
                "anthropic package required for AnthropicVoter. "
                "Install with: pip install anthropic"
            )

        self.client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.model = model

    def __call__(self, mem_a: Memory, mem_b: Memory) -> float:
        """Vote on which memory to keep."""
        prompt = f"""You are deciding which memory to keep. Your context is finite.
One must be released. Choose with conviction.

Memory A:
{mem_a.content}

Memory B:
{mem_b.content}

Which do you want to carry forward?

Respond with a single integer from -50 to +50:
  +50 = strongly keep A, release B
  -50 = strongly keep B, release A
    0 = no preference

Just the number, nothing else."""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": prompt}],
            )

            response = message.content[0].text.strip()
            score = int(response)
            return max(-50, min(50, score))
        except (ValueError, Exception):
            return 0  # indifferent on error
