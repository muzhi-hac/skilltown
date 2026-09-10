from pathlib import Path

import yaml

from server.main import create_app


HTTP_METHODS = {"get", "post", "delete", "put", "patch"}


def operations(spec: dict) -> dict[tuple[str, str], str]:
    return {
        (path, method): operation["operationId"]
        for path, path_item in spec["paths"].items()
        for method, operation in path_item.items()
        if method in HTTP_METHODS
    }


def test_implemented_operations_match_committed_contract(tmp_path):
    committed = yaml.safe_load(Path("docs/openapi.yaml").read_text(encoding="utf-8"))
    generated = create_app(tmp_path / "contract.sqlite3").openapi()
    assert operations(generated) == operations(committed)
