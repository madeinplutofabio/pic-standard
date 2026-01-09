import json
from pathlib import Path
from jsonschema import validate

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "proposal_schema.json").read_text(encoding="utf-8"))

def test_all_examples_validate_against_schema():
    examples_dir = ROOT / "examples"
    example_files = sorted(examples_dir.glob("*.json"))
    assert example_files, "No example JSON files found in examples/"

    for path in example_files:
        data = json.loads(path.read_text(encoding="utf-8"))
        validate(instance=data, schema=SCHEMA)
