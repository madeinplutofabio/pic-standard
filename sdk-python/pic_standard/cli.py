from __future__ import annotations

import argparse
import json
from pathlib import Path
from importlib import resources

from jsonschema import validate as js_validate, ValidationError
from .verifier import ActionProposal


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"File not found: {path}")
    except json.JSONDecodeError as e:
        raise SystemExit(f"Invalid JSON in {path}: {e}")


def load_packaged_schema() -> dict:
    schema_text = (
        resources.files("pic_standard")
        .joinpath("schemas/proposal_schema.json")
        .read_text(encoding="utf-8")
    )
    return json.loads(schema_text)


def cmd_schema(proposal_path: Path) -> int:
    schema = load_packaged_schema()
    proposal = load_json(proposal_path)

    try:
        js_validate(instance=proposal, schema=schema)
        print("✅ Schema valid")
        return 0
    except ValidationError as e:
        print("❌ Schema invalid")
        print(str(e))
        return 2


def cmd_verify(proposal_path: Path) -> int:
    code = cmd_schema(proposal_path)
    if code != 0:
        return code

    proposal = load_json(proposal_path)
    try:
        ActionProposal(**proposal)
        print("✅ Verifier passed")
        return 0
    except Exception as e:
        print("❌ Verifier failed")
        print(str(e))
        return 3


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pic-cli", description="PIC Standard CLI utilities")
    sub = p.add_subparsers(dest="command", required=True)

    s1 = sub.add_parser("schema", help="Validate proposal against JSON Schema")
    s1.add_argument("proposal", type=Path)

    s2 = sub.add_parser("verify", help="Validate proposal against schema + verifier")
    s2.add_argument("proposal", type=Path)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "schema":
        return cmd_schema(args.proposal)
    if args.command == "verify":
        return cmd_verify(args.proposal)

    raise SystemExit("Unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
