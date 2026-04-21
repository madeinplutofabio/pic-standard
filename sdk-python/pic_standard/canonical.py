"""PIC Canonical JSON v1 reference implementation (Python).

This module is the Python reference implementation of PIC Canonical JSON v1
(PIC-CJSON/1.0), specified in ``docs/canonicalization.md``. Protocol
correctness is established by that specification plus the conformance
vectors under ``conformance/canonicalization/`` — not by this implementation
alone. If this implementation and the specification disagree, the
specification wins and this implementation is a bug.

The RFC 8785 / ECMAScript number and string serialization core is vendored
from Trail of Bits' ``rfc8785.py`` (Apache-2.0). See ``_rfc8785.py`` for the
vendored formatter, its upstream provenance (commit + SHA-256), and its
license header. Repo-level attribution lives in ``THIRD_PARTY_NOTICES.md``.

Public API:
    canonicalize(value) -> bytes
    sha256_hex(value) -> str
    intent_digest_hex(intent) -> str
    CanonicalizationError

Scope (per docs/canonicalization.md §12):
    - Implements §7.1–§7.9 and §7.12–§7.13 (canonicalization rules).
    - Implements the canonical-byte rule used by §8.4 for attestation
      object serialization, and provides convenience helpers:
        * ``sha256_hex`` for digests computed over canonical JSON bytes —
          i.e., §8.1 ``args_digest`` and §8.2 ``claims_digest``.
        * ``intent_digest_hex`` for §8.3 ``intent_digest``, which is
          computed over the raw UTF-8 bytes of the intent string (NOT
          canonicalized JSON bytes).
    - The two helpers are deliberately separate so that callers cannot
      accidentally use the canonical-JSON path for ``intent_digest``,
      which would hash the JSON-quoted form (e.g., ``"hello"`` with
      quotes) and produce incorrect bytes that would fail cross-language
      verification.
    - Does NOT implement §7.10 (base64 variant) or §7.11 (file hash rules)
      — those are PIC protocol constraints handled by the evidence module.
    - Does NOT implement the §8.4 transport/extraction rule (parsing an
      attestation object out of an evidence payload string) — that is an
      evidence-profile behavior handled by the evidence module.

PIC-specific behavior this module adds on top of the vendored formatter:
    1. Tuple rejection (§6 accepts only JSON-representable values; lists
       are the JSON-array analogue, tuples are not accepted).
    2. Non-string object key rejection (§7.3), enforced at the wrapper
       boundary rather than delegated to the vendored formatter.
    3. Lone-surrogate validation for object keys before sort (§7.13).
    4. Circular reference detection.
    5. Exception normalization: vendored canonicalization exceptions are
       caught and re-raised as PIC's own ``CanonicalizationError`` to keep
       the public API decoupled from the vendored library's error taxonomy.

Backward compatibility: this module is additive in v0.8.0. No existing
code paths use it yet — wiring into evidence signing is deferred to a
future release.
"""

from __future__ import annotations

import hashlib
from typing import Any

from . import _rfc8785


__all__ = [
    "canonicalize",
    "sha256_hex",
    "intent_digest_hex",
    "CanonicalizationError",
]


class CanonicalizationError(ValueError):
    """Raised when a value cannot be canonicalized per PIC Canonical JSON v1.

    This is PIC's public exception for canonicalization failures. It is
    intentionally independent of the vendored formatter's exception
    hierarchy: the public API MUST NOT leak vendored-library-specific
    exception types, so this module catches vendored canonicalization
    exceptions and re-raises them as ``CanonicalizationError``.

    Failure causes defined by the specification (non-exhaustive):
      - NaN, +Infinity, -Infinity (§7.9)
      - Integers outside the IEEE 754 safe integer range |n| <= 2^53 - 1 (§7.9)
      - Dicts with non-string keys (§7.3)
      - Strings or string keys containing lone surrogate code points (§7.13)
      - Tuples (explicitly rejected — use list to represent a JSON array)
      - Circular references among containers
      - Host-language types with no JSON mapping (sets, custom objects, etc.)
    """


