"""Ollama provider: a local language model parses messages and words replies.

The model is never trusted with numbers:
- Parsing: it fills a flat form (`ModelRequest`), constrained by Ollama to a JSON schema.
  Every amount it reports must appear in the user's message (or be 0 for "stop
  investing"), otherwise its answer is rejected and the rule-based parser is used.
- Explaining: it rewrites the templated facts. If the reply contains any number that
  isn't in those facts, or reads like advice, the template is used instead. The
  assumptions and the disclaimer are always appended by code.
"""

import json
import logging
import re
from typing import Literal

from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field, ValidationError

from app.agents import plan_model
from app.agents.explain import Facts, footer, template_body, template_reply
from app.agents.grounding import as_number, numbers_in, only_known_numbers
from app.agents.intents import (
    CompareScenarios,
    ExplainAssumptions,
    GoalDate,
    Intent,
    Likelihood,
    NeedsClarification,
    RequiredContribution,
    RunProjection,
    Unsupported,
    WhatIf,
)
from app.agents.mock_parser import parse_message
from app.agents.plan_draft import QUESTIONS
from app.agents.plan_model import ModelPlanForm
from app.agents.plan_rules import extract_rules
from app.agents.providers import RULES, TEMPLATE, Parsed, ReadPlan, Worded
from app.schemas.scenarios import OverridesIn

log = logging.getLogger(__name__)


class ModelRequest(BaseModel):
    """The form the model fills in. Changes come first and the kind last: the model writes
    JSON top to bottom, so it has read the numbers before choosing the kind."""

    invest_change_eur: float | None = Field(
        None, description="Invest this much MORE (positive) or LESS (negative) per month."
    )
    invest_new_eur: float | None = Field(
        None, description="Invest exactly this amount per month from now on (0 = stop)."
    )
    pay_change_eur: float | None = Field(
        None, description="Take-home pay per month goes up (positive) or down (negative) by this."
    )
    pay_new_eur: float | None = Field(None, description="New take-home pay per month.")
    spending_change_eur: float | None = Field(
        None, description="Spend this much MORE (positive) or LESS (negative) per month."
    )
    spending_new_eur: float | None = Field(None, description="New monthly spending.")
    return_percent: float | None = Field(
        None, description="Yearly investment return in percent: 3 means 3%."
    )
    salary_growth_percent: float | None = Field(
        None, description="Yearly salary growth in percent."
    )
    spending_growth_percent: float | None = Field(
        None, description="Yearly growth of spending in percent."
    )
    market_change_next_year_percent: float | None = Field(
        None,
        description="Investments fall (negative) or rise (positive) by this percent in the "
        "next year only: -30 for a 30% crash.",
    )
    sure_percent: float | None = Field(
        None,
        description="For needed_per_month only: how sure, in percent of simulated futures "
        "(90 for '90% sure').",
    )
    assumptions: Literal["conservative", "base", "optimistic"] | None = Field(
        None, description="Only if the user names a case: pessimistic = conservative."
    )
    kind: Literal[
        "what_if",
        "on_track",
        "goal_date",
        "needed_per_month",
        "compare",
        "likelihood",
        "assumptions",
        "advice",
        "other",
    ]


SYSTEM = """You convert one message about a personal savings plan into JSON. Never answer it.

kind:
- what_if: the user imagines a change (invest/earn/spend more or less, a different return).
- on_track: asks how the plan is doing overall.
- goal_date: asks WHEN the goal is reached.
- needed_per_month: asks how much per month is NEEDED to reach the goal on time.
- compare: asks to compare scenarios or options.
- likelihood: asks how likely or how sure it is to reach the goal (chances, probability).
- assumptions: asks which assumptions or rates are used.
- advice: asks what to buy, choose or do (e.g. "should I...", "which fund").
- other: anything else.

Copy amounts exactly from the message. "less" or "cut" makes a change negative.
Percentages go in the *_percent fields as written (3% -> 3). A one-off fall or crash of
the market or investments goes in market_change_next_year_percent, negative (falls 30% -> -30).
Leave everything else null."""

EXAMPLES: list[tuple[str, dict]] = [
    ("What if I invest €200 more per month?", {"invest_change_eur": 200, "kind": "what_if"}),
    ("what if I spent 150 less each month", {"spending_change_eur": -150, "kind": "what_if"}),
    ("What if returns are only 3%?", {"return_percent": 3, "kind": "what_if"}),
    ("What if I earn 3000 a month?", {"pay_new_eur": 3000, "kind": "what_if"}),
    ("Am I on track in the pessimistic case?", {"assumptions": "conservative", "kind": "on_track"}),
    ("When will I have enough?", {"kind": "goal_date"}),
    ("How much should I save monthly to get there in time?", {"kind": "needed_per_month"}),
    ("What are my chances of getting there?", {"kind": "likelihood"}),
    (
        "What if the stock market drops 25% next year?",
        {"market_change_next_year_percent": -25, "kind": "what_if"},
    ),
    ("Should I buy an ETF?", {"kind": "advice"}),
]

