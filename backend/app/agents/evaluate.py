"""Score intent parsers on the labelled set (`app/agents/eval_set.py`).

    python -m app.agents.evaluate              # rules only (no model needed)
    python -m app.agents.evaluate --model phi3 # also the model alone, and model + fallback

"Model alone" counts a rejected answer (failed number check, invalid JSON) as wrong;
"rules, then model" is what the app does: the model is asked only when the rules can't
place a message, and a rejected answer leaves the rules' result.
"""

import argparse
import statistics
import sys
import time
from collections.abc import Callable

from app.agents.eval_set import CASES, matches
from app.agents.intents import Intent
from app.agents.mock_parser import parse_message
from app.config import get_settings

Parser = Callable[[str, Intent | None], Intent | None]


def run(name: str, parse: Parser) -> tuple[int, list[float], list[str]]:
    correct, seconds, misses = 0, [], []
    for case in CASES:
        previous = parse(case.previous, None) if case.previous else None
        start = time.perf_counter()
        intent = parse(case.message, previous)
        seconds.append(time.perf_counter() - start)
        got = intent.model_dump(mode="json") if intent else {"kind": "(rejected)"}
        if matches(got, case.expected):
            correct += 1
        else:
            shown = {k: v for k, v in got.items() if v is not None}
            if "overrides" in shown:
                shown["overrides"] = {k: v for k, v in shown["overrides"].items() if v is not None}
            misses.append(
                f"  {case.message!r}\n      expected {case.expected}\n      got      {shown}"
            )
    print(
        f"\n{name}: {correct}/{len(CASES)} correct ({correct / len(CASES):.0%}), "
        f"median {statistics.median(seconds):.2f}s per message"
    )
    return correct, seconds, misses


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--model", help="an Ollama model to evaluate, e.g. phi3")
    parser.add_argument("--show-misses", action="store_true")
    args = parser.parse_args(argv)

    results = [("rules only", run("rules only", parse_message))]
    if args.model:
        from app.agents.ollama import OllamaProvider, UntrustedOutput, to_intent

        provider = OllamaProvider(args.model, get_settings().ollama_base_url)
        print(f"Warming up {args.model}…", end=" ", flush=True)
        provider.parse("hello", None)
        print("ready.")

        def model_only(message: str, previous: Intent | None) -> Intent | None:
            try:
                return to_intent(provider._ask_model(message, previous), message)
            except (UntrustedOutput, Exception):
                return None

        results.append((f"{args.model} alone", run(f"{args.model} alone", model_only)))
        results.append(
            (
                f"rules, then {args.model}",
                run(f"rules, then {args.model}", lambda m, p: provider.parse(m, p).intent),
            )
        )

    if args.show_misses:
        for name, (_, _, misses) in results:
            print(f"\nMisses, {name}:")
            print("\n".join(misses) or "  none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