def canonicalize(value: Any) -> bytes:
    """Serialize ``value`` to PIC Canonical JSON v1 bytes.

    Implements RFC 8785 serialization semantics plus the PIC canonicalization
    rules in §7.1–§7.9 and §7.12–§7.13 of ``docs/canonicalization.md``. The
    returned bytes are the canonical serialization used as input to §8.4
    attestation-object signing and to the digests in §8.1 ``args_digest``
    and §8.2 ``claims_digest``. §8.3 ``intent_digest`` uses a different
    input rule — use ``intent_digest_hex`` for that.

    Args:
        value: A JSON-representable value — dict (string-keyed), list, str,
            int (within the IEEE 754 safe integer range), finite float,
            bool, or None.

    Returns:
        The canonical UTF-8 byte sequence. No trailing newline. No BOM.

    Raises:
        CanonicalizationError: If the input is not canonicalizable per the
            specification. See the class docstring for the full failure list.
    """
    # Pre-validation enforces the PIC-specific rules at the wrapper
    # boundary: tuple rejection, non-string key rejection, lone-surrogate
    # rejection in object keys, and cycle detection.
    _validate(value, seen=set())

    # Hand the validated input to the vendored RFC 8785 formatter. Normalize
    # vendored canonicalization exceptions (CanonicalizationError and its
    # subclasses, e.g. IntegerDomainError, FloatDomainError) into PIC's own
    # CanonicalizationError so the public API stays decoupled from the
    # vendored library's error taxonomy. Other exception types are NOT
    # caught here — unexpected errors surface as-is so real bugs remain
    # debuggable.
    try:
        return _rfc8785.dumps(value)
    except _rfc8785.CanonicalizationError as e:
        raise CanonicalizationError(str(e)) from e


def sha256_hex(value: Any) -> str:
    """Return the lowercase hex SHA-256 digest of ``canonicalize(value)``.

    This is the convenience helper for digests over canonical JSON bytes,
    such as §8.1 ``args_digest`` and §8.2 ``claims_digest`` in
    ``docs/canonicalization.md``.

    It MUST NOT be used for §8.3 ``intent_digest``, which is defined over
    the raw UTF-8 bytes of the intent string rather than over canonicalized
    JSON string bytes. Use ``intent_digest_hex`` for that case; it is a
    separate helper precisely so this mistake cannot be made silently.
    """
    return hashlib.sha256(canonicalize(value)).hexdigest()


def intent_digest_hex(intent: str) -> str:
    """Return the lowercase hex SHA-256 digest of ``intent`` per §8.3.

    §8.3 of ``docs/canonicalization.md`` defines ``intent_digest`` as:

        intent_digest = SHA-256( UTF-8 bytes of intent string )

    This is deliberately computed over the raw UTF-8 bytes of the intent
    string — NOT over a canonicalized JSON string (which would include
    surrounding quotes and JSON escape sequences). Since the intent is a
    scalar string with no JSON structure to canonicalize, wrapping it in
    JSON serialization would add fragility without improving byte
    stability across implementations.

    This helper is kept separate from ``sha256_hex`` so callers cannot
    accidentally use the canonical-JSON digest path for ``intent_digest``,
    which would silently produce incorrect bytes that fail cross-language
    verification.

    Args:
        intent: The intent string. MUST be a ``str``; MUST NOT contain
            lone surrogate code points (per §7.13 — such input is
            non-conformant and rejected rather than repaired).

    Returns:
        The 64-character lowercase hex SHA-256 digest of the intent
        string's UTF-8 bytes.

    Raises:
        CanonicalizationError: If ``intent`` is not a ``str``, or if it
            contains a lone surrogate code point.
    """
    if not isinstance(intent, str):
        raise CanonicalizationError(
            f"intent must be a str, got {type(intent).__name__}. "
            f"§8.3 intent_digest is defined over the raw UTF-8 bytes of the "
            f"intent string."
        )
    try:
        intent_bytes = intent.encode("utf-8")
    except UnicodeEncodeError as e:
        raise CanonicalizationError(
            f"intent contains a lone surrogate code point at position "
            f"{e.start}. Per §7.13, such input is non-conformant and MUST "
            f"be rejected rather than repaired."
        ) from e
    return hashlib.sha256(intent_bytes).hexdigest()


