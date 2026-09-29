"""Chat providers: what turns a message into an intent, and a result into words.

Keep this switchable (`LLM_PROVIDER`). The mock provider needs no model at all; a
language-model provider must implement the same two methods.
"""

from typing import Protocol

from app.agents.explain import Facts, template_reply
from app.agents.intents import Intent
from app.agents.mock_parser import parse_message
from app.config import Settings


class ChatProvider(Protocol):
    name: str

    def parse(self, message: str, previous: Intent | None) -> Intent: ...

    def explain(self, facts: Facts) -> str: ...


class MockProvider:
    """Rule-based parsing and templated explanations. Deterministic; used in tests and CI."""

    name = "mock"

    def parse(self, message: str, previous: Intent | None) -> Intent:
        return parse_message(message, previous)

    def explain(self, facts: Facts) -> str:
        return template_reply(facts)


def build_provider(settings: Settings) -> ChatProvider:
    if settings.llm_provider == "mock":
        return MockProvider()
    raise NotImplementedError(f"LLM provider {settings.llm_provider!r} is not available yet")
