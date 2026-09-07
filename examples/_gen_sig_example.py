from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = REPO_ROOT / "examples"
FAILING = EXAMPLES / "failing"
ARTIFACTS = EXAMPLES / "artifacts"

OK_PATH = EXAMPLES / "financial_sig_ok.json"
BAD_PATH = FAILING / "financial_sig_bad.json"
HASH_OK_PATH = EXAMPLES / "financial_hash_ok.json"
HASH_OK_ARTIFACT = ARTIFACTS / "invoice_123.txt"
KEYS_EXAMPLE_PATH = REPO_ROOT / "pic_keys.example.json"

DEFAULT_EXPIRES_AT = "2027-01-01T00:00:00Z"


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_existing_keyring() -> dict:
    """Load current pic_keys.example.json (rich shape); return empty on absence."""
    if KEYS_EXAMPLE_PATH.exists():
        return json.loads(KEYS_EXAMPLE_PATH.read_text(encoding="utf-8"))
    return {"trusted_keys": {}}


def _set_trusted_key(
    keyring: dict, key_id: str, pub_b64: str, expires_at: str = DEFAULT_EXPIRES_AT
) -> None:
    """Set/update a trusted key in the keyring (rich shape). Preserves other keys."""
    keyring.setdefault("trusted_keys", {})[key_id] = {
        "public_key": pub_b64,
        "expires_at": expires_at,
    }


def _regenerate_sig_examples(keyring: dict) -> list[str]:
    """Regenerate sig_ok / sig_bad demo signatures. Returns list of updated file paths."""
    key_id = "demo_signer_v1"
    priv = ed25519.Ed25519PrivateKey.generate()
    pub_raw = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    payload_ok = "amount=500;currency=USD;invoice=123"
    payload_bad = "amount=600;currency=USD;invoice=123"
    sig_ok = priv.sign(payload_ok.encode("utf-8"))
    # IMPORTANT: reuse the OK signature for the tampered-payload example
    # so it fails deterministically.
    sig_bad = sig_ok

    ok = json.loads(OK_PATH.read_text(encoding="utf-8"))
    ok["evidence"][0]["key_id"] = key_id
    ok["evidence"][0]["signer"] = key_id
    ok["evidence"][0]["payload"] = payload_ok
    ok["evidence"][0]["signature"] = _b64(sig_ok)
    OK_PATH.write_text(json.dumps(ok, indent=4) + "\n", encoding="utf-8")

    bad = json.loads(BAD_PATH.read_text(encoding="utf-8"))
    bad["evidence"][0]["key_id"] = key_id
    bad["evidence"][0]["signer"] = key_id
    bad["evidence"][0]["payload"] = payload_bad
    bad["evidence"][0]["signature"] = _b64(sig_bad)
    BAD_PATH.write_text(json.dumps(bad, indent=4) + "\n", encoding="utf-8")

    _set_trusted_key(keyring, key_id, _b64(pub_raw))
    return [str(OK_PATH.relative_to(REPO_ROOT)), str(BAD_PATH.relative_to(REPO_ROOT))]


def _regenerate_hash_ok_example(keyring: dict) -> list[str]:
    """Regenerate financial_hash_ok.json with hash + signature evidence (v0.8.3+).

    Post-v0.8.3, hash evidence proves content-integrity only; signature evidence
    provides authority for trust upgrade. This function rewrites
    financial_hash_ok.json so it demonstrates both: the hash entry pins the
    current bytes of examples/artifacts/invoice_123.txt, and the sig entry
    proves a trusted signer authorized the payment.
    """
    key_id = "demo_hash_signer_v1"
    priv = ed25519.Ed25519PrivateKey.generate()
    pub_raw = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    payload = f"invoice_123 approved by {key_id} for $500"
    sig = priv.sign(payload.encode("utf-8"))

    hash_ok = json.loads(HASH_OK_PATH.read_text(encoding="utf-8"))
    hash_ok["intent"] = (
        "Send payment for approved invoice (signature-authorized; hash proves content-integrity)"
    )
    hash_ok["claims"] = [
        {
            "text": (
                f"Invoice 123 is approved for $500 (hash-integrity verified, signed by {key_id})"
            ),
            "evidence": ["invoice_123"],
        }
    ]
    # Rewrite evidence: recompute the hash from the current artifact bytes and
    # attach a fresh signature. Idempotent across runs.
    hash_ok["evidence"] = [
        {
            "id": "invoice_123",
            "type": "hash",
            "ref": "file://artifacts/invoice_123.txt",
            "sha256": _sha256_file(HASH_OK_ARTIFACT),
            "attestor": "local-demo",
        },
        {
            "id": "invoice_123",
            "type": "sig",
            "ref": "inline:invoice_signer_payload",
            "payload": payload,
            "alg": "ed25519",
            "signature": _b64(sig),
            "key_id": key_id,
            "signer": key_id,
            "attestor": "demo",
        },
    ]
    HASH_OK_PATH.write_text(json.dumps(hash_ok, indent=4) + "\n", encoding="utf-8")

    _set_trusted_key(keyring, key_id, _b64(pub_raw))
    return [str(HASH_OK_PATH.relative_to(REPO_ROOT))]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Regenerate demo signatures for signed example proposals."
    )
    parser.add_argument(
        "--target",
        choices=["all", "sig", "hash_ok"],
        default="all",
        help=(
            "Which example(s) to regenerate. 'sig' regenerates financial_sig_ok.json "
            "and failing/financial_sig_bad.json using demo_signer_v1. 'hash_ok' "
            "regenerates financial_hash_ok.json's hash + signature evidence using "
            "demo_hash_signer_v1. 'all' does both. Default: all."
        ),
    )
    args = parser.parse_args()

    keyring = _read_existing_keyring()
    updated_files: list[str] = []

    if args.target in ("all", "sig"):
        updated_files.extend(_regenerate_sig_examples(keyring))
    if args.target in ("all", "hash_ok"):
        updated_files.extend(_regenerate_hash_ok_example(keyring))

    KEYS_EXAMPLE_PATH.write_text(json.dumps(keyring, indent=2) + "\n", encoding="utf-8")
    updated_files.append(str(KEYS_EXAMPLE_PATH.relative_to(REPO_ROOT)))

    print("PASS: Wrote:")
    for path in updated_files:
        print(f" - {path}")
    print()
    print("Next (verify with the demo keyring):")
    print(
        "  PIC_KEYS_PATH=pic_keys.example.json "
        "pic-cli evidence-verify examples/financial_sig_ok.json"
    )
    print(
        "  PIC_KEYS_PATH=pic_keys.example.json "
        "pic-cli evidence-verify examples/failing/financial_sig_bad.json"
    )
    print(
        "  PIC_KEYS_PATH=pic_keys.example.json "
        "pic-cli verify examples/financial_hash_ok.json --verify-evidence"
    )


if __name__ == "__main__":
    main()