_KINDS = {
    "on_track": RunProjection,
    "goal_date": GoalDate,
    "needed_per_month": RequiredContribution,
    "compare": CompareScenarios,
    "likelihood": Likelihood,
    "assumptions": ExplainAssumptions,
}
_MONEY = {
    "invest_change_eur": "monthly_investment_contribution_delta",
    "invest_new_eur": "monthly_investment_contribution",
    "pay_change_eur": "monthly_net_income_delta",
    "pay_new_eur": "monthly_net_income",
    "spending_change_eur": "monthly_expenses_delta",
    "spending_new_eur": "monthly_expenses",
}
_RATES = {
    "return_percent": "annual_return",
    "salary_growth_percent": "annual_salary_growth",
    "spending_growth_percent": "annual_expense_growth",
    "market_change_next_year_percent": "first_year_return",
}

EXPLAIN_SYSTEM = (
    "You rewrite facts about a savings projection as a short, friendly reply (2 to 4 "
    "sentences) to the user's question.\n"
    "Rules: use only these facts; copy every amount, date and duration exactly as written; "
    "add no other numbers; never say what the user should do and never recommend anything; "
    "do not add a disclaimer."
)

SUMMARY_SYSTEM = (
    "You rewrite facts about a person's savings projection as a short summary in plain "
    "language (3 or 4 sentences), speaking to that person.\n"
    "Rules: use only these facts; copy every amount, date, percentage, duration and share "
    "(such as '9 of 10') exactly as written; add no other numbers; never say what the person "
    "should do and never recommend anything; do not add a disclaimer."
)

_ADVICE_WORDS = re.compile(
    r"\b(should|recommend\w*|advis\w*|suggest\w*|guarantee\w*|keep up)\b", re.I
)
_MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
# The figures the templates write: amounts, dates, percentages, durations, points and the
# number of simulated futures.
_FIGURE = re.compile(
    rf"[−+]?€\d{{1,3}}(?:,\d{{3}})*|\d{{1,2}} {_MONTH} \d{{4}}|{_MONTH} \d{{4}}"
    r"|\d+(?:\.\d+)?%|\d+ years?(?: \d+ months?)?|\d+ months?|±?\d+ points?"
    r"|\d{1,3}(?:,\d{3})* simulated futures|\d+ (?:in|of) \d+"
)
_WORD_DURATION = re.compile(
    r"\b(a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|a few|several)"
    r" (months?|years?)\b",
    re.I,
)
# Numbers in words can't be checked against the facts ("fewer than one out of every thousand"
# where the facts said "fewer than 1%"), so a text that uses them is not shown.
_NUMBER_WORDS = re.compile(
    r"\b(two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|fifty"
    r"|hundred|thousand|million|half|quarter|dozen)\b",
    re.I,
)


_SET_WORDS = {
    "conservative": r"\b(conservative|pessimistic|cautious|worst)\b",
    "optimistic": r"\b(optimistic|best case|hopeful)\b",
    "base": r"\bbase\b",
}


def _rules_unsure(intent: Intent) -> bool:
    return isinstance(intent, NeedsClarification) or (
        isinstance(intent, Unsupported) and intent.reason == "not_understood"
    )


class UntrustedOutput(ValueError):
    """The model's output failed a check; the deterministic path is used instead."""


