"""PIC Standard conformance suite (``conformance/``).

This package contains:

- ``canonicalization/`` — byte-exact PIC Canonical JSON v1 test vectors.
- ``core/allow/``, ``core/block/`` — core verifier allow/block vectors.
- ``manifest.json`` — the index of all vectors the runner executes.
- ``run.py`` — the conformance runner (``python -m conformance.run``).

See the README files under ``conformance/`` for vector format specifications
and seeding discipline. The conformance suite is normative for PIC-CJSON/1.0
and for the PIC core verifier's allow/block boundary in v0.8.0.
"""
