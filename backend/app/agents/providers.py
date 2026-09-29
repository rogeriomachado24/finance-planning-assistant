"""Chat providers: what turns a message into an intent, and a result into words.

Keep this switchable (`LLM_PROVIDER`). The mock provider needs no model at all; a
language-model provider implements the same two methods and falls back to the mock
behaviour whenever its own output can't be trusted.
"""

from dataclasses import dataclass
from typing import Protocol

from app.agents.explain import Facts, template_reply
from app.agents.intents import Intent
from app.agents.mock_parser import parse_message
from app.config import Settings

RULES = "rules"
TEMPLATE = "template"


@dataclass(frozen=True)
class Parsed:
    intent: Intent
    source: str
    """Who understood the message: a model name, or "rules"."""


@dataclass(frozen=True)
class Worded:
    text: str
    source: str
    """Who wrote the reply: a model name, or "template"."""


class ChatProvider(Protocol):
    name: str

    def parse(self, message: str, previous: Intent | None) -> Parsed: ...

    def explain(self, facts: Facts) -> Worded: ...

    def is_available(self) -> bool: ...

    def warm_up(self) -> None: ...


class MockProvider:
    """Rule-based parsing and templated explanations. Deterministic; used in tests and CI."""

    name = "mock"

    def parse(self, message: str, previous: Intent | None) -> Parsed:
        return Parsed(parse_message(message, previous), RULES)

    def explain(self, facts: Facts) -> Worded:
        return Worded(template_reply(facts), TEMPLATE)

    def is_available(self) -> bool:
        return True

    def warm_up(self) -> None:
        pass


def build_provider(settings: Settings) -> ChatProvider:
    if settings.llm_provider == "ollama":
        from app.agents.ollama import OllamaProvider  # imported only when used

        return OllamaProvider(
            settings.ollama_model,
            settings.ollama_base_url,
            rewrite_replies=settings.ollama_rewrite_replies,
        )
    return MockProvider()