# ------------------------------------------------------------------
# Pre-validation pass
# ------------------------------------------------------------------
# The vendored formatter handles most PIC-CJSON/1.0 rules directly
# (NaN/Inf rejection, out-of-range ints, non-UTF-8 string values). This
# pre-validation layer owns the PIC-specific rules at the wrapper
# boundary so the public API's semantics are not silently coupled to
# the vendored library's internal behavior:
#
#   1. Tuple rejection. The vendored formatter transparently treats
#      tuples as arrays. PIC rejects tuples explicitly so that callers
#      in other languages have an unambiguous "list = JSON array"
#      mapping; Python callers must convert tuples to list() before
#      canonicalizing.
#
#   2. Non-string object keys. §7.3 enforcement is PIC-owned here
#      rather than delegated to the vendored formatter. This avoids
#      a subtle edge case where a custom key object that happens to
#      implement .encode(...) would slip past the vendored
#      AttributeError-based check.
#
#   3. Lone surrogates in object KEYS. The vendored formatter catches
#      lone surrogates in string VALUES (via a UTF-8 encode round-trip
#      inside its string serializer). But object keys are first passed
#      through .encode("utf-16be") during sorting, which raises a
#      different UnicodeEncodeError that the vendored formatter does
#      not wrap. Pre-checking keys here surfaces such input as
#      CanonicalizationError with a clear, spec-anchored message.
#
#   4. Circular references. The vendored formatter has no cycle
#      detection and would recurse until Python's recursion limit
#      raises RecursionError. We detect cycles explicitly and raise
#      CanonicalizationError.
# ------------------------------------------------------------------

def _validate(value: Any, *, seen: set) -> None:
    """Pre-validate input before handing to the vendored formatter.

    Raises ``CanonicalizationError`` for any PIC-specific rule enforced
    at the wrapper boundary. Walks the full input; O(n) in total nodes.
    A second traversal happens inside the vendored formatter; for v0.8.0
    the 2x-traversal cost is acceptable for attestation-sized inputs.
    """
    # Tuples: explicit rejection. §6 defines input values as JSON values;
    # the array representative in Python is list, not tuple.
    if isinstance(value, tuple):
        raise CanonicalizationError(
            "Tuples are not accepted input for PIC Canonical JSON v1. "
            "Convert to list() before canonicalizing. This restriction "
            "ensures unambiguous cross-language mapping where list = JSON array."
        )

    # Scalars: no further structural validation needed here. The vendored
    # formatter handles NaN/Inf (floats), int range, and lone surrogates
    # in string values.
    # Note: bool is a subclass of int in Python, so the isinstance check
    # below catches both; that is fine because neither needs further
    # structural validation at this layer.
    if value is None or isinstance(value, (bool, int, float, str)):
        return

    # Containers: check for cycles, then recurse.
    oid = id(value)
    if oid in seen:
        raise CanonicalizationError(
            "Circular reference detected in input. PIC Canonical JSON v1 "
            "cannot canonicalize cyclic structures."
        )
    seen.add(oid)
    try:
        if isinstance(value, dict):
            for k in value.keys():
                # §7.3: non-string keys rejected at the wrapper boundary.
                if not isinstance(k, str):
                    raise CanonicalizationError(
                        f"Non-string object key: {k!r} (type {type(k).__name__}). "
                        f"PIC Canonical JSON v1 requires all object member names "
                        f"to be JSON strings (§7.3)."
                    )
                # §7.13: lone surrogates in keys rejected here so the
                # vendored formatter's utf-16be sort does not leak
                # UnicodeEncodeError unwrapped.
                try:
                    k.encode("utf-8")
                except UnicodeEncodeError as e:
                    raise CanonicalizationError(
                        f"Object key contains a lone surrogate code point "
                        f"at position {e.start}. Per §7.13, such input is "
                        f"non-conformant and MUST be rejected rather than "
                        f"repaired."
                    ) from e
            for v in value.values():
                _validate(v, seen=seen)
        elif isinstance(value, list):
            for item in value:
                _validate(item, seen=seen)
        # Other container-ish types (sets, custom objects, etc.) reach the
        # vendored formatter's final `else` branch and raise
        # CanonicalizationError there; we don't pre-check because the
        # vendored formatter's message is sufficient and will be normalized
        # into PIC's CanonicalizationError by canonicalize().
    finally:
        seen.discard(oid)