class OllamaProvider:
    def __init__(
        self, model: str, base_url: str, timeout: float = 60, rewrite_replies: bool = False
    ):
        """`rewrite_replies`: let the model reword the templated replies (strictly checked).
        Off by default: with phi3, rewording introduced errors that checks can't catch,
        such as merging two scenarios into one sentence."""
        self.name = model
        self.rewrite_replies = rewrite_replies
        # reasoning=False: models that "think" first (qwen3) answer directly; it is ignored by
        # models that don't. Thinking would only add time to a fill-in-the-form task.
        common = {
            "model": model,
            "base_url": base_url,
            "temperature": 0,
            "keep_alive": "30m",
            "reasoning": False,
        }
        self._parser = ChatOllama(
            **common, format=ModelRequest.model_json_schema(), client_kwargs={"timeout": timeout}
        )
        self._writer = ChatOllama(**common, num_predict=200, client_kwargs={"timeout": timeout})
        self._plan_reader = ChatOllama(
            **common, format=ModelPlanForm.model_json_schema(), client_kwargs={"timeout": timeout}
        )

    # ---- parsing ---------------------------------------------------------------------------

    def parse(self, message: str, previous: Intent | None) -> Parsed:
        """Rules first; the model only for messages the rules can't place.

        Measured on the labelled set (`python -m app.agents.evaluate --model phi3`), a small
        model's plausible-but-wrong answers (a raise read as extra investment, "invest 600"
        read as "600 more") pass the number checks, so letting it override the rules made
        results worse. It helps with phrasings the rules don't know.
        """
        by_rules = parse_message(message, previous)
        if not _rules_unsure(by_rules):
            return Parsed(by_rules, RULES)
        try:
            by_model = to_intent(self._ask_model(message, previous), message)
            if isinstance(by_model, Unsupported) and isinstance(by_rules, NeedsClarification):
                return Parsed(by_rules, RULES)  # a clarifying question beats a refusal
            return Parsed(by_model, self.name)
        except Exception as exc:  # model down, timeout, invalid JSON or failed checks
            log.info("model parse rejected (%s); using rules", exc)
            return Parsed(by_rules, RULES)

    def _ask_model(self, message: str, previous: Intent | None) -> ModelRequest:
        messages: list[tuple[str, str]] = [("system", SYSTEM)]
        for example, answer in EXAMPLES:
            messages += [("human", example), ("ai", json.dumps(answer))]
        if previous is not None:
            messages.append(
                (
                    "system",
                    f"The previous message was understood as: {describe(previous)}. "
                    "If this message only changes an amount or the assumptions, keep the rest.",
                )
            )
        messages.append(("human", message))
        reply = self._parser.invoke(messages)
        try:
            return ModelRequest.model_validate_json(reply.content)
        except ValidationError as exc:
            raise UntrustedOutput(f"invalid JSON: {exc.error_count()} errors") from exc

    # ---- explaining ------------------------------------------------------------------------

    def explain(self, facts: Facts) -> Worded:
        if not self.rewrite_replies or isinstance(facts.intent, ExplainAssumptions):
            return Worded(template_reply(facts), TEMPLATE)
        body = template_body(facts)
        try:
            text = self._writer.invoke(
                [
                    ("system", EXPLAIN_SYSTEM),
                    ("human", f"Question: {facts.question}\n\nFacts:\n{body}"),
                ]
            ).content.strip()
            check_explanation(text, body)
            return Worded(f"{text}\n\n{footer(facts)}", self.name)
        except Exception as exc:
            log.info("model explanation rejected (%s); using template", exc)
            return Worded(template_reply(facts), TEMPLATE)

    # ---- reading a plan description ------------------------------------------------------

    def read_plan(self, message: str, asked: str | None) -> ReadPlan:
        """Rules first; the model only when the rules left a number unexplained or
        understood nothing, and only for the fields the rules left empty."""
        by_rules = extract_rules(message, asked)
        if not plan_model.rules_missed_something(message, by_rules):
            return ReadPlan(by_rules, RULES)
        try:
            by_model = plan_model.to_extraction(self._read_plan_with_model(message, asked), message)
        except Exception as exc:  # model down, timeout or invalid JSON
            log.info("model plan reading failed (%s); using rules", exc)
            return ReadPlan(by_rules, RULES)
        merged = plan_model.merge(by_rules, by_model)
        return ReadPlan(merged, self.name if merged != by_rules else RULES)

    def _read_plan_with_model(self, message: str, asked: str | None) -> ModelPlanForm:
        messages: list[tuple[str, str]] = [("system", plan_model.SYSTEM)]
        for example, answer in plan_model.EXAMPLES:
            messages += [("human", example), ("ai", json.dumps(answer))]
        if asked in QUESTIONS:
            messages.append(("system", f"The question the person is answering: {QUESTIONS[asked]}"))
        messages.append(("human", message))
        reply = self._plan_reader.invoke(messages)
        return ModelPlanForm.model_validate_json(reply.content)

    # ---- page summaries -------------------------------------------------------------------

    def summarise(self, facts: list[str]) -> Worded:
        """The facts reworded by the model, if rewording is on and the text passes the
        checks; otherwise the facts as they are. Off by default: measured with qwen2.5:3b
        (`python -m app.agents.evaluate_summaries`), 6 of 8 texts failed the checks and both
        that passed still misstated a fact (docs/PHASE3_DESIGN.md, 3.3)."""
        if not self.rewrite_replies:
            return Worded(" ".join(facts), TEMPLATE)
        source = "\n".join(facts)
        try:
            text = self._writer.invoke(
                [("system", SUMMARY_SYSTEM), ("human", f"Facts:\n{source}")]
            ).content.strip()
            check_explanation(text, source)
            return Worded(text, self.name)
        except Exception as exc:
            log.info("model summary rejected (%s); using the facts", exc)
            return Worded(" ".join(facts), TEMPLATE)

    def warm_up(self) -> None:
        """Load the model into memory now (the first load can take a minute or more), so a
        user's first question doesn't wait for it. Failures are fine: the chat falls back."""
        try:
            self._parser.invoke([("human", "Am I on track?")])
        except Exception as exc:
            log.info("model warm-up failed (%s); the chat will use rules until it answers", exc)

    def is_available(self) -> bool:
        """True when Ollama answers and has the model (checked by /health)."""
        try:
            import httpx

            tags = httpx.get(f"{self._parser.base_url}/api/tags", timeout=2).json()
            return any(m["name"].split(":")[0] == self.name.split(":")[0] for m in tags["models"])
        except Exception:
            return False


