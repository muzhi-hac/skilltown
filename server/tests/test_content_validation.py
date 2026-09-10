from copy import deepcopy

import pytest

from server.core.content_validation import validate_content
from server.core.scenario_engine import ScenarioEngine


def test_production_content_validates():
    validate_content(ScenarioEngine().content)


def test_duplicate_or_unresolved_knowledge_is_rejected():
    content = deepcopy(ScenarioEngine().content)
    node = content["scenarios"]["dinner-invitation"]["nodes"]["alex_public_gift"]
    node["knowledge"].append("ANNEX-1.1")
    with pytest.raises(ValueError, match="knowledge must be non-empty and unique"):
        validate_content(content)
