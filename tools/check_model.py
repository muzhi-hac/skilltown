"""Run one explicitly requested paid model evaluation against a grounded node.

The script reads configured credentials but never writes them. It picks the same
provider the server would, sends the same immutable EvaluationContext the API
uses, and prints the verified result - including the line the character would
have spoken, so a provider that grades well but cannot stay in character is
visible before a demo rather than during one.

    .venv/bin/python tools/check_model.py          # reads .env like the server

"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.core.grounding import PressureState, build_context  # noqa: E402
from server.core.model_evaluator import (  # noqa: E402
    build_evaluator, chosen_provider, default_model_for,
)
from server.core.evaluator import FallbackTextEvaluator  # noqa: E402
from server.main import load_local_env  # noqa: E402
from server.core.scenario_engine import ScenarioEngine  # noqa: E402


def main() -> int:
    load_local_env()
    provider = chosen_provider()
    if provider == "none":
        print("No model credential is set. Paste one into .env:")
        print("  OPENAI_API_KEY=...      (or OPENAI_BASE_URL for a compatible gateway)")
        print("  ANTHROPIC_API_KEY=...   (or ANTHROPIC_AUTH_TOKEN + ANTHROPIC_BASE_URL)")
        return 2

    evaluator = build_evaluator()
    if isinstance(evaluator, FallbackTextEvaluator):
        print(f"Credential found for {provider}, but SKILLTOWN_MODEL_ENABLED is not true.")
        return 2

    engine = ScenarioEngine()
    scenario = engine.get_scenario("dinner-invitation")
    node_id = "alex_public_gift"
    node = scenario["nodes"][node_id]
    context = build_context(
        "dinner-invitation", scenario["version"], node_id, node,
        persona=engine.persona(node["npc_id"]),
        pressure=PressureState(turn=1, max_turns=4, history=(("npc", node["line"]),)),
    )
    # A weak answer, so the character has a reason to push and the verdict has
    # something to catch. One call, one paid request.
    answer = next(item.text for item in context.reference_answers if item.outcome == "miss")

    print(f"provider={provider}")
    print(f"model={default_model_for(provider)}")
    print(f"answer={answer!r}")
    result = evaluator.evaluate(node["text_rule"], answer, context=context)
    print(f"mode={result.mode}")
    print(f"assessed={result.assessed}")
    print(f"outcome={result.outcome}")
    print(f"cited_ids={result.policy_clause_ids}")
    print(f"feedback={result.feedback}")
    print(f"character_line={result.character_line!r}")
    if result.mode != "ai":
        print("\nThe endpoint did not produce a usable verdict; the log line above says why.")
        return 1
    if not result.character_line:
        print("\nGraded, but the spoken line was rejected or empty: the authored ladder")
        print("will be used instead. Usable, just less specific to what the learner wrote.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
