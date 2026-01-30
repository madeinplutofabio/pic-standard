from __future__ import annotations

import json
from pathlib import Path
from importlib import resources

from jsonschema import validate as js_validate

ROOT = Path(__file__).resolve().parents[1]


def _load_packaged_schema() -> dict:
    schema_text = (
        resources.files("pic_standard")
        .joinpath("schemas/proposal_schema.json")
        .read_text(encoding="utf-8")
    )
    return json.loads(schema_text)


def _looks_like_pic_proposal(obj: object) -> bool:
    if not isinstance(obj, dict):
        return False
    # PIC proposals always have protocol = "PIC/1.0"
    return obj.get("protocol") == "PIC/1.0"


def test_examples_validate_against_schema():
    schema = _load_packaged_schema()

    examples_dir = ROOT / "examples"
    assert examples_dir.exists(), f"Missing examples dir: {examples_dir}"

    validated = 0

    # Only top-level examples (NOT failing/).
    for p in sorted(examples_dir.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))

        # Skip non-proposal JSON files (e.g. pic_keys.json, policy JSON, etc.)
        if not _looks_like_pic_proposal(data):
            continue

        js_validate(instance=data, schema=schema)
        validated += 1

    # Safety check: make sure we actually validated something
    assert validated > 0, "No PIC proposal JSON files found in examples/ to validate."
