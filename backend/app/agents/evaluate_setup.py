"""Score "describe your plan" readers on the labelled set (`app/agents/setup_eval_set.py`).

    python -m app.agents.evaluate_setup                    # rules only (no model needed)
    python -m app.agents.evaluate_setup --model qwen2.5:3b # also the model alone, and
                                                           # rules then model (what the app does)

Each description goes through the same path as the app (extraction -> draft), and the draft
is scored field by field: correct, missing, or wrong (an invented or misread value). Wrong is
the costly kind: a missing value gets a question, a wrong one may go unnoticed.
"""

import argparse
import sys
import time
from collections.abc import Callable
from datetime import date

from app.agents.plan_draft import Extraction, apply_extraction, start
from app.agents.plan_rules import extract_rules
from app.agents.setup_eval_set import CASES, score
from app.config import get_settings

TODAY = date(2026, 10, 15)

Reader = Callable[[str], Extraction | None]


def run(name: str, read: Reader) -> list[str]:
    correct = missing = wrong = perfect = 0
    seconds, misses = [], []
    for case in CASES:
        began = time.perf_counter()
        found = read(case.message)
        seconds.append(time.perf_counter() - began)
        draft = apply_extraction(start().draft, found or Extraction(), TODAY).draft
        c, m, w, details = score(draft.model_dump(mode="json"), case.expected)
        correct, missing, wrong = correct + c, missing + m, wrong + w
        perfect += not (m or w)
        if details:
            misses.append(f"  {case.message!r}\n      " + "\n      ".join(details))
    expected = sum(len(c.expected) for c in CASES)
    seconds.sort()
    print(
        f"\n{name}: {correct}/{expected} fields correct ({correct / expected:.0%}), "
        f"{missing} missing, {wrong} wrong; {perfect}/{len(CASES)} descriptions fully right; "
        f"median {seconds[len(seconds) // 2]:.2f}s"
    )
    return misses


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--model", help="an Ollama model to evaluate, e.g. qwen2.5:3b")
    parser.add_argument("--show-misses", action="store_true")
    args = parser.parse_args(argv)

    results = [("rules only", run("rules only", extract_rules))]
    if args.model:
        from app.agents.ollama import OllamaProvider
        from app.agents.plan_model import to_extraction

        provider = OllamaProvider(args.model, get_settings().ollama_base_url)
        print(f"Warming up {args.model}…", end=" ", flush=True)
        provider.warm_up()
        print("ready.")

        def model_only(message: str) -> Extraction | None:
            try:
                return to_extraction(provider._read_plan_with_model(message, None), message)
            except Exception:
                return None

        results.append((f"{args.model} alone", run(f"{args.model} alone", model_only)))
        both = f"rules, then {args.model}"
        results.append((both, run(both, lambda m: provider.read_plan(m, None).extraction)))

    if args.show_misses:
        for name, misses in results:
            print(f"\nMisses, {name}:")
            print("\n".join(misses) or "  none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
