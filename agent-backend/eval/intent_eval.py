"""Measure how well the chat intent classifier separates general from personalised.

Adding the my_documents / my_courses intents made classification harder: several
personalised questions differ from their general twin by little more than the word
"I". This scores that distinction so the decision to wire the remaining agents in
rests on a measured error rate rather than on a guess.

Needs an LLM key (common.config). Without one it exits with a clear message rather
than reporting a misleading zero.

Usage:
    python -m eval.intent_eval
    python -m eval.intent_eval --repeat 3     # classification is not deterministic
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from common import config

_CASES = Path(__file__).resolve().parent / "cases" / "chat_intents.json"

# Which intents belong to which side of the split we care about.
_PERSONALISED = {"my_documents", "my_courses"}


def load_cases() -> list[dict]:
    return json.loads(_CASES.read_text(encoding="utf-8"))["cases"]


def classify(message: str) -> str:
    """One classification via the real graph node."""
    from langchain_core.messages import HumanMessage

    from app.agents.supervisor import classify_intent_node

    state = {"messages": [HumanMessage(content=message)], "user_stage": "applicant"}
    return classify_intent_node(state)["intent"]


def _side(intent: str) -> str:
    return "personalised" if intent in _PERSONALISED else "general"


def run(repeat: int) -> int:
    if not config.get_api_key():
        print("No LLM key configured — intent classification cannot be measured.")
        print("Set DEEPSEEK_API_KEY / NVIDIA_API_KEY, or configure it on the settings page.")
        return 2

    cases = load_cases()
    wrong: list[tuple[dict, str]] = []
    confusion: Counter[tuple[str, str]] = Counter()
    correct = total = 0
    # A general question misrouted into a personalised branch is the costly error:
    # the user gets asked for profile data instead of the answer they wanted.
    leaked = 0

    for case in cases:
        for _ in range(repeat):
            got = classify(case["message"])
            total += 1
            if got == case["expected"]:
                correct += 1
            else:
                wrong.append((case, got))
                confusion[(case["expected"], got)] += 1
                if _side(case["expected"]) == "general" and _side(got) == "personalised":
                    leaked += 1

    print(f"\naccuracy: {correct}/{total} = {correct / total:.0%}   (repeat={repeat})")
    print(f"general questions pulled into a personalised branch: {leaked}")
    print("  ^ the expensive error: the user is asked for profile data instead of answered")

    if wrong:
        print(f"\n--- misclassified ({len(wrong)}) ---")
        for case, got in wrong:
            print(f"  [{case['id']}] expected {case['expected']}, got {got}")
            print(f"      {case['message']}")
            print(f"      why hard: {case['why']}")

    if confusion:
        print("\n--- confusion pairs ---")
        for (want, got), n in confusion.most_common():
            print(f"  {want:14} -> {got:14} x{n}")

    return 0 if not wrong else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=1,
                        help="classify each case N times; the classifier is not deterministic")
    return run(parser.parse_args().repeat)


if __name__ == "__main__":
    raise SystemExit(main())
