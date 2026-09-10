"""Run one explicitly requested paid model evaluation against a grounded node.

The script reads configured credentials but never writes them. It sends the same
immutable EvaluationContext used by the API, then prints the verified result.

    set -a; . <your env file>; set +a
    .venv/bin/python tools/check_model.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.core.grounding import build_context  # noqa: E402
from server.core.model_evaluator import ClaudeTextEvaluator  # noqa: E402
from server.core.scenario_engine import ScenarioEngine  # noqa: E402


def main() -> int:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN", "").strip()
    if not api_key and not auth_token:
        print("No model credential is set; probe not run.")
        return 2

    engine = ScenarioEngine()
    scenario = engine.get_scenario("dinner-invitation")
    node = scenario["nodes"]["alex_public_gift"]
    context = build_context("dinner-invitation", scenario["version"], "alex_public_gift", node)
    answer = next(item.text for item in context.reference_answers if item.outcome == "pass")
    evaluator = ClaudeTextEvaluator(
        api_key=api_key or None,
        auth_token=auth_token or None,
        base_url=os.getenv("ANTHROPIC_BASE_URL", "").strip() or None,
        model=os.getenv("SKILLTOWN_MODEL", "claude-opus-5").strip() or "claude-opus-5",
        user_agent=os.getenv("SKILLTOWN_MODEL_USER_AGENT", "").strip() or None,
    )
    result = evaluator.evaluate(node["text_rule"], answer, context=context)
    print(f"mode={result.mode}")
    print(f"assessed={result.assessed}")
    print(f"outcome={result.outcome}")
    print(f"cited_ids={result.policy_clause_ids}")
    print(f"feedback={result.feedback}")
    return 0 if result.mode == "ai" and result.assessed else 1


if __name__ == "__main__":
    raise SystemExit(main())
