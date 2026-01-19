from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from importlib import resources

from jsonschema import validate as js_validate, ValidationError

from .verifier import ActionProposal
from .evidence import EvidenceSystem, apply_verified_ids_to_provenance
from .config import load_policy, dump_policy


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
    proposal = load_json(proposal_path)
    schema = load_packaged_schema()

    try:
        js_validate(instance=proposal, schema=schema)
        print("✅ Schema valid")
        return 0
    except ValidationError as e:
        print("❌ Schema invalid")
        print(str(e))
        return 2


def cmd_evidence_verify(proposal_path: Path) -> int:
    # Always validate schema first (consistent UX)
    code = cmd_schema(proposal_path)
    if code != 0:
        return code

    proposal = load_json(proposal_path)

    es = EvidenceSystem()
    report = es.verify_all(proposal, base_dir=proposal_path.parent)

    if not report.results:
        print("❌ Evidence verification failed")
        print("No evidence entries found in proposal (expected 'evidence': [...]).")
        return 4

    for r in report.results:
        if r.ok:
            print(f"✅ Evidence {r.id}: {r.message}")
        else:
            print(f"❌ Evidence {r.id}: {r.message}")

    if report.ok:
        print("✅ Evidence verification passed")
        return 0

    print("❌ Evidence verification failed")
    return 4


def cmd_verify(proposal_path: Path, *, verify_evidence: bool = False) -> int:
    code = cmd_schema(proposal_path)
    if code != 0:
        return code

    proposal = load_json(proposal_path)

    # Optional evidence verification (v0.3)
    if verify_evidence:
        es = EvidenceSystem()
        report = es.verify_all(proposal, base_dir=proposal_path.parent)

        if not report.results:
            print("❌ Evidence verification failed")
            print("No evidence entries found in proposal (expected 'evidence': [...]).")
            return 4

        if not report.ok:
            print("❌ Evidence verification failed")
            for r in report.results:
                if not r.ok:
                    print(f"- {r.id}: {r.message}")
            return 4

        # Upgrade provenance trust based on verified evidence IDs
        proposal = apply_verified_ids_to_provenance(proposal, report.verified_ids)

    try:
        ActionProposal(**proposal)
        print("✅ Verifier passed")
        return 0
    except Exception as e:
        print("❌ Verifier failed")
        print(str(e))
        return 3


def _find_policy_source(repo_root: Path) -> str:
    """
    Best-effort: explain where policy came from.
    This mirrors load_policy() priority:
      explicit_path (not used by CLI)
      PIC_POLICY_PATH env var
      repo_root/pic_policy.json or repo_root/pic_policy.local.json
      default policy
    """
    env_path = os.getenv("PIC_POLICY_PATH")
    if env_path:
        return f"PIC_POLICY_PATH={env_path}"

    for name in ("pic_policy.json", "pic_policy.local.json"):
        candidate = repo_root / name
        if candidate.exists():
            return str(candidate)

    return "default (no policy file found)"


def cmd_policy(*, repo_root: Path, write_example: bool = False) -> int:
    """
    Show the effective policy (and where it was loaded from).
    """
    if write_example:
        example = {
            "impact_by_tool": {
                "payments_send": "money",
                "customer_export": "privacy",
                "aws_batch_run": "compute",
            },
            "require_pic_for_impacts": ["money", "privacy", "irreversible"],
            "require_evidence_for_impacts": ["money", "privacy", "irreversible"],
        }
        print(json.dumps(example, indent=2, ensure_ascii=False))
        return 0

    policy = load_policy(repo_root=repo_root)
    source = _find_policy_source(repo_root)

    print("✅ Policy loaded")
    print(f"Source: {source}")
    print(json.dumps(dump_policy(policy), indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pic-cli", description="PIC Standard CLI utilities")
    sub = p.add_subparsers(dest="command", required=True)

    s1 = sub.add_parser("schema", help="Validate proposal against JSON Schema")
    s1.add_argument("proposal", type=Path)

    s2 = sub.add_parser("verify", help="Validate proposal against schema + verifier")
    s2.add_argument("proposal", type=Path)
    s2.add_argument(
        "--verify-evidence",
        action="store_true",
        help="Verify evidence (v0.3: sha256) and upgrade provenance to TRUSTED based on verified IDs before running verifier.",
    )

    s3 = sub.add_parser("evidence-verify", help="Verify evidence only (v0.3: sha256)")
    s3.add_argument("proposal", type=Path)

    s4 = sub.add_parser("policy", help="Show the effective policy loaded from pic_policy.json / PIC_POLICY_PATH")
    s4.add_argument(
        "--repo-root",
        type=Path,
        default=Path(".").resolve(),
        help="Repo root to search for pic_policy.json (default: current working directory).",
    )
    s4.add_argument(
        "--write-example",
        action="store_true",
        help="Print an example policy JSON you can save as pic_policy.json.",
    )

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "schema":
        return cmd_schema(args.proposal)
    if args.command == "evidence-verify":
        return cmd_evidence_verify(args.proposal)
    if args.command == "verify":
        return cmd_verify(args.proposal, verify_evidence=getattr(args, "verify_evidence", False))
    if args.command == "policy":
        return cmd_policy(repo_root=getattr(args, "repo_root"), write_example=getattr(args, "write_example", False))

    raise SystemExit("Unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
