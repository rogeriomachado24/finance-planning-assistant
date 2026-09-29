"""The chat workflow (docs/PHASE1_DESIGN.md, section 6):

    parse_intent ─► validate ─► execute (no LLM) ─► explain ─► END
                       │            └─► ask_clarification ─► END  (the change isn't possible)
                       ├─► ask_clarification ─► END   (no plan yet, unclear amount)
                       └─► decline_unsupported ─► END (advice, out of scope)

Only `parse_intent` and `explain` may use a language model. The state holds plain JSON
(dicts, strings), so the checkpointer that remembers each conversation never has to
deserialise our classes. `previous_intent` carries over between turns for follow-ups.
"""

from datetime import date
from typing import Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session, sessionmaker

from app.agents.explain import DECLINE, NEEDS_PLAN, Facts
from app.agents.intents import (
    ANSWERABLE,
    ExplainAssumptions,
    IntentAdapter,
    NeedsClarification,
    Unsupported,
)
from app.agents.providers import ChatProvider
from app.domain.errors import InvalidInputError
from app.schemas.plan import Rates
from app.schemas.scenarios import ComparedScenarioOut
from app.services.errors import NotFoundError
from app.services.goals import get_active_goal
from app.services.profile import get_profile
from app.tools.run_intent import run_intent

Status = Literal["answered", "clarification", "declined"]


class ChatState(TypedDict, total=False):
    # Input, every turn
    message: str
    today: str
    """ISO date from the API's clock; projections start on the first of that month."""
    default_assumption_set: str
    # Carried over between turns by the checkpointer
    previous_intent: dict | None
    # Output, every turn
    intent: dict
    status: Status
    note: str
    """Clarification text, when status is "clarification"."""
    assumption_set: str | None
    assumptions: dict | None
    results: list[dict]
    reply: str


def build_chat_graph(
    session_factory: sessionmaker[Session], provider: ChatProvider, checkpointer=None
):
    def parse_intent(state: ChatState) -> ChatState:
        previous = state.get("previous_intent")
        intent = provider.parse(
            state["message"], IntentAdapter.validate_python(previous) if previous else None
        )
        # Reset this turn's outputs so nothing leaks from the previous answer.
        return {
            "intent": intent.model_dump(mode="json"),
            "status": "answered",
            "note": "",
            "assumption_set": None,
            "assumptions": None,
            "results": [],
        }

    def validate(state: ChatState) -> ChatState:
        intent = IntentAdapter.validate_python(state["intent"])
        if isinstance(intent, Unsupported):
            return {"status": "declined"}
        if isinstance(intent, NeedsClarification):
            return {"status": "clarification", "note": intent.question}
        if not isinstance(intent, ExplainAssumptions):
            with session_factory() as session:
                try:
                    get_profile(session)
                    get_active_goal(session)
                except NotFoundError:
                    return {"status": "clarification", "note": NEEDS_PLAN}
        return {"status": "answered"}

    def execute(state: ChatState) -> ChatState:
        intent = IntentAdapter.validate_python(state["intent"])
        assert isinstance(intent, ANSWERABLE)
        today = date.fromisoformat(state["today"])
        with session_factory() as session:
            try:
                outcome = run_intent(session, intent, today, state["default_assumption_set"])
            except InvalidInputError as exc:
                return {"status": "clarification", "note": f"I couldn't run that scenario: {exc}."}
        return {
            "assumption_set": outcome.assumption_set,
            "assumptions": Rates.from_domain(outcome.assumptions).model_dump(mode="json"),
            "results": [
                ComparedScenarioOut.from_domain(c).model_dump(mode="json") for c in outcome.results
            ],
        }

    def explain(state: ChatState) -> ChatState:
        facts = Facts(
            intent=IntentAdapter.validate_python(state["intent"]),
            results=[ComparedScenarioOut.model_validate(r) for r in state["results"]],
            assumption_set=state["assumption_set"],
            rates=Rates.model_validate(state["assumptions"]),
        )
        # Remember what was answered, so "and with €300 instead?" can build on it.
        return {"reply": provider.explain(facts), "previous_intent": state["intent"]}

    def ask_clarification(state: ChatState) -> ChatState:
        return {"reply": state["note"]}

    def decline_unsupported(state: ChatState) -> ChatState:
        reason = IntentAdapter.validate_python(state["intent"]).reason  # type: ignore[union-attr]
        return {"reply": DECLINE[reason]}

    graph = StateGraph(ChatState)
    for node in (parse_intent, validate, execute, explain, ask_clarification, decline_unsupported):
        graph.add_node(node.__name__, node)
    graph.add_edge(START, "parse_intent")
    graph.add_edge("parse_intent", "validate")
    graph.add_conditional_edges(
        "validate",
        lambda s: {"answered": "execute", "clarification": "ask_clarification"}.get(
            s["status"], "decline_unsupported"
        ),
    )
    graph.add_conditional_edges(
        "execute", lambda s: "explain" if s["status"] == "answered" else "ask_clarification"
    )
    for node in ("explain", "ask_clarification", "decline_unsupported"):
        graph.add_edge(node, END)
    return graph.compile(checkpointer=checkpointer or InMemorySaver())