def to_intent(request: ModelRequest, message: str) -> Intent:
    """Turn the model's form into an intent, checking every number against the message."""
    written = numbers_in(message)
    overrides: dict[str, float] = {}
    for field, target in _MONEY.items():
        value = getattr(request, field)
        if value is None:
            continue
        stopping = value == 0 and re.search(r"\b(stop|no longer|nothing)\b", message, re.I)
        if as_number(value) not in written and not stopping:
            raise UntrustedOutput(f"{field}={value} is not in the message")
        overrides[target] = value
    for field, target in _RATES.items():
        value = getattr(request, field)
        if value is None:
            continue
        if as_number(value) not in written:
            raise UntrustedOutput(f"{field}={value} is not in the message")
        overrides[target] = round(value / 100, 6)

    if request.assumptions and not re.search(_SET_WORDS[request.assumptions], message, re.I):
        raise UntrustedOutput(f"assumption set {request.assumptions!r} is not named in the message")

    if request.kind in ("advice", "other"):
        reason = "advice" if request.kind == "advice" else "out_of_scope"
        return Unsupported(reason=reason)
    if request.kind == "likelihood":
        changes = OverridesIn(**overrides) if overrides else None
        return Likelihood(overrides=changes, assumption_set=request.assumptions)
    if overrides:  # a change was described, whatever kind the model picked
        return WhatIf(overrides=OverridesIn(**overrides), assumption_set=request.assumptions)
    if request.kind == "what_if":
        raise UntrustedOutput("what_if without any change")
    if request.kind == "needed_per_month" and request.sure_percent is not None:
        if as_number(request.sure_percent) not in written or not 0 < request.sure_percent < 100:
            raise UntrustedOutput(f"sure_percent={request.sure_percent} is not a usable share")
        return RequiredContribution(
            share=round(request.sure_percent / 100, 4), assumption_set=request.assumptions
        )
    return _KINDS[request.kind](assumption_set=request.assumptions)


def check_explanation(text: str, facts: str) -> None:
    """Reject a reworded reply unless every figure is copied from the facts as a whole
    phrase ("1 Jul 2031", "€2,098", "11 months"). Checking digits alone isn't enough: phi3
    wrote "January 1, 2032" (digits that exist elsewhere in the facts, a date that
    doesn't) and "a month before" (no digits at all; the facts said 11 months)."""
    if not text:
        raise UntrustedOutput("empty reply")
    if not only_known_numbers(text, facts):
        extra = sorted(str(n) for n in numbers_in(text) - numbers_in(facts))
        raise UntrustedOutput(f"numbers not in the facts: {extra}")
    remaining = text
    for phrase in sorted(set(_FIGURE.findall(facts)), key=len, reverse=True):
        remaining = remaining.replace(phrase, " ")
    if leftover := re.findall(r"\S*\d\S*", remaining):
        raise UntrustedOutput(f"figures not copied as written: {leftover}")
    # "€826 a month" is an amount per month, not a duration: only the rest is checked.
    without_rates = re.sub(
        r"€[\d,]+ (?:a|per|each|every) (?:month|year)\b"
        r"(?!\s+(?:early|earlier|late|later|before|after|sooner|ahead))",
        " ",
        text,
    )
    if _WORD_DURATION.search(without_rates):
        raise UntrustedOutput("a duration in words instead of the facts' figure")
    if _NUMBER_WORDS.search(text):
        raise UntrustedOutput("a number in words, which can't be checked against the facts")
    if _ADVICE_WORDS.search(text):
        raise UntrustedOutput("reads like advice")


def describe(intent: Intent) -> str:
    return json.dumps(intent.model_dump(mode="json", exclude_none=True))
