#!/usr/bin/env python3
"""PIC CLI

Minimal command-line utility for:
1) Validating a proposal against the JSON Schema
2) Validating a proposal against the reference verifier rules

Usage examples:

  # Schema validation only
  python sdk-python/pic_cli.py schema examples/financial_irreversible.json

  # Full verification (schema + verifier)
  python sdk-python/pic_cli.py verify examples/financial_irreversible.json

  # Specify explicit schema path
  python sdk-python/pic_cli.py verify examples/financial_irreversible.json --schema schemas/proposal_schema.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import validate as js_validate, ValidationError
from pic_verifier import ActionProposal  # reference verifier


DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "proposal_schema.json"


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"File not found: {path}")
    except json.JSONDecodeError as e:
        raise SystemExit(f"Invalid JSON in {path}: {e}")


def cmd_schema(proposal_path: Path, schema_path: Path) -> int:
    schema = load_json(schema_path)
    proposal = load_json(proposal_path)

    try:
        js_validate(instance=proposal, schema=schema)
        print("✅ Schema valid")
        return 0
    except ValidationError as e:
        print("❌ Schema invalid")
        print(str(e))
        return 2


def cmd_verify(proposal_path: Path, schema_path: Path) -> int:
    # 1) Schema validation
    code = cmd_schema(proposal_path, schema_path)
    if code != 0:
        return code

    # 2) Verifier validation (pydantic model + rules)
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
    p.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_SCHEMA_PATH,
        help=f"Path to proposal JSON Schema (default: {DEFAULT_SCHEMA_PATH})",
    )
    sub = p.add_subparsers(dest="command", required=True)

    s1 = sub.add_parser("schema", help="Validate proposal against JSON Schema")
    s1.add_argument("proposal", type=Path, help="Path to proposal JSON")

    s2 = sub.add_parser("verify", help="Validate proposal against schema + reference verifier")
    s2.add_argument("proposal", type=Path, help="Path to proposal JSON")

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    schema_path: Path = args.schema
    proposal_path: Path = args.proposal

    if args.command == "schema":
        return cmd_schema(proposal_path, schema_path)
    if args.command == "verify":
        return cmd_verify(proposal_path, schema_path)

    raise SystemExit("Unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
